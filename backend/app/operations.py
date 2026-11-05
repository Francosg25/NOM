"""Database-backed catalogue work and opt-in source scheduling."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, or_, select, update
from sqlalchemy.exc import IntegrityError

from .jobs import _refresh_proposals, request_job
from .models import Audit, CatalogItem, Job, Publication, Reevaluation, Source, SourceRun, Version, utcnow


def enqueue_reevaluation(db, catalog_id: int, actor: str):
    # An edit to a family also affects descendants that inherit its rules.
    ids, frontier = {catalog_id}, [catalog_id]
    while frontier:
        children = list(db.scalars(select(CatalogItem.id).where(CatalogItem.parent_id.in_(frontier))))
        frontier = [id for id in children if id not in ids]
        ids.update(frontier)
    for id in sorted(ids):
        changed = db.execute(
            update(Reevaluation)
            .where(Reevaluation.catalog_id == id)
            .values(
                requested_revision=Reevaluation.requested_revision + 1,
                cursor=0,
                actor=actor,
                requested_at=utcnow(),
                error=None,
            )
        ).rowcount
        if not changed:
            try:
                with db.begin_nested():
                    db.add(Reevaluation(catalog_id=id, actor=actor))
                    db.flush()
            except IntegrityError:
                db.execute(
                    update(Reevaluation)
                    .where(Reevaluation.catalog_id == id)
                    .values(
                        requested_revision=Reevaluation.requested_revision + 1,
                        cursor=0,
                        actor=actor,
                        requested_at=utcnow(),
                        error=None,
                    )
                )


def reevaluate_batch(db, limit=50):
    """One bounded transaction. A concurrent edit resets the cursor after commit.

    PostgreSQL row locks serialize consumers; compare-and-set also protects
    SQLite. A crash rolls back proposals and cursor together; it is safe to retry.
    """
    task = db.scalar(
        select(Reevaluation)
        .where(Reevaluation.requested_revision > Reevaluation.completed_revision)
        .order_by(Reevaluation.requested_at, Reevaluation.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if task is None:
        db.rollback()
        return None
    revision, cursor = task.requested_revision, task.cursor
    claimed = db.execute(
        update(Reevaluation)
        .where(
            Reevaluation.id == task.id,
            Reevaluation.requested_revision == revision,
            Reevaluation.cursor == cursor,
            Reevaluation.completed_revision < revision,
        )
        .values(error=None)
    ).rowcount
    if not claimed:
        db.rollback()
        return None
    item = db.get(CatalogItem, task.catalog_id)
    pubs = (
        db.scalars(
            select(Publication)
            .where(Publication.id > cursor, Publication.is_demo == item.is_demo)
            .order_by(Publication.id)
            .limit(limit)
        ).all()
        if item.active
        else []
    )
    catalog = db.scalars(select(CatalogItem).where(CatalogItem.is_demo == item.is_demo)).all()
    created = 0
    for pub in pubs:
        version = db.get(Version, pub.current_version_id) if pub.current_version_id else None
        if version:
            created += _refresh_proposals(db, pub, version, actor=task.actor, items=[item], catalog=catalog)
    task.cursor = pubs[-1].id if pubs else cursor
    if len(pubs) < limit:
        task.completed_revision = revision
    db.add(
        Audit(
            actor="sistema",
            action="reevaluar_lote",
            entity_type="catalog",
            entity_id=str(item.id),
            after={"revision": revision, "cursor": task.cursor, "processed": len(pubs), "created": created},
        )
    )
    db.commit()
    return {
        "catalog_id": item.id,
        "processed": len(pubs),
        "created": created,
        "complete": task.completed_revision == revision,
    }


def schedule_due(db, now=None):
    """Called by one supervised scheduler; no external service or paid timer needed.

    Unfinished intervals are retried before advancing. Limit-only partial batches
    resume immediately; failed requests back off to the configured frequency.
    A one-day overlap rechecks recent DOF changes after successful intervals.
    """
    now = now or utcnow()
    today = now.astimezone(ZoneInfo("America/Mexico_City")).date()
    ids = list(
        db.scalars(
            select(Source.id)
            .where(
                Source.active.is_(True),
                Source.schedule_enabled.is_(True),
                or_(Source.next_due_at.is_(None), Source.next_due_at <= now),
            )
            .order_by(case((Source.kind == "sidof", 0), else_=1), Source.id)
        )
    )
    created = []
    for source_id in ids:
        source = db.get(Source, source_id)
        if not source.urls or not source.schedule_start or source.schedule_start > today:
            source.last_error = "Programación incompleta: configure URLs y fecha inicial no futura."
            source.next_due_at = now + timedelta(hours=source.frequency_hours)
            db.commit()
            continue
        if db.scalar(select(Job.id).where(Job.source_id == source.id, Job.active_key.is_not(None))):
            db.rollback()
            continue
        previous = db.scalar(
            select(Job)
            .where(Job.source_id == source.id, Job.requested_by == "scheduler")
            .order_by(Job.requested_at.desc(), Job.id.desc())
            .limit(1)
        )
        if previous:
            run = db.scalar(select(SourceRun).where(SourceRun.job_id == previous.id))
            snapshot = run.source_snapshot if run else None
            if snapshot and any(
                snapshot.get(key, []) != getattr(source, key) for key in ("kind", "urls", "expected_terms")
            ):
                previous = None
        from .collectors.sidof import is_daily

        daily = source.kind == "sidof" and is_daily(source.urls)
        # An unavailable historical date must not freeze future daily checks.
        # Finish other queued dates first; then retry the rolling seven-day window.
        rolling_start = None
        if (
            daily
            and previous
            and previous.error_count
            and (
                previous.period_end < today
                or not any(not item.get("failed") for item in (previous.continuation or {}).get("queue", []))
            )
        ):
            previous = None
            rolling_start = max(source.schedule_start, today - timedelta(days=6))
        continuation = None
        if previous and previous.status in ("partial", "failed", "interrupted"):
            start, end, continuation = previous.period_start, previous.period_end, previous.continuation
        else:
            start = (
                max(source.schedule_start, previous.period_end - timedelta(days=1))
                if previous
                else rolling_start or source.schedule_start
            )
            # Advance large backlogs rather than remaining stuck on the overlap.
            if previous and previous.period_end < today:
                start = max(source.schedule_start, previous.period_end)
            end = min(today, start + timedelta(days=365))
        source.next_due_at = now + timedelta(hours=source.frequency_hours)
        db.commit()
        try:
            job = request_job(db, source.id, "scheduler", start, end, continuation)
            created.append(job.id)
        except ValueError as exc:
            source.last_error = str(exc)
            db.commit()
    return created


def advance_schedule(db, job):
    if job is None or job.requested_by != "scheduler":
        return
    source = db.get(Source, job.source_id)
    pending_dates = (job.continuation or {}).get("queue", [])
    unattempted_days = source.kind == "sidof" and any(not item.get("failed") for item in pending_dates)
    if source.schedule_enabled and (
        job.status == "partial"
        and job.error_count == 0
        or job.status == "partial"
        and unattempted_days
        or job.status == "succeeded"
        and job.period_end < utcnow().astimezone(ZoneInfo("America/Mexico_City")).date()
    ):
        source.next_due_at = utcnow()
        db.commit()
