from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Literal
from contextlib import asynccontextmanager
import asyncio
import json
from threading import Event
import json
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .auth import Identity, identity, require_role
from .config import get_settings
from .db import get_db
from .models import Alert, Audit, CatalogItem, Comment, Job, Publication, Reevaluation, Source, SourceRun, Version, utcnow

production = get_settings().environment == 'production'


@asynccontextmanager
async def lifespan(app):
    stop, thread = Event(), None
    if get_settings().monitor_enabled:
        from .monitor import initialize_portal, start_monitor
        await asyncio.to_thread(initialize_portal)
        thread = start_monitor(stop)
    yield
    stop.set()
    if thread:
        await asyncio.to_thread(thread.join, 2)


app = FastAPI(title='JE NOM Monitor', version='0.3.1', lifespan=lifespan,
              docs_url=None if production else '/api/docs', openapi_url=None if production else '/api/openapi.json')


@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path == '/api/docs' and not production:
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; connect-src 'self'; img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


def mexico_today():
    return utcnow().astimezone(ZoneInfo('America/Mexico_City')).date()


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CatalogInput(Input):
    kind: Literal['familia','subfamilia','producto'] | None = None
    parent_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=300)
    model: str | None = Field(None, max_length=200)
    part_number: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=20000)
    technical: dict | None = None
    use: str | None = Field(None, max_length=20000)
    tariff_code: str | None = Field(None, pattern=r'^\d{8}$')
    nico: str | None = Field(None, pattern=r'^\d{2}$')
    owner: str | None = Field(None, max_length=200)
    keywords: list[str] | None = Field(None, max_length=200)
    synonyms: list[str] | None = Field(None, max_length=200)
    watched_norms: list[str] | None = Field(None, max_length=200)
    active: bool | None = None
    is_demo: bool | None = None


class SourceInput(Input):
    name: str | None = Field(None, min_length=1, max_length=200)
    kind: Literal['dof','sidof','platiica','snice'] | None = None
    urls: list[str] | None = Field(None, max_length=100)
    expected_terms: list[str] | None = Field(None, max_length=50)
    frequency_hours: int | None = Field(None, ge=1, le=8760)
    active: bool | None = None
    coverage: str | None = Field(None, max_length=20000)
    schedule_enabled: bool | None = None
    schedule_start: date | None = None


class RelationInput(Input):
    publication_id: int
    catalog_id: int
    reason: str = Field(min_length=1, max_length=20000)
    evidence: str = Field(min_length=1, max_length=40000)


class AlertInput(Input):
    status: Literal['pendiente','en_revision','resuelta'] | None = None
    decision: Literal['propuesta','confirmada','descartada'] | None = None
    assigned_to: str | None = Field(None, max_length=200)
    closure_reason: str | None = Field(None, max_length=20000)


class PublicationInput(Input):
    review_status: Literal['pendiente','en_revision','resuelta'] | None = None
    kind: Literal['proyecto','norma_definitiva','modificacion','cancelacion','acuerdo','aviso','clasificacion_pendiente'] | None = None
    effective_on: date | None = None
    effective_verified: bool | None = None
    effective_evidence: str | None = Field(None, max_length=20000)


class CommentInput(Input):
    text: str = Field(min_length=1, max_length=20000)


class JobInput(Input):
    source_id: int
    period_start: date | None = None
    period_end: date | None = None
    resume_job_id: str | None = None


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
    result['recently_published'] = bool(obj.published_on and mexico_today() - timedelta(days=7) <= obj.published_on <= mexico_today())
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


