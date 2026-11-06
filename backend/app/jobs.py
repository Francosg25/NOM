"""Durable database queue and collection service, independent of the HTTP process."""

from __future__ import annotations

import hashlib
from copy import deepcopy
import json
import re
import threading
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .collectors import collect, CollectionError
from .matching import suggest, normalized
from .models import Alert, Audit, CatalogItem, Job, Publication, Source, SourceRun, Version, utcnow
from .storage import get_storage

LEASE_SECONDS = 120


def recover_interrupted(db: Session) -> int:
    """Reclaim dead processes without silently replaying their work."""
    cutoff = utcnow() - timedelta(seconds=LEASE_SECONDS)
    stale = db.scalars(select(Job).where(Job.status == "running", Job.heartbeat_at < cutoff)).all()
    for job in stale:
        # Compare-and-set: an active heartbeat can win this race and preserve ownership.
        changed = db.execute(
            update(Job)
            .where(Job.id == job.id, Job.status == "running", Job.heartbeat_at < cutoff)
            .values(
                status="interrupted",
                active_key=None,
                lease_token=None,
                finished_at=utcnow(),
                error="Proceso interrumpido; reanudar explícitamente para cubrir el periodo pendiente.",
                error_count=1,
            )
        ).rowcount
        if changed:
            db.execute(
                update(SourceRun)
                .where(SourceRun.job_id == job.id, SourceRun.status == "running")
                .values(
                    status="interrupted",
                    finished_at=utcnow(),
                    error_count=1,
                    error="Proceso interrumpido; periodo sin completar.",
                )
            )
            source = db.get(Source, job.source_id)
            if source:
                source.last_error = "Proceso interrumpido; periodo pendiente de reanudación."
    db.commit()
    return len(stale)


def request_job(
    db: Session,
    source_id: int,
    actor: str,
    period_start: date | None = None,
    period_end: date | None = None,
    continuation: dict | None = None,
) -> Job:
    source = db.get(Source, source_id)
    if source is None:
        raise ValueError("Fuente inexistente")
    if not source.active:
        raise ValueError("La fuente está desactivada")
    if continuation is not None:
        expected_config = {"kind": source.kind, "urls": list(source.urls)}
        if source.expected_terms:
            expected_config["expected_terms"] = list(source.expected_terms)
        if continuation.get("source_config") != expected_config:
            raise ValueError(
                "La configuración de la fuente cambió o el cursor no conserva su configuración; solicite de nuevo el periodo completo sin reanudar"
            )
        continuation = deepcopy(continuation)
    today = utcnow().astimezone(ZoneInfo("America/Mexico_City")).date()
    period_start, period_end = period_start or today, period_end or today
    if period_end < period_start or period_end > today:
        raise ValueError("El periodo debe ser válido y no incluir fechas futuras")
    if (period_end - period_start).days > 365:
        raise ValueError(
            "Solicite periodos de hasta 366 días; los límites se conservan mediante continuación"
        )
    recover_interrupted(db)
    key = str(source_id)
    previous = db.scalar(select(Job).where(Job.active_key == key))
    if previous:
        if (previous.period_start, previous.period_end, previous.continuation) != (
            period_start,
            period_end,
            continuation,
        ):
            raise ValueError(
                "La fuente tiene una ejecución activa para otro periodo o continuación; espere y vuelva a solicitar la consulta"
            )
        return previous
    job = Job(
        id=str(uuid.uuid4()),
        source_id=source_id,
        requested_by=str(actor),
        period_start=period_start,
        period_end=period_end,
        continuation=continuation,
        status="queued",
        active_key=key,
    )
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
        db.add(
            Audit(
                actor=str(actor),
                action="solicitar_consulta",
                entity_type="job",
                entity_id=job.id,
                after={
                    "source_id": source_id,
                    "period_start": str(period_start),
                    "period_end": str(period_end),
                    "resume": bool(continuation),
                },
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Job).where(Job.active_key == key))
        if existing is None:
            raise
        if (existing.period_start, existing.period_end, existing.continuation) != (
            period_start,
            period_end,
            continuation,
        ):
            raise ValueError(
                "La fuente tiene una ejecución activa para otro periodo o continuación; espere y vuelva a solicitar la consulta"
            )
        return existing
    return job


