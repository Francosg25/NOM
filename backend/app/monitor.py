"""Small single-instance portal: initialize storage and consume the existing queue."""

import logging
import json
from datetime import timedelta
from threading import Event, Thread
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .models import Source, utcnow

log = logging.getLogger("nom.monitor")


def initialize_portal():
    from .cli import apply_migrations, init_sources

    apply_migrations()
    with SessionLocal() as db:
        init_sources(db)
        if get_settings().scheduler_enabled:
            today = utcnow().astimezone(ZoneInfo("America/Mexico_City")).date()
            for source in db.scalars(select(Source).where(Source.active.is_(True))):
                # An existing date means the source has already been configured.
                if source.urls and source.schedule_start is None:
                    from .collectors.sidof import is_daily

                    source.schedule_start = (
                        today - timedelta(days=6)
                        if source.kind == "sidof" and is_daily(source.urls)
                        else today
                    )
                    source.schedule_enabled = True
            db.commit()
        from .observability import record_pulse

        record_pulse(db)


def tick():
    from .jobs import run_once
    from .operations import advance_schedule, reevaluate_batch, schedule_due

    with SessionLocal() as db:
        from .observability import record_pulse

        record_pulse(db)
        if get_settings().scheduler_enabled:
            schedule_due(db)
        job = run_once(db)
        advance_schedule(db, job)
        task = reevaluate_batch(db)
        if job:
            from .cli import upgrade_sidof_source

            upgrade_sidof_source(db)
            event = {
                "event": "sidof_check",
                "job_id": job.id,
                "status": job.status,
                "new_count": job.new_count,
                "modified_count": job.modified_count,
                "error_count": job.error_count,
            }
            (log.warning if job.error_count else log.info)(json.dumps(event))
        record_pulse(db)
        return job is not None or task is not None


def start_monitor(stop: Event):
    if not log.handlers:
        log.addHandler(logging.StreamHandler())
    log.setLevel(logging.INFO)
    log.propagate = False

    def run():
        while not stop.wait(3):
            try:
                tick()
            except Exception:
                log.exception("La consulta no pudo completarse; se volverá a revisar la cola")
                try:
                    from .observability import record_pulse

                    with SessionLocal() as db:
                        record_pulse(db, error=True)
                except Exception:
                    log.error("WORKER_HEARTBEAT_UNAVAILABLE")
                stop.wait(30)

    thread = Thread(target=run, name="nom-monitor", daemon=True)
    thread.start()
    return thread