@app.get('/api/health')
def health():
    release = Path(get_settings().frontend_dist) / 'portal-release.json'
    try:
        frontend = json.loads(release.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        frontend = {}
    return {'status':'ok', 'service':'JE NOM Monitor', 'frontend':frontend}


@app.get('/api/auth/config')
def auth_config():
    s = get_settings()
    return {'tenant_id':s.entra_tenant_id, 'client_id':s.entra_client_id,
            'scopes':s.entra_scopes.split(), 'app_service':s.entra_app_service_auth,
            'development':s.dev_auth_enabled and s.environment != 'production',
            'mode':s.auth_mode, 'demo_enabled':s.demo_mode}


@app.get('/api/me')
def me(user: Identity = Depends(identity)):
    return {**user.__dict__, 'development_auth': user.auth_mode == 'development'}


@app.get('/api/dashboard')
def dashboard(db: Session = Depends(get_db), user: Identity = Depends(identity)):
    count = lambda stmt: db.scalar(stmt) or 0
    sources = db.scalars(select(Source).order_by(Source.name)).all()
    upcoming = db.scalars(select(Publication).where(Publication.effective_verified.is_(True), Publication.effective_on >= mexico_today(), Publication.is_demo.is_(False)).order_by(Publication.effective_on).limit(10)).all()
    return {'publications_detected':count(select(func.count(Publication.id)).where(Publication.is_demo.is_(False))),
            'official_count':count(select(func.count(Publication.id)).where(Publication.is_demo.is_(False))),
            'demo_count':count(select(func.count(Publication.id)).where(Publication.is_demo.is_(True))),
            'alerts_pending':count(select(func.count(Alert.id)).join(Publication).where(Alert.status != 'resuelta',Publication.is_demo.is_(False))),
            'sources_with_errors':sum(bool(s.last_error) for s in sources),
            'upcoming':pub_dicts(db,upcoming), 'sources':[fields(s) for s in sources],
            'reevaluations_pending':count(select(func.count(Reevaluation.id)).where(Reevaluation.requested_revision > Reevaluation.completed_revision)),
            'scheduler_enabled':get_settings().scheduler_enabled,
            'monitor_enabled':get_settings().monitor_enabled}


@app.get('/api/catalog')
def catalog(q: str = '', kind: str | None = None, active: bool | None = None, is_demo: bool | None = None,
            page: int = Query(1,ge=1), page_size: int = Query(50,ge=1,le=200),
            db: Session = Depends(get_db), user: Identity = Depends(identity)):
    stmt = select(CatalogItem).order_by(CatalogItem.id)
    if q: stmt = stmt.where(or_(CatalogItem.name.ilike(f'%{q}%'), CatalogItem.part_number.ilike(f'%{q}%'), CatalogItem.model.ilike(f'%{q}%')))
    if kind: stmt = stmt.where(CatalogItem.kind == kind)
    if active is not None: stmt = stmt.where(CatalogItem.active == active)
    if is_demo is not None: stmt = stmt.where(CatalogItem.is_demo == is_demo)
    rows, result = paginate(db, stmt, page, page_size)
    parents = {c.id:c.name for c in db.scalars(select(CatalogItem).where(CatalogItem.id.in_({o.parent_id for o in rows if o.parent_id})))}
    result['items'] = [{**catalog_dict(o),'parent_name':parents.get(o.parent_id)} for o in rows]
    return result


def validate_catalog(db, data, existing=None):
    merged = fields(existing) if existing else {}
    merged.update(data)
    if not merged.get('name') or not merged.get('kind'):
        raise HTTPException(422,'Nombre y tipo son obligatorios')
    for key in ('technical','keywords','synonyms','watched_norms','active','is_demo'):
        if key in data and data[key] is None:
            raise HTTPException(422,f'{key} no admite null')
    if merged.get('is_demo') and not get_settings().demo_mode:
        raise HTTPException(422,'Activa DEMO_MODE en desarrollo para crear demostraciones')
    parent_id = merged.get('parent_id')
    if parent_id:
        parent = get_or_404(db,CatalogItem,parent_id)
        expected = {'subfamilia':'familia','producto':'subfamilia'}.get(merged['kind'])
        if parent.kind != expected or existing and parent.id == existing.id:
            raise HTTPException(422,'Jerarquía inválida: familia > subfamilia > producto')
        if bool(parent.is_demo) != bool(merged.get('is_demo',False)):
            raise HTTPException(422,'No mezcles registros de demostración con datos oficiales')
    elif merged['kind'] == 'familia' and parent_id is not None:
        raise HTTPException(422,'Una familia no admite padre')
    if existing and ('kind' in data or 'parent_id' in data or 'is_demo' in data):
        children = db.scalars(select(CatalogItem).where(CatalogItem.parent_id == existing.id)).all()
        for child in children:
            if {'familia':'subfamilia','subfamilia':'producto'}.get(merged['kind']) != child.kind or child.is_demo != merged.get('is_demo'):
                raise HTTPException(422,'El cambio invalidaría registros dependientes')


@app.post('/api/catalog',status_code=201)
def create_catalog(body: CatalogInput, db: Session = Depends(get_db), user: Identity = Depends(require_role('administrador'))):
    data = body.model_dump(exclude_unset=True)
    validate_catalog(db,data)
    obj = CatalogItem(**data)
    db.add(obj); db.flush(); audit(db,user,'crear',obj)
    from .operations import enqueue_reevaluation
    enqueue_reevaluation(db,obj.id,user.id)
    db.commit()
    return catalog_dict(obj)


@app.patch('/api/catalog/{id}')
def update_catalog(id: int, body: CatalogInput, db: Session = Depends(get_db), user: Identity = Depends(require_role('administrador'))):
    obj = get_or_404(db,CatalogItem,id); before = fields(obj)
    data = body.model_dump(exclude_unset=True); validate_catalog(db,data,obj)
    for k,v in data.items(): setattr(obj,k,v)
    audit(db,user,'actualizar',obj,before)
    from .operations import enqueue_reevaluation
    db.flush(); enqueue_reevaluation(db,obj.id,user.id)
    db.commit()
    return catalog_dict(obj)


@app.get('/api/publications')
def publications(q: str = '', kind: str | None = None, status: str | None = None, source_id: int | None = None,
                 is_demo: bool = False, page: int = Query(1,ge=1), page_size: int = Query(25,ge=1,le=200),
                 sort: Literal['published','detected'] = 'detected', published_since: date | None = None,
                 changes_only: bool = False,
                 db: Session = Depends(get_db), user: Identity = Depends(identity)):
    stmt = select(Publication).where(Publication.is_demo == is_demo)
    stmt = stmt.order_by(Publication.published_on.desc().nulls_last(), Publication.detected_at.desc(), Publication.id.desc()) if sort == 'published' else stmt.order_by(Publication.detected_at.desc(), Publication.id.desc())
    if q: stmt = stmt.where(or_(Publication.title.ilike(f'%{q}%'),Publication.official_id.ilike(f'%{q}%'),
        select(Version.id).where(Version.id == Publication.current_version_id, Version.content.ilike(f'%{q}%')).exists()))
    if kind: stmt = stmt.where(Publication.kind == kind)
    if status: stmt = stmt.where(Publication.review_status == status)
    if source_id: stmt = stmt.where(Publication.source_id == source_id)
    if published_since: stmt = stmt.where(Publication.published_on >= published_since)
    if changes_only: stmt = stmt.where(select(Version.id).where(Version.id == Publication.current_version_id, Version.sequence > 1).exists())
    rows,result = paginate(db,stmt,page,page_size); result['items'] = pub_dicts(db,rows)
    return result


@app.get('/api/publications/{id}')
def publication(id: int, db: Session = Depends(get_db), user: Identity = Depends(identity)):
    obj = get_or_404(db,Publication,id); result = pub_dict(db,obj)
    versions = db.scalars(select(Version).where(Version.publication_id == id).order_by(Version.sequence.desc())).all()
    result['versions'] = [{**fields(v),'evidence_url':f'/api/versions/{v.id}/evidence'} for v in versions]
    result['alerts'] = [alert_dict(db,a) for a in db.scalars(select(Alert).where(Alert.publication_id == id)).all()]
    return result


@app.patch('/api/publications/{id}')
def update_publication(id: int, body: PublicationInput, db: Session = Depends(get_db), user: Identity = Depends(require_role('revisor'))):
    obj = get_or_404(db,Publication,id); before = fields(obj); data = body.model_dump(exclude_unset=True)
    evidence = data.pop('effective_evidence',None)
    if data.get('effective_verified'):
        proposed_date = data['effective_on'] if 'effective_on' in data else obj.effective_on
        if not proposed_date or not evidence or not evidence.strip():
            raise HTTPException(422,'Verificar una fecha requiere fecha y evidencia de la disposición oficial')
    if data.get('effective_on') != obj.effective_on and 'effective_on' in data and not data.get('effective_verified'):
        data['effective_verified'] = False
    if data.get('kind',obj.kind) is None or data.get('review_status',obj.review_status) is None or data.get('effective_verified',obj.effective_verified) is None:
        raise HTTPException(422,'Tipo y estado no admiten null')
    for k,v in data.items(): setattr(obj,k,v)
    audit(db,user,'revisar_publicacion',obj,before)
    if evidence:
        db.add(Audit(actor=user.id,action='evidencia_vigencia',entity_type='publications',entity_id=str(obj.id),before=None,after={'evidence':evidence,'effective_on':str(obj.effective_on),'version_id':obj.current_version_id}))
    db.commit(); return pub_dict(db,obj)


@app.get('/api/versions/{id}/evidence')
def evidence(id: int, db: Session = Depends(get_db), user: Identity = Depends(identity)):
    version = get_or_404(db,Version,id)
    if not version.evidence_key: raise HTTPException(404,'Esta versión no conserva un archivo recuperable')
    from .storage import get_storage
    try:
        raw = get_storage().read(version.evidence_key)
    except FileNotFoundError:
        raise HTTPException(404,'Archivo de evidencia no disponible')
    # Never execute retrieved HTML or active content under the application origin.
    return Response(raw, media_type='application/octet-stream', headers={'Content-Disposition':f'attachment; filename="evidencia-{id}.bin"','X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'})


@app.get('/api/alerts')
def alerts(q: str = '', status: str | None = None, decision: str | None = None, general: bool = False,
           is_demo: bool = False, page: int = Query(1,ge=1), page_size: int = Query(25,ge=1,le=200),
           db: Session = Depends(get_db), user: Identity = Depends(identity)):
    stmt = select(Alert).join(Publication).where(Publication.is_demo == is_demo).order_by(Alert.id.desc())
    if q: stmt = stmt.where(Publication.title.ilike(f'%{q}%'))
    if status: stmt = stmt.where(Alert.status == status)
    if decision: stmt = stmt.where(Alert.decision == decision)
    if general: stmt = stmt.where(Alert.catalog_id.is_(None))
    rows,result = paginate(db,stmt,page,page_size); result['items'] = alert_dicts(db,rows)
    return result


@app.post('/api/alerts',status_code=201)
def propose_relation(body: RelationInput, db: Session = Depends(get_db), user: Identity = Depends(require_role('revisor'))):
    publication = get_or_404(db,Publication,body.publication_id)
    catalog = get_or_404(db,CatalogItem,body.catalog_id)
    if publication.is_demo != catalog.is_demo:
        raise HTTPException(422,'La relación no puede mezclar datos oficiales y demostraciones')
    if not catalog.active:
        raise HTTPException(422,'El registro de catálogo está desactivado')
    if not body.reason.strip() or not body.evidence.strip():
        raise HTTPException(422,'Motivo y evidencia son obligatorios')
    existing = db.scalar(select(Alert).where(Alert.publication_id == publication.id,Alert.catalog_id == catalog.id))
    if existing:
        raise HTTPException(409,'Ya existe una relación para este documento y registro')
    obj = Alert(publication_id=publication.id,catalog_id=catalog.id,reason=body.reason.strip(),evidence=body.evidence.strip())
    try:
        db.add(obj); db.flush(); audit(db,user,'proponer_relacion',obj); db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,'La relación ya fue registrada')
    return alert_dict(db,obj)