def claim_job(db: Session, job_id: str | None = None) -> Job | None:
    recover_interrupted(db)
    query = select(Job).where(Job.status == "queued")
    if job_id:
        query = query.where(Job.id == job_id)
    candidates = db.scalars(query.order_by(Job.requested_at).limit(20)).all()
    for candidate in candidates:
        token = str(uuid.uuid4())
        now = utcnow()
        claimed = db.execute(
            update(Job)
            .where(Job.id == candidate.id, Job.status == "queued")
            .values(
                status="running",
                started_at=now,
                heartbeat_at=now,
                lease_token=token,
            )
        ).rowcount
        db.commit()
        if claimed:
            db.refresh(candidate)
            source = db.get(Source, candidate.source_id)
            source.last_attempt_at = now
            db.add(
                SourceRun(
                    job_id=candidate.id,
                    source_id=candidate.source_id,
                    started_at=now,
                    period_start=candidate.period_start,
                    period_end=candidate.period_end,
                    continuation=candidate.continuation,
                    status="running",
                    source_snapshot={
                        "name": source.name,
                        "kind": source.kind,
                        "urls": list(source.urls),
                        "expected_terms": list(source.expected_terms),
                        "frequency_hours": source.frequency_hours,
                        "coverage": source.coverage,
                    },
                )
            )
            db.commit()
            return candidate
    return None


