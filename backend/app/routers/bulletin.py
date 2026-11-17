"""Visit summary and opt-in saved-version comparisons."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import Identity, identity
from ..comparison import compare_text, comparison_cache
from ..db import get_db
from ..models import Publication, Source, SourceRun, Version, utcnow

router = APIRouter(prefix="/api/bulletin", tags=["bulletin"])


@router.get("/updates")
def updates(
    after_version_id: int | None = Query(None, ge=0, le=9_007_199_254_740_991),
    anchor_hash: str = Query("", max_length=64),
    is_demo: bool = False,
    db: Session = Depends(get_db),
    user: Identity = Depends(identity),
):
    scope = (
        select(Version.id, Version.content_hash)
        .join(Publication, Version.publication_id == Publication.id)
        .join(Source, Publication.source_id == Source.id)
        .where(Publication.is_demo == is_demo, Source.kind.in_(["sidof", "platiica_catalog"]))
    )
    latest = db.execute(scope.order_by(Version.id.desc()).limit(1)).first()
    through = latest.id if latest else 0
    reset = bool(after_version_id == 0 and anchor_hash)
    if after_version_id:
        anchor = db.execute(scope.where(Version.id == after_version_id)).first()
        reset = anchor is None or anchor.content_hash != anchor_hash or after_version_id > through
    baseline = through if after_version_id is None or reset else after_version_id
    counts = {}
    for source_kind, prefix in (("sidof", "publications"), ("platiica_catalog", "catalog")):
        entries = (
            select(Version.publication_id, Version.sequence)
            .join(Publication, Version.publication_id == Publication.id)
            .join(Source, Publication.source_id == Source.id)
            .where(
                Version.id > baseline,
                Version.id <= through,
                Publication.is_demo == is_demo,
                Source.kind == source_kind,
            )
            .subquery()
        )
        new_ids = select(entries.c.publication_id).where(entries.c.sequence == 1)
        counts[f"new_{prefix}"] = (
            db.scalar(
                select(func.count(func.distinct(entries.c.publication_id))).where(entries.c.sequence == 1)
            )
            or 0
        )
        counts[f"changed_{prefix}"] = (
            db.scalar(
                select(func.count(func.distinct(entries.c.publication_id))).where(
                    entries.c.sequence > 1, entries.c.publication_id.not_in(new_ids)
                )
            )
            or 0
        )
    run_columns = (SourceRun.status, SourceRun.finished_at, SourceRun.period_start, SourceRun.period_end)
    runs = (
        select(*run_columns)
        .join(Source, SourceRun.source_id == Source.id)
        .where(Source.kind == "sidof")
        .order_by(SourceRun.id.desc())
    )
    recent = db.execute(runs.limit(1)).mappings().first()
    complete = db.execute(runs.where(SourceRun.status == "succeeded").limit(1)).mappings().first()
    return {
        **counts,
        "first_visit": after_version_id is None,
        "reset": reset,
        "cursor": {
            "version_id": through,
            "content_hash": latest.content_hash if latest else "",
            "visited_at": utcnow().isoformat(),
        },
        "latest_check": dict(recent) if recent else None,
        "last_complete_check": dict(complete) if complete else None,
    }


@router.get("/publications/{publication_id}/comparison")
def comparison(
    publication_id: int,
    from_version_id: int = Query(..., ge=1, le=9_007_199_254_740_991),
    to_version_id: int = Query(..., ge=1, le=9_007_199_254_740_991),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=20),
    db: Session = Depends(get_db),
    user: Identity = Depends(identity),
):
    rows = (
        db.execute(
            select(Version.id, Version.sequence, Version.content_hash, Version.captured_at).where(
                Version.publication_id == publication_id, Version.id.in_([from_version_id, to_version_id])
            )
        )
        .mappings()
        .all()
    )
    versions = {row["id"]: row for row in rows}
    if len(versions) != 2 or from_version_id not in versions or to_version_id not in versions:
        raise HTTPException(404, "No se encontraron ambas versiones de esta publicación.")
    before, after = versions[from_version_id], versions[to_version_id]
    if before["sequence"] >= after["sequence"]:
        raise HTTPException(422, "Selecciona una versión anterior para comparar.")
    key = (db.get_bind(), from_version_id, to_version_id, before["content_hash"], after["content_hash"])
    result = comparison_cache.get(key)
    if result is None:
        texts = dict(
            db.execute(
                select(Version.id, Version.content).where(
                    Version.publication_id == publication_id, Version.id.in_([from_version_id, to_version_id])
                )
            ).all()
        )
        result = compare_text(texts[from_version_id] or "", texts[to_version_id] or "")
        comparison_cache.put(key, result)
    total = len(result["rows"])
    return {key: value for key, value in result.items() if key != "rows"} | {
        "from_version_id": from_version_id,
        "to_version_id": to_version_id,
        "from_captured_at": before["captured_at"],
        "to_captured_at": after["captured_at"],
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": result["rows"][(page - 1) * page_size : page * page_size],
    }