@app.get('/api/alerts/{id}')
def alert(id: int, db: Session = Depends(get_db), user: Identity = Depends(identity)):
    obj = get_or_404(db,Alert,id)
    return {**alert_dict(db,obj),'comments':[fields(c) for c in db.scalars(select(Comment).where(Comment.alert_id == id).order_by(Comment.id)).all()],
            'history':[fields(a) for a in db.scalars(select(Audit).where(Audit.entity_type.in_(['alerts','alert']),Audit.entity_id == str(id)).order_by(Audit.id)).all()]}


@app.patch('/api/alerts/{id}')
def update_alert(id: int, body: AlertInput, db: Session = Depends(get_db), user: Identity = Depends(require_role('revisor'))):
    obj = get_or_404(db,Alert,id); before = fields(obj); data = body.model_dump(exclude_unset=True)
    status = data.get('status',obj.status); decision = data.get('decision',obj.decision)
    if status is None or decision is None: raise HTTPException(422,'Estado y decisión no admiten null')
    deciding = 'decision' in data and decision != obj.decision
    closing = status == 'resuelta' and obj.status != 'resuelta'
    if (deciding and decision != 'propuesta' or closing) and not (data.get('closure_reason') or '').strip():
        raise HTTPException(422,'La decisión o cierre requiere justificación')
    if 'closure_reason' in data and (status == 'resuelta' or decision != 'propuesta') and not (data['closure_reason'] or '').strip():
        raise HTTPException(422,'Una relación decidida o cerrada debe conservar una justificación')
    if decision == 'confirmada' and obj.catalog_id is None:
        raise HTTPException(422,'La revisión general no confirma aplicabilidad a un producto o familia')
    for k,v in data.items(): setattr(obj,k,v)
    if deciding and decision != 'propuesta': obj.decided_by = user.id; obj.decided_at = utcnow()
    elif deciding: obj.decided_by = None; obj.decided_at = None
    audit(db,user,'revisar_relacion',obj,before); db.commit()
    return alert_dict(db,obj)