@contextmanager
def heartbeat(db: Session, job_id: str, token: str):
    """Renew leases during bounded remote requests without holding a DB transaction."""
    done = threading.Event()
    maker = sessionmaker(bind=db.get_bind())

    def renew():
        while not done.wait(10):
            try:
                with maker() as session:
                    result = session.execute(
                        update(Job)
                        .where(Job.id == job_id, Job.status == "running", Job.lease_token == token)
                        .values(heartbeat_at=utcnow())
                    )
                    session.commit()
                    if not result.rowcount:
                        return
            except Exception:
                # Main thread must reacquire ownership before storing any result.
                continue

    thread = threading.Thread(target=renew, name=f"job-heartbeat-{job_id}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join(timeout=2)


def _own(db: Session, job: Job, token: str):
    renewed = db.execute(
        update(Job)
        .where(Job.id == job.id, Job.status == "running", Job.lease_token == token)
        .values(heartbeat_at=utcnow())
    ).rowcount
    if not renewed:
        db.rollback()
        raise RuntimeError("La ejecución perdió su bloqueo; no se guardaron más resultados")


def _digest(document) -> str:
    # Navigation bytes are deliberately excluded once useful text is extracted.
    content = {
        "title": document.title,
        "content": document.content,
        "kind": document.kind,
        "published_on": str(document.published_on) if document.published_on else None,
        "processing_note": document.processing_note,
        "links": sorted(document.links),
        "norm_status": document.norm_status,
        "product_scope": document.product_scope,
    }
    if not document.content.strip():
        content["binary_sha256"] = hashlib.sha256(document.raw).hexdigest()
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _record_observation(db, job_id, publication, version, outcome):
    if job_id is None:
        return
    db.add(
        Audit(
            actor="sistema",
            action="observar_documento",
            entity_type="job",
            entity_id=job_id,
            after={
                "source_id": publication.source_id,
                "official_id": publication.official_id,
                "publication_id": publication.id,
                "media_type": version.media_type,
                "url": publication.url,
                "published_on": str(publication.published_on) if publication.published_on else None,
                "version_id": version.id,
                "outcome": outcome,
            },
        )
    )


def ingest_document(
    db: Session, source: Source, document, storage, *, is_demo: bool = False, job_id: str | None = None
) -> str:
    """Save a useful version; comparing against latest preserves A→B→A reversions."""
    pub = db.scalar(
        select(Publication).where(
            Publication.source_id == source.id, Publication.official_id == document.official_id
        )
    )
    now = utcnow()
    created = pub is None
    if created:
        pub = Publication(
            source_id=source.id,
            official_id=document.official_id,
            url=document.url,
            title=document.title,
            kind=document.kind,
            published_on=document.published_on,
            detected_at=now,
            last_seen_at=now,
            processing_note=document.processing_note,
            norm_status=document.norm_status,
            product_scope=document.product_scope,
            source_updated_at=document.source_updated_at,
            is_demo=is_demo,
        )
        db.add(pub)
        db.flush()
    elif pub.is_demo != is_demo:
        raise ValueError("No mezcle demostración y publicaciones oficiales")
    pub.norm_status = document.norm_status
    pub.product_scope = document.product_scope
    pub.source_updated_at = document.source_updated_at
    previous = db.get(Version, pub.current_version_id) if pub.current_version_id else None
    pub.last_seen_at = now
    content_hash = _digest(document)
    if previous and previous.content_hash == content_hash:
        _refresh_proposals(db, pub, previous, actor="sistema")
        _record_observation(db, job_id, pub, previous, "unchanged")
        return "unchanged"
    raw = document.raw or document.content.encode("utf-8")
    evidence_key = storage.put(raw, document.media_type)
    version = Version(
        publication_id=pub.id,
        sequence=(previous.sequence + 1 if previous else 1),
        content=document.content,
        content_hash=content_hash,
        evidence_key=evidence_key,
        media_type=document.media_type,
        captured_at=now,
        processing_note=document.processing_note,
    )
    version.links = list(document.links)
    db.add(version)
    db.flush()
    pub.current_version_id = version.id
    pub.title, pub.url, pub.kind = document.title, document.url, document.kind
    pub.published_on, pub.processing_note = document.published_on, document.processing_note
    pub.review_status = "pendiente"
    # Any manually verified effective date belongs to the reviewed version.
    if previous:
        pub.effective_verified = False
        for old in db.scalars(select(Alert).where(Alert.publication_id == pub.id)).all():
            db.add(
                Audit(
                    actor="sistema",
                    action="reabrir_por_version",
                    entity_type="alert",
                    entity_id=str(old.id),
                    before={
                        "status": old.status,
                        "decision": old.decision,
                        "decided_by": old.decided_by,
                        "decided_at": old.decided_at.isoformat() if old.decided_at else None,
                        "closure_reason": old.closure_reason,
                        "reason": old.reason,
                        "evidence": old.evidence,
                    },
                    after={"status": "pendiente", "decision": "propuesta", "version_id": version.id},
                )
            )
            old.status, old.decision = "pendiente", "propuesta"
            old.decided_by = old.decided_at = old.closure_reason = None
            old.reason = f"Documento modificado; reevaluar relación anterior. Versión {version.sequence}."
            old.evidence = (
                f"Versión anterior {previous.id}; nueva versión {version.id}. Consulte ambas evidencias."
            )
    _refresh_proposals(db, pub, version, update_existing=True)
    db.add(
        Audit(
            actor="sistema",
            action="detectar_publicacion" if created else "nueva_version",
            entity_type="publication",
            entity_id=str(pub.id),
            after={
                "version_id": version.id,
                "sequence": version.sequence,
                "hash": content_hash,
                "is_demo": is_demo,
            },
        )
    )
    _record_observation(db, job_id, pub, version, "new" if created else "modified")
    return "new" if created else "modified"


def _refresh_proposals(
    db: Session,
    pub: Publication,
    version: Version,
    *,
    update_existing: bool = False,
    actor: str = "sistema",
    items=None,
    catalog=None,
) -> int:
    created = 0
    if pub.norm_status is not None and pub.norm_status.casefold() != "vigente":
        return 0
    catalog_entry = pub.norm_status is not None
    if not catalog_entry:
        general = db.scalar(select(Alert).where(Alert.publication_id == pub.id, Alert.catalog_id.is_(None)))
        if general is None:
            db.add(
                Alert(
                    publication_id=pub.id,
                    catalog_id=None,
                    reason="Relevancia por evaluar: revisión general obligatoria",
                    evidence=f"Publicación detectada; versión {version.sequence}. No se infiere aplicabilidad legal.",
                )
            )
            created += 1
    catalog = (
        catalog
        if catalog is not None
        else db.scalars(select(CatalogItem).where(CatalogItem.is_demo == pub.is_demo)).all()
    )
    by_id = {item.id: item for item in catalog}
    existing_by_id = {
        a.catalog_id: a for a in db.scalars(select(Alert).where(Alert.publication_id == pub.id)).all()
    }
    for item in items if items is not None else catalog:
        if not item.active or item.is_demo != pub.is_demo:
            continue
        matches, ancestor, seen = [], item, set()
        while ancestor is not None and ancestor.id not in seen:
            seen.add(ancestor.id)
            if ancestor.active:
                inherited = suggest(pub.title + "\n" + version.content, ancestor)
                if ancestor.id != item.id:
                    for match in inherited:
                        match.reason += (
                            f" (regla heredada de {ancestor.kind}: {ancestor.name}, id {ancestor.id})"
                        )
                matches.extend(inherited)
            ancestor = by_id.get(ancestor.parent_id)
        if not matches:
            continue
        existing = existing_by_id.get(item.id)
        if existing and not update_existing:
            continue  # A catalogue edit never silently resets a reviewer's decision.
        reason = "; ".join(match.reason for match in matches)
        evidence = json.dumps(
            {
                "version_id": version.id,
                "matches": [match.__dict__ for match in matches],
                "disclaimer": "Posible impacto; requiere evaluación humana.",
            },
            ensure_ascii=False,
        )
        if existing:
            existing.reason, existing.evidence = reason, evidence
        else:
            relation = Alert(publication_id=pub.id, catalog_id=item.id, reason=reason, evidence=evidence)
            db.add(relation)
            db.flush()
            db.add(
                Audit(
                    actor=actor,
                    action="proponer_relacion",
                    entity_type="alert",
                    entity_id=str(relation.id),
                    after={
                        "publication_id": pub.id,
                        "catalog_id": item.id,
                        "version_id": version.id,
                        "reason": reason,
                        "evidence": evidence,
                    },
                )
            )
            created += 1
    return created


def reevaluate_publication(db: Session, publication_id: int, actor: str = "sistema") -> int:
    pub = db.get(Publication, publication_id)
    if pub is None:
        raise ValueError("Publicación inexistente")
    version = db.get(Version, pub.current_version_id) if pub.current_version_id else None
    return _refresh_proposals(db, pub, version, actor=actor) if version else 0


def reevaluate_all(db: Session, actor: str = "sistema") -> int:
    """Apply current transparent criteria to stored content; caller owns transaction."""
    return sum(reevaluate_publication(db, pub.id, actor) for pub in db.scalars(select(Publication)).all())


def run_once(
    db: Session, *, collector=collect, storage=None, limit: int = 40, job_id: str | None = None
) -> Job | None:
    job = claim_job(db, job_id)
    if job is None:
        return None
    token = job.lease_token
    source = db.get(Source, job.source_id)
    run = db.scalar(select(SourceRun).where(SourceRun.job_id == job.id))
    job_id = job.id
    snapshot = run.source_snapshot or {"kind": source.kind, "urls": list(source.urls)}
    source_kind, urls, start, end, continuation = (
        snapshot["kind"],
        list(snapshot["urls"]),
        job.period_start,
        job.period_end,
        job.continuation,
    )
    db.commit()  # Never hold a transaction over remote I/O.
    try:
        storage = storage or get_storage()
        with heartbeat(db, job_id, token):
            if source_kind == "platiica_catalog":
                from .collectors.platiica_catalog import collect_catalog

                known_updated = dict(
                    db.execute(
                        select(Publication.url, Publication.source_updated_at).where(
                            Publication.source_id == source.id,
                            Publication.is_demo.is_(False),
                        )
                    ).all()
                )
                batch = collect_catalog(
                    urls,
                    continuation,
                    limit,
                    known_updated,
                )
            else:
                batch = collector(source_kind, urls, start, end, continuation, limit=limit)
            for document in batch.documents:
                expected_terms = snapshot.get("expected_terms", [])

                def compact(text):
                    return re.sub(r"[\s-]", "", normalized(text))

                body = compact(document.title + "\n" + document.content)
                if any(compact(term) not in body for term in expected_terms if term.strip()):
                    raise CollectionError(
                        "Referencia esperada ausente; no se guardó la respuesta como publicación válida"
                    )
                _own(db, job, token)
                outcome = ingest_document(db, source, document, storage, job_id=job_id)
                job.reviewed_count += 1
                job.new_count += int(outcome == "new")
                job.modified_count += int(outcome == "modified")
                db.commit()
            _own(db, job, token)
            job.continuation = deepcopy(batch.continuation)
            if job.continuation is not None:
                job.continuation["source_config"] = {"kind": source_kind, "urls": list(urls)}
                if snapshot.get("expected_terms"):
                    job.continuation["source_config"]["expected_terms"] = list(snapshot["expected_terms"])
            errors = getattr(batch, "errors", [])
            for check in getattr(batch, "checks", []):
                db.add(
                    Audit(
                        actor="sistema",
                        action="revisar_indice_diario",
                        entity_type="job",
                        entity_id=job_id,
                        after=check,
                    )
                )
            job.error_count = len(errors)
            job.error = "\n".join(errors)[:5000] or None
            job.status = "succeeded" if batch.complete and not errors else "partial"
            source.coverage = batch.coverage + (
                " Revisión parcial: el periodo conserva un punto de continuación pendiente."
                if job.status == "partial"
                else ""
            )
            source.last_error = job.error
            if job.status == "succeeded":
                source.last_success_at = utcnow()
            _finish(db, job, run, coverage=source.coverage)
    except Exception as exc:
        db.rollback()
        db.refresh(job)
        if job.status != "running" or job.lease_token != token:
            return job
        job.status = "failed"
        job.error_count += 1
        job.error = (
            str(exc)[:3000]
            if isinstance(exc, (CollectionError, ValueError))
            else f"Error interno de recopilación ({type(exc).__name__}); revisar logs del servidor."
        )
        # Original continuation is retained so a retry cannot skip uncommitted work.
        source = db.get(Source, job.source_id)
        source.last_error = job.error
        run = db.scalar(select(SourceRun).where(SourceRun.job_id == job.id))
        _finish(db, job, run)
    return job


def _finish(db: Session, job: Job, run: SourceRun, coverage: str | None = None):
    job.finished_at = utcnow()
    job.active_key = None
    job.lease_token = None
    for field in (
        "status",
        "reviewed_count",
        "new_count",
        "modified_count",
        "error_count",
        "error",
        "continuation",
        "finished_at",
    ):
        setattr(run, field, getattr(job, field))
    db.add(
        Audit(
            actor="sistema",
            action="finalizar_consulta",
            entity_type="job",
            entity_id=job.id,
            after={
                "status": job.status,
                "new": job.new_count,
                "modified": job.modified_count,
                "errors": job.error_count,
                "coverage": coverage,
            },
        )
    )
    db.commit()
