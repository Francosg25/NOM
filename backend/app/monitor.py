"""Small single-instance portal: initialize storage and consume the existing queue."""
import logging
from datetime import timedelta
from threading import Event, Thread
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .models import Source, utcnow

log = logging.getLogger('nom.monitor')


def initialize_portal():
    from .cli import apply_migrations, init_sources
    apply_migrations()
    with SessionLocal() as db:
        init_sources(db)
        if get_settings().scheduler_enabled:
            today = utcnow().astimezone(ZoneInfo('America/Mexico_City')).date()
            for source in db.scalars(select(Source).where(Source.active.is_(True))):
                # An existing date means the source has already been configured.
                if source.urls and source.schedule_start is None:
                    from .collectors.sidof import is_daily
                    source.schedule_start = today - timedelta(days=6) if source.kind == 'sidof' and is_daily(source.urls) else today
                    source.schedule_enabled = True
            db.commit()


def tick():
    from .jobs import run_once
    from .operations import advance_schedule, reevaluate_batch, schedule_due
    with SessionLocal() as db:
        if get_settings().scheduler_enabled:
            schedule_due(db)
        job = run_once(db)
        advance_schedule(db, job)
        task = reevaluate_batch(db)
        if job:
            from .cli import upgrade_sidof_source
            upgrade_sidof_source(db)
            log.info('Consulta %s: %s, nuevos=%s, cambios=%s', job.id, job.status,
                     job.new_count, job.modified_count)
        return job is not None or task is not None


def start_monitor(stop: Event):
    def run():
        while not stop.wait(3):
            try:
                tick()
            except Exception:
                log.exception('La consulta no pudo completarse; se volverá a revisar la cola')
                stop.wait(30)
    thread = Thread(target=run, name='nom-monitor', daemon=True)
    thread.start()
    return thread