@app.post('/api/alerts/{id}/comments',status_code=201)
def comment(id: int, body: CommentInput, db: Session = Depends(get_db), user: Identity = Depends(require_role('revisor'))):
    get_or_404(db,Alert,id)
    if not body.text.strip(): raise HTTPException(422,'El comentario no puede estar vacío')
    obj = Comment(alert_id=id,author=user.id,text=body.text.strip()); db.add(obj); db.flush(); audit(db,user,'comentar',obj); db.commit()
    return fields(obj)


def validate_source_urls(kind, urls):
    if kind == 'dof' and len(urls) > 1:
        raise HTTPException(422,'DOF admite un único índice base; las ediciones se descubren desde sus enlaces')
    from .collectors import validate_url, CollectionError
    for url in urls:
        try: validate_url(url)
        except (ValueError, CollectionError) as exc: raise HTTPException(422,str(exc))
    from .collectors.core import HOSTS
    hosts = HOSTS
    from urllib.parse import urlsplit
    if any(urlsplit(u).hostname not in hosts[kind] for u in urls):
        raise HTTPException(422,'El dominio no coincide con el conector de la fuente')
    if kind == 'dof' and any(urlsplit(u).hostname not in {'www.dof.gob.mx', 'dof.gob.mx'} or
                             urlsplit(u).path != '/index.php' for u in urls):
        raise HTTPException(422,'El descubrimiento DOF requiere su índice /index.php; use SIDOF para documentos conocidos')
    if kind in {'platiica', 'snice'} and any(urlsplit(u).path in {'', '/'} for u in urls):
        raise HTTPException(422,'Configura una ficha o publicación concreta en lugar de la portada')


