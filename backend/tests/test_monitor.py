"""The single-process portal consumes a durable queue and preserves source choices."""
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app import cli, jobs, monitor
from app.collectors import Batch, Document
from app.config import Settings
from app.models import Audit, Base, Job, Publication, Source, Version
from app.storage import LocalEvidenceStore


def test_portal_initializes_and_monitors_without_external_services(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "portal.db"}')
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(_env_file=None, monitor_enabled=True, scheduler_enabled=True)
    monkeypatch.setattr(monitor, 'get_settings', lambda: settings)
    monkeypatch.setattr(monitor, 'SessionLocal', sessions)
    monkeypatch.setattr(cli, 'apply_migrations', lambda: Base.metadata.create_all(engine))
    monitor.initialize_portal()
    with sessions() as db:
        sources = db.scalars(select(Source).order_by(Source.id)).all()
        assert {source.kind for source in sources} == {'sidof', 'platiica_catalog'}
        assert all(source.schedule_enabled and source.schedule_start for source in sources)
        sidof_source = next(source for source in sources if source.kind == 'sidof')
        first_id = sidof_source.id
        for source in sources:
            if source.kind == 'sidof':
                continue
            source.schedule_enabled = False
        db.commit()
    # Restart preparation must respect an explicitly disabled source.
    monitor.initialize_portal()
    with sessions() as db:
        assert db.scalar(select(func.count(Source.id)).where(Source.schedule_enabled.is_(True))) == 1
    store = LocalEvidenceStore(tmp_path / 'evidence')
    document = Document('CONTROLLED-PORTAL', 'https://www.dof.gob.mx/',
        'Muestra controlada, no publicación oficial', 'Texto controlado para comprobar persistencia.', raw=b'controlled')
    original = jobs.run_once
    monkeypatch.setattr(jobs, 'run_once', lambda db: original(db,
        collector=lambda *args, **kwargs: Batch([document], True, None, 'Controlado'), storage=store))
    assert monitor.tick()
    assert not monitor.tick()
    with sessions() as db:
        job = db.scalar(select(Job).where(Job.source_id == first_id))
        assert job.status == 'succeeded' and job.new_count == 1
        version = db.scalar(select(Version))
        assert store.read(version.evidence_key) == b'controlled'
        assert db.scalar(select(func.count(Publication.id))) == 1
    engine.dispose()


def test_official_source_upgrade_preserves_documents_and_cancels_legacy_queue(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "upgrade.db"}')
    Base.metadata.create_all(engine)
    store = LocalEvidenceStore(tmp_path / 'evidence')
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        old = Source(name='PLATIICA',kind='platiica',urls=['https://platiica.economia.gob.mx/ficha/'],active=True,schedule_enabled=True)
        db.add(old); db.commit()
        jobs.ingest_document(db,old,Document('HISTORICAL','https://platiica.economia.gob.mx/ficha/',
            'Historical document','Keep this text',raw=b'historical-evidence'),store)
        db.commit()
        queued = jobs.request_job(db,old.id,'test')
        cli.init_sources(db)
        assert not old.active and not old.schedule_enabled
        assert queued.status == 'cancelled' and queued.active_key is None
        assert {s.kind for s in db.scalars(select(Source).where(Source.active.is_(True)))} == {
            'sidof',
            'platiica_catalog',
        }
        assert db.scalar(select(func.count(Publication.id))) == 1
        version = db.scalar(select(Version))
        assert store.read(version.evidence_key) == b'historical-evidence'
        cli.init_sources(db)
        assert db.scalar(select(func.count(Audit.id)).where(Audit.action == 'retirar_fuente')) == 1
    engine.dispose()
