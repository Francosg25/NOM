from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select

from .models import Alert, Audit, CatalogItem, Publication, Source, Version, utcnow


def mexico_today():
    return utcnow().astimezone(ZoneInfo('America/Mexico_City')).date()


def fields(obj):
    values = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for key, value in values.items():
        if isinstance(value, datetime) and value.tzinfo is None:
            values[key] = value.replace(tzinfo=timezone.utc)
    return jsonable_encoder(values)


def audit(db, user, action, obj, before=None):
    db.add(Audit(actor=user.id, action=action, entity_type=obj.__tablename__, entity_id=str(obj.id), before=before, after=fields(obj)))


def get_or_404(db, cls, id):
    obj = db.get(cls, id)
    if obj is None:
        raise HTTPException(404, 'Registro no encontrado')
    return obj


def paginate(db, stmt, page, page_size):
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return rows, {'items': [], 'total': total, 'page': page, 'page_size': page_size}


def catalog_dict(obj):
    result = fields(obj)
    required = ['owner', 'description']
    if obj.kind == 'producto':
        required += ['model','part_number','technical','use','tariff_code','nico','parent_id']
    result['missing_fields'] = [name for name in required if not getattr(obj, name)]
    if obj.kind == 'producto' and not any(k not in ('pilot_key','provenance_url','catalog_status') for k in (obj.technical or {})) and 'technical' not in result['missing_fields']:
        result['missing_fields'].append('technical')
    return result


def pub_dict(db, obj, context=None):
    result = fields(obj)
    source = context[0].get(obj.source_id) if context else db.get(Source, obj.source_id)
    result['source_name'] = source.name if source else None
    latest_effective = context[1].get(str(obj.id)) if context else db.scalar(select(Audit).where(Audit.entity_type == 'publications',Audit.entity_id == str(obj.id),Audit.action == 'evidencia_vigencia').order_by(Audit.id.desc()).limit(1))
    evidence_record = latest_effective.after if latest_effective else None
    result['effective_evidence'] = evidence_record.get('evidence') if evidence_record and evidence_record.get('version_id') == obj.current_version_id and obj.effective_verified else None
    result['effective_verified_by'] = latest_effective.actor if result['effective_evidence'] else None
    result['effective_verified_at'] = latest_effective.created_at.replace(tzinfo=timezone.utc).isoformat() if result['effective_evidence'] else None
    today = mexico_today()
    result['recently_published'] = bool(obj.published_on and today - timedelta(days=7) <= obj.published_on <= today)
    version = context[2].get(obj.current_version_id) if context else db.get(Version, obj.current_version_id) if obj.current_version_id else None
    result['excerpt'] = ' '.join(version.content.split())[:420] if version else ''
    result['has_changes'] = bool(version and version.sequence > 1)
    result['captured_at'] = version.captured_at.isoformat() if version else None
    return result


def pub_dicts(db, rows):
    if not rows: return []
    sources = {s.id:s for s in db.scalars(select(Source).where(Source.id.in_({p.source_id for p in rows})))}
    latest_ids = select(func.max(Audit.id)).where(Audit.entity_type == 'publications',
        Audit.entity_id.in_([str(p.id) for p in rows]), Audit.action == 'evidencia_vigencia').group_by(Audit.entity_id)
    records = {a.entity_id:a for a in db.scalars(select(Audit).where(Audit.id.in_(latest_ids)))}
    versions = {v.id: v for v in db.scalars(select(Version).where(Version.id.in_({p.current_version_id for p in rows if p.current_version_id})))}
    return [pub_dict(db, p, (sources, records, versions)) for p in rows]


def alert_dict(db, obj):
    result = fields(obj)
    publication = db.get(Publication, obj.publication_id)
    catalog = db.get(CatalogItem, obj.catalog_id) if obj.catalog_id else None
    result.update(publication_title=publication.title if publication else None, is_demo=publication.is_demo if publication else False,
                  catalog_name=catalog.name if catalog else None)
    return result


def alert_dicts(db, rows):
    if not rows: return []
    pubs = {p.id:p for p in db.scalars(select(Publication).where(Publication.id.in_({a.publication_id for a in rows})))}
    cats = {c.id:c for c in db.scalars(select(CatalogItem).where(CatalogItem.id.in_({a.catalog_id for a in rows if a.catalog_id})))}
    return [{**fields(a), 'publication_title':pubs[a.publication_id].title,
             'is_demo':pubs[a.publication_id].is_demo,
             'catalog_name':cats[a.catalog_id].name if a.catalog_id in cats else None} for a in rows]
