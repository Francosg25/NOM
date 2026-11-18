"""Saved SIDOF archive coverage and paginated, evidence-based NOM references."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from ..api_helpers import get_or_404, mexico_today, paginate, pub_dicts
from ..auth import Identity, identity
from ..db import get_db
from ..models import Audit, Job, Publication, PublicationNormReference, Source
from ..publication_history import pending_count, primary_codes

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/coverage")
def coverage(
    year: int | None = Query(None, ge=1900, le=2100),
    is_demo: bool = False,
    db: Session = Depends(get_db),
    user: Identity = Depends(identity),
):
    year = year or mexico_today().year
    base = (
        select(Publication)
        .join(Source, Publication.source_id == Source.id)
        .where(Source.kind == "sidof", Publication.is_demo == is_demo)
    )
    scope = base.with_only_columns(Publication.id, Publication.published_on).subquery()
    first, last, total = db.execute(
        select(func.min(scope.c.published_on), func.max(scope.c.published_on), func.count()).select_from(
            scope
        )
    ).one()
    year_col = extract("year", scope.c.published_on)
    years = [
        {"year": int(y), "count": count}
        for y, count in db.execute(
            select(year_col, func.count())
            .where(scope.c.published_on.is_not(None))
            .group_by(year_col)
            .order_by(year_col.desc())
        )
    ]
    # One latest successful index observation per day. A requested period or a
    # min/max publication date is never treated as proof that all days were checked.
    day = Audit.after["day"].as_string()
    latest = (
        select(func.max(Audit.id))
        .join(Job, Audit.entity_id == Job.id)
        .join(Source, Job.source_id == Source.id)
        .where(
            Audit.entity_type == "job",
            Audit.action == "revisar_indice_diario",
            Source.kind == "sidof",
            day >= f"{year}-01-01",
            day <= f"{year}-12-31",
        )
        .group_by(day)
    )
    checks = [] if is_demo else db.scalars(select(Audit.after).where(Audit.id.in_(latest))).all()
    verified = sum(isinstance(check.get("unresolved"), list) and not check["unresolved"] for check in checks)
    return {
        "total": total,
        "first_publication": first,
        "last_publication": last,
        "years": years,
        "year": year,
        "verified_days": verified,
        "incomplete_days": len(checks) - verified,
        "no_publication_days": sum(bool(check.get("declared_no_publication")) for check in checks),
        "unindexed_publications": pending_count(db, is_demo),
    }


@router.get("/publications/{publication_id}")
def related_publications(
    publication_id: int,
    norm_code: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: Identity = Depends(identity),
):
    publication = get_or_404(db, Publication, publication_id)
    codes = primary_codes(publication)
    if norm_code and norm_code not in codes:
        raise HTTPException(422, "Selecciona una clave NOM identificada en esta ficha.")
    norm_code = norm_code or (codes[0] if codes else None)
    reference = PublicationNormReference
    stmt = (
        select(Publication)
        .join(Source, Publication.source_id == Source.id)
        .join(reference, reference.publication_id == Publication.id)
        .where(
            Source.kind == "sidof",
            Publication.is_demo == publication.is_demo,
            reference.norm_code == norm_code,
            reference.version_id == Publication.current_version_id,
        )
        .order_by(Publication.published_on.asc().nulls_last(), Publication.id.asc())
    )
    rows, result = paginate(db, stmt, page, 25)
    refs = (
        {
            r.publication_id: r
            for r in db.scalars(
                select(reference).where(
                    reference.norm_code == norm_code, reference.publication_id.in_([p.id for p in rows])
                )
            )
        }
        if rows
        else {}
    )
    result["items"] = [
        {
            **item,
            "reference_location": refs[item["id"]].location,
            "reference_snippet": refs[item["id"]].snippet,
        }
        for item in pub_dicts(db, rows, include_excerpt=False)
    ]
    return {
        **result,
        "norm_codes": codes,
        "selected_norm_code": norm_code,
        "unindexed_publications": pending_count(db, publication.is_demo),
    }
