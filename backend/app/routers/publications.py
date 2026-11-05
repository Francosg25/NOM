"""Publication search, review and evidence downloads."""

from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from ..api_helpers import alert_dict, audit, fields, get_or_404, paginate, pub_dict, pub_dicts
from ..auth import Identity, identity, require_role
from ..db import get_db
from ..models import Alert, Audit, Publication, Source, Version
from ..schemas import PublicationInput

router = APIRouter(prefix="/api", tags=["publications"])


@router.get("/publications")
def publications(
    q: str = "",
    kind: str | None = None,
    status: str | None = None,
    source_id: int | None = None,
    source_kind: Literal["sidof"] | None = None,
    is_demo: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    sort: Literal["published", "detected"] = "detected",
    published_since: date | None = None,
    changes_only: bool = False,
    db: Session = Depends(get_db),
    user: Identity = Depends(identity),
):
    stmt = select(Publication).where(Publication.is_demo == is_demo)
    if source_kind:
        stmt = stmt.join(Source, Publication.source_id == Source.id).where(Source.kind == source_kind)
    stmt = (
        stmt.order_by(
            Publication.published_on.desc().nulls_last(),
            Publication.detected_at.desc(),
            Publication.id.desc(),
        )
        if sort == "published"
        else stmt.order_by(Publication.detected_at.desc(), Publication.id.desc())
    )
    if q:
        stmt = stmt.where(
            or_(
                Publication.title.ilike(f"%{q}%"),
                Publication.official_id.ilike(f"%{q}%"),
                select(Version.id)
                .where(Version.id == Publication.current_version_id, Version.content.ilike(f"%{q}%"))
                .exists(),
            )
        )
    if kind:
        stmt = stmt.where(Publication.kind == kind)
    if status:
        stmt = stmt.where(Publication.review_status == status)
    if source_id:
        stmt = stmt.where(Publication.source_id == source_id)
    if published_since:
        stmt = stmt.where(Publication.published_on >= published_since)
    if changes_only:
        stmt = stmt.where(
            select(Version.id)
            .where(Version.id == Publication.current_version_id, Version.sequence > 1)
            .exists()
        )
    rows, result = paginate(db, stmt, page, page_size)
    result["items"] = pub_dicts(db, rows)
    return result


@router.get("/publications/{id}")
def publication(id: int, db: Session = Depends(get_db), user: Identity = Depends(identity)):
    obj = get_or_404(db, Publication, id)
    result = pub_dict(db, obj)
    versions = db.scalars(
        select(Version).where(Version.publication_id == id).order_by(Version.sequence.desc())
    ).all()
    result["versions"] = [{**fields(v), "evidence_url": f"/api/versions/{v.id}/evidence"} for v in versions]
    result["alerts"] = [
        alert_dict(db, a) for a in db.scalars(select(Alert).where(Alert.publication_id == id)).all()
    ]
    return result


@router.patch("/publications/{id}")
def update_publication(
    id: int,
    body: PublicationInput,
    db: Session = Depends(get_db),
    user: Identity = Depends(require_role("revisor")),
):
    obj = get_or_404(db, Publication, id)
    before = fields(obj)
    data = body.model_dump(exclude_unset=True)
    evidence = data.pop("effective_evidence", None)
    if data.get("effective_verified"):
        proposed_date = data["effective_on"] if "effective_on" in data else obj.effective_on
        if not proposed_date or not evidence or not evidence.strip():
            raise HTTPException(
                422, "Verificar una fecha requiere fecha y evidencia de la disposición oficial"
            )
    if (
        data.get("effective_on") != obj.effective_on
        and "effective_on" in data
        and not data.get("effective_verified")
    ):
        data["effective_verified"] = False
    if (
        data.get("kind", obj.kind) is None
        or data.get("review_status", obj.review_status) is None
        or data.get("effective_verified", obj.effective_verified) is None
    ):
        raise HTTPException(422, "Tipo y estado no admiten null")
    for k, v in data.items():
        setattr(obj, k, v)
    audit(db, user, "revisar_publicacion", obj, before)
    if evidence:
        db.add(
            Audit(
                actor=user.id,
                action="evidencia_vigencia",
                entity_type="publications",
                entity_id=str(obj.id),
                before=None,
                after={
                    "evidence": evidence,
                    "effective_on": str(obj.effective_on),
                    "version_id": obj.current_version_id,
                },
            )
        )
    db.commit()
    return pub_dict(db, obj)


@router.get("/versions/{id}/evidence")
def evidence(id: int, db: Session = Depends(get_db), user: Identity = Depends(identity)):
    version = get_or_404(db, Version, id)
    if not version.evidence_key:
        raise HTTPException(404, "Esta versión no conserva un archivo recuperable")
    from ..storage import get_storage

    try:
        raw = get_storage().read(version.evidence_key)
    except FileNotFoundError:
        raise HTTPException(404, "Archivo de evidencia no disponible")
    # Never execute retrieved HTML or active content under the application origin.
    return Response(
        raw,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="evidencia-{id}.bin"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
