"""Behavioral smoke check for an isolated CI PostgreSQL, without network sources."""
from datetime import date
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, engine
from app.collectors import Batch, Document
from app.jobs import ingest_document, request_job, run_once
from app.models import Alert, CatalogItem, Job, Source, Version, utcnow
from app.operations import enqueue_reevaluation, reevaluate_batch, schedule_due
from app.storage import LocalEvidenceStore


def main():
    # Never run destructive/fixture checks against a production database.
    if get_settings().environment != 'test' or engine.dialect.name != 'postgresql' or engine.url.database != 'nom_ci':
        raise RuntimeError('Esta comprobación requiere ENVIRONMENT=test y la base PostgreSQL aislada nom_ci')
    day = date(2025, 6, 2)
    with TemporaryDirectory() as directory, SessionLocal() as db:
        store = LocalEvidenceStore(directory)
        source = Source(name='CI · muestra sintética', kind='dof', urls=['https://www.dof.gob.mx/index.php'])
        family = CatalogItem(kind='familia', name='CI · familia', keywords=['motor de ensayo'])
        db.add_all([source, family]); db.flush()
        sub = CatalogItem(kind='subfamilia', name='CI · subfamilia', parent_id=family.id)
        db.add(sub); db.flush()
        product = CatalogItem(kind='producto', name='CI · producto', parent_id=sub.id)
        db.add(product); db.commit()
        for value in ('A', 'B', 'A'):
            doc = Document('CI-10001', 'https://www.dof.gob.mx/nota_detalle.php?codigo=10001',
                'Muestra sintética CI', 'motor de ensayo ' + value, day, raw=value.encode())
            ingest_document(db, source, doc, store)
            db.commit()
        versions = db.scalars(select(Version).order_by(Version.id)).all()
        assert len(versions) == 3
        assert [store.read(v.evidence_key) for v in versions] == [b'A', b'B', b'A']
        assert db.scalar(select(Alert).where(Alert.catalog_id == product.id)) is not None
        enqueue_reevaluation(db, family.id, 'ci'); db.commit()
        while reevaluate_batch(db, limit=1):
            pass
        job = request_job(db, source.id, 'ci', day, day)
        result = run_once(db, storage=store, job_id=job.id,
            collector=lambda *a, **kw: Batch([doc], True, None, 'Muestra sintética CI'))
        assert result.status == 'succeeded' and result.new_count == result.modified_count == 0
        with SessionLocal() as reader:
            assert reader.get(Job, job.id).status == 'succeeded'
        source.schedule_enabled = True
        source.schedule_start = utcnow().astimezone(ZoneInfo('America/Mexico_City')).date().replace(day=1)
        db.commit()
        assert len(schedule_due(db)) == 1
        assert schedule_due(db) == []
    print('PostgreSQL: migraciones, persistencia, versiones A-B-A, herencia, cola y programación comprobadas.')


if __name__ == '__main__':
    main()