@app.get('/api/sources')
def sources(page: int = Query(1,ge=1), page_size: int = Query(50,ge=1,le=200), db: Session = Depends(get_db), user: Identity = Depends(identity)):
    rows,result = paginate(db,select(Source).order_by(Source.id),page,page_size); result['items'] = [fields(o) for o in rows]; return result


@app.post('/api/sources',status_code=201)
def create_source(body: SourceInput, db: Session = Depends(get_db), user: Identity = Depends(require_role('administrador'))):
    data = body.model_dump(exclude_unset=True)
    if not data.get('name') or not data.get('kind'): raise HTTPException(422,'Nombre y conector son obligatorios')
    if any(v is None for k,v in data.items() if k != 'schedule_start'): raise HTTPException(422,'Los campos de fuente no admiten null')
    validate_source_urls(data['kind'],data.get('urls') or [])
    validate_schedule(data)
    obj = Source(**data); db.add(obj); db.flush(); audit(db,user,'crear',obj); db.commit(); return fields(obj)


@app.patch('/api/sources/{id}')
def update_source(id: int, body: SourceInput, db: Session = Depends(get_db), user: Identity = Depends(require_role('administrador'))):
    obj = get_or_404(db,Source,id); before = fields(obj); data = body.model_dump(exclude_unset=True)
    if any(v is None for k,v in data.items() if k != 'schedule_start'): raise HTTPException(422,'Los campos de fuente no admiten null')
    if any(key in data and data[key] != getattr(obj,key) for key in ('kind','urls','expected_terms','active')) and db.scalar(select(Job).where(Job.source_id == id,Job.active_key.is_not(None))):
        raise HTTPException(409,'Espera a que termine el trabajo activo antes de cambiar el conector, URLs o estado')
    validate_source_urls(data.get('kind',obj.kind),data.get('urls',obj.urls))
    validate_schedule({**fields(obj), **data})
    for k,v in data.items(): setattr(obj,k,v)
    if any(k in data for k in ('schedule_enabled','schedule_start','frequency_hours')): obj.next_due_at = None
    audit(db,user,'actualizar',obj,before); db.commit(); return fields(obj)


