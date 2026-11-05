from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main
from app.config import Settings
from app.db import get_db
from app.models import Base, Job, Source, WorkerPulse
from app.observability import operational_status, record_pulse
from app.routers import operations

NOW = datetime(2026, 10, 2, 15, tzinfo=timezone.utc)


def test_heartbeat_failure_recovery_and_overdue_source(tmp_path, monkeypatch):
    import app.observability as module

    monkeypatch.setattr(module, "utcnow", lambda: NOW)
    engine = create_engine(f"sqlite:///{tmp_path / 'health.db'}")
    Base.metadata.create_all(engine)
    settings = Settings(_env_file=None, scheduler_enabled=True, monitor_enabled=True)
    with sessionmaker(bind=engine)() as db:
        assert "WORKER_UNAVAILABLE" in operational_status(db, settings, NOW)["codes"]
        source = Source(
            name="SIDOF",
            kind="sidof",
            urls=[],
            schedule_enabled=True,
            schedule_start=NOW.date(),
            next_due_at=NOW - timedelta(hours=1),
            last_attempt_at=NOW,
            last_error="private upstream details",
        )
        db.add(source)
        db.commit()
        record_pulse(db)
        codes = operational_status(db, settings, NOW)["codes"]
        assert "WORKER_UNAVAILABLE" not in codes
        assert codes == ["SCHEDULE_OVERDUE", "SOURCE_CHECK_INCOMPLETE"]
        record_pulse(db, error=True)
        assert not operational_status(db, settings, NOW)["worker_alive"]
        record_pulse(db)
        assert db.get(WorkerPulse, "monitor").consecutive_errors == 0
        assert not operational_status(db, settings, NOW + timedelta(minutes=3))["worker_alive"]
        # A lengthy active ingestion is alive through its renewed job lease.
        db.add(
            Job(
                id="live",
                requested_by="test",
                source_id=source.id,
                status="running",
                heartbeat_at=NOW + timedelta(minutes=3),
                period_start=NOW.date(),
                period_end=NOW.date(),
            )
        )
        db.commit()
        assert operational_status(db, settings, NOW + timedelta(minutes=3))["worker_alive"]
    engine.dispose()


def test_readiness_distinguishes_upstream_error_from_local_failure(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'ready.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    settings = Settings(_env_file=None, storage_path=str(tmp_path / "evidence"), scheduler_enabled=True)
    monkeypatch.setattr(operations, "get_settings", lambda: settings)

    def database():
        with sessions() as db:
            yield db

    main.app.dependency_overrides[get_db] = database
    try:
        with TestClient(main.app) as client:
            assert client.get("/api/ready").status_code == 503
            with sessions() as db:
                db.add(
                    Source(
                        name="SIDOF",
                        kind="sidof",
                        urls=[],
                        last_error="SECRET-TOKEN-EXAMPLE",
                        schedule_enabled=True,
                        schedule_start=NOW.date(),
                    )
                )
                record_pulse(db)
            assert client.get("/api/ready").status_code == 200
            response = client.get("/api/operations")
            assert response.json()["status"] == "degraded"
            assert "SOURCE_CHECK_INCOMPLETE" in response.json()["codes"]
            assert "SECRET-TOKEN" not in response.text
            # Unwritable evidence location must fail readiness, not /api/health.
            blocked = tmp_path / "file"
            blocked.write_text("not a folder")
            settings.storage_path = str(blocked)
            assert client.get("/api/ready").json()["codes"] == ["STORAGE_UNAVAILABLE"]
            assert client.get("/api/health").status_code == 200
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()
