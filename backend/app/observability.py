"""Durable worker heartbeat and health signals, without external services."""

from datetime import timedelta, timezone

from sqlalchemy import func, select

from .models import Job, Source, WorkerPulse, utcnow


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def record_pulse(db, name="monitor", error=False):
    pulse = db.get(WorkerPulse, name)
    if pulse is None:
        pulse = WorkerPulse(name=name, consecutive_errors=0)
        db.add(pulse)
    pulse.last_seen_at = utcnow()
    pulse.status = "error" if error else "ok"
    pulse.consecutive_errors = pulse.consecutive_errors + 1 if error else 0
    db.commit()


def operational_status(db, settings, now=None):
    now = now or utcnow()
    codes = []
    pulses = db.scalars(select(WorkerPulse)).all()
    latest_pulse = max((aware(p.last_seen_at) for p in pulses), default=None)
    recent = [p for p in pulses if aware(p.last_seen_at) >= now - timedelta(minutes=2)]
    active_heartbeat = db.scalar(select(func.max(Job.heartbeat_at)).where(Job.status == "running"))
    worker_alive = any(p.status == "ok" for p in recent) or bool(
        active_heartbeat and aware(active_heartbeat) >= now - timedelta(minutes=2)
    )
    if settings.monitor_enabled or settings.scheduler_enabled:
        if not worker_alive:
            codes.append("WORKER_UNAVAILABLE")
    if settings.scheduler_enabled:
        sources = db.scalars(select(Source).where(Source.active.is_(True), Source.kind == "sidof")).all()
        if not sources or any(not s.schedule_enabled or not s.schedule_start for s in sources):
            codes.append("SCHEDULE_NOT_CONFIGURED")
        if any(
            s.schedule_enabled and s.next_due_at and aware(s.next_due_at) < now - timedelta(minutes=15)
            for s in sources
        ):
            codes.append("SCHEDULE_OVERDUE")
        if any(s.last_error for s in sources):
            codes.append("SOURCE_CHECK_INCOMPLETE")
        if any(s.schedule_enabled and not s.last_attempt_at for s in sources):
            codes.append("FIRST_CHECK_PENDING")
    return {
        "status": "degraded" if codes else "ok",
        "codes": codes,
        "worker_alive": worker_alive,
        "last_worker_seen_at": latest_pulse,
        "scheduler_enabled": settings.scheduler_enabled,
        "monitor_enabled": settings.monitor_enabled,
    }