def validate_schedule(data):
    start = data.get('schedule_start')
    if isinstance(start,str): start = date.fromisoformat(start)
    if data.get('schedule_enabled') and (not start or start > mexico_today() or not data.get('urls')):
        raise HTTPException(422,'Programación requiere URLs y fecha inicial no futura')


@app.get('/api/reevaluations')
def reevaluations(db: Session = Depends(get_db), user: Identity = Depends(identity)):
    rows = db.scalars(select(Reevaluation).where(Reevaluation.requested_revision > Reevaluation.completed_revision).order_by(Reevaluation.id).limit(100)).all()
    return {'items':[fields(o) for o in rows], 'pending': db.scalar(select(func.count(Reevaluation.id)).where(Reevaluation.requested_revision > Reevaluation.completed_revision))}


@app.get('/api/jobs')
def jobs(source_id: int | None = None,page: int = Query(1,ge=1),page_size: int = Query(25,ge=1,le=200),db: Session = Depends(get_db),user: Identity = Depends(identity)):
    stmt = select(Job).order_by(Job.requested_at.desc())
    if source_id: stmt = stmt.where(Job.source_id == source_id)
    rows,result = paginate(db,stmt,page,page_size); result['items'] = [fields(o) for o in rows]; return result


@app.post('/api/refresh', status_code=202)
def refresh_bulletin(db: Session = Depends(get_db), user: Identity = Depends(identity)):
    """Readers may request a bounded refresh of configured sources, without editing them."""
    from .jobs import request_job
    requested, recent = [], 0
    for source in db.scalars(select(Source).where(Source.active.is_(True))).all():
        if not source.urls:
            continue
        active = db.scalar(select(Job).where(Job.source_id == source.id, Job.active_key.is_not(None)))
        if active:
            requested.append(active.id)
            continue
        previous = db.scalar(select(Job).where(Job.source_id == source.id).order_by(Job.requested_at.desc(), Job.id.desc()).limit(1))
        if previous:
            unsuccessful = previous.status in ('failed', 'partial', 'interrupted')
            cooldown = 60 if unsuccessful else 900
            last_event = func.coalesce(Job.finished_at, Job.requested_at) if unsuccessful else Job.requested_at
            if db.scalar(select(Job.id).where(Job.id == previous.id,
                    last_event > utcnow() - timedelta(seconds=cooldown))):
                recent += 1
                continue
        try:
            requested.append(request_job(db, source.id, 'portal').id)
        except ValueError:
            db.rollback()
    return {'jobs':requested, 'recent_sources':recent, 'monitor_enabled':get_settings().monitor_enabled}


@app.post('/api/jobs',status_code=202)
def create_job(body: JobInput,db: Session = Depends(get_db),user: Identity = Depends(require_role('revisor'))):
    from .jobs import request_job
    source = get_or_404(db,Source,body.source_id)
    if not source.active: raise HTTPException(422,'La fuente está desactivada')
    start,end,continuation = body.period_start,body.period_end,None
    if body.resume_job_id:
        previous = get_or_404(db,Job,body.resume_job_id)
        if previous.source_id != source.id or previous.status not in ('partial','failed','interrupted'):
            raise HTTPException(422,'Solo se reanuda un trabajo parcial, fallido o interrumpido de la misma fuente')
        start,end,continuation = previous.period_start,previous.period_end,previous.continuation
    if start and end and start > end: raise HTTPException(422,'Periodo inválido')
    try: obj = request_job(db,source.id,user.id,start,end,continuation)
    except ValueError as exc: raise HTTPException(422,str(exc))
    audit(db,user,'solicitar_revision',obj); db.commit(); return fields(obj)


@app.get('/api/jobs/{id}')
def job(id: str,db: Session = Depends(get_db),user: Identity = Depends(identity)):
    obj = get_or_404(db,Job,id)
    observations = db.scalars(select(Audit).where(Audit.entity_type == 'job', Audit.entity_id == id,
        Audit.action == 'observar_documento').order_by(Audit.id)).all()
    finished = db.scalar(select(Audit).where(Audit.entity_type == 'job', Audit.entity_id == id,
        Audit.action == 'finalizar_consulta').order_by(Audit.id.desc()).limit(1))
    return {**fields(obj),'runs':[fields(r) for r in db.scalars(select(SourceRun).where(SourceRun.job_id == id).order_by(SourceRun.id)).all()],
            'documents':[o.after for o in observations], 'coverage': finished.after.get('coverage') if finished else None}


@app.get('/api/audit')
def audit_list(entity_type: str | None = None,entity_id: str | None = None,page: int = Query(1,ge=1),page_size: int = Query(50,ge=1,le=200),db: Session = Depends(get_db),user: Identity = Depends(require_role('revisor'))):
    stmt = select(Audit).order_by(Audit.id.desc())
    if entity_type: stmt = stmt.where(Audit.entity_type == entity_type)
    if entity_id: stmt = stmt.where(Audit.entity_id == entity_id)
    rows,result = paginate(db,stmt,page,page_size); result['items'] = [fields(o) for o in rows]; return result


# Serve one compiled application; API routes retain authentication and SPA fallback never swallows unknown APIs.
dist = Path(get_settings().frontend_dist).resolve()
if (dist / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')


@app.get('/{path:path}',include_in_schema=False)
def frontend(path: str):
    if path.startswith('api/') or path == 'api': raise HTTPException(404,'Ruta API no encontrada')
    index = dist / 'index.html'
    if not index.is_file(): raise HTTPException(503,'Compila el frontend con npm run build antes de iniciar')
    return FileResponse(index, headers={'Cache-Control': 'no-cache'})
