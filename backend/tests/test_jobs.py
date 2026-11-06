from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.collectors import Batch, CollectionError, Document
from app.jobs import claim_job, ingest_document, recover_interrupted, request_job, run_once
from app.matching import suggest
from app.models import Alert, Audit, Base, CatalogItem, Job, Publication, Source, SourceRun, Version, utcnow
from app.operations import schedule_due
from app.storage import LocalEvidenceStore

DAY = date(2025, 1, 15)


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    with maker() as db:
        source = Source(name="Fuente controlada", kind="dof", urls=["https://www.dof.gob.mx/index.php"])
        db.add(source)
        db.commit()
        yield db, maker, LocalEvidenceStore(tmp_path / "evidence"), source.id
    engine.dispose()


def document(text="Texto sobre microactuador NOM-TEST y fracción 8501.10.01", *, identifier="CONTROLADO-1", raw=None):
    return Document(official_id=identifier, url="https://www.dof.gob.mx/nota_detalle.php?codigo=12345", title="Muestra controlada (no fuente oficial validada)",
                    content=text, published_on=DAY, raw=raw or text.encode(), kind="proyecto")


def collect_documents(*documents, complete=True, continuation=None, errors=None):
    return lambda *args, **kwargs: Batch(list(documents), complete, continuation, "Muestra controlada; no validación en vivo", errors or [])


def enqueue(db, source_id):
    return request_job(db, source_id, "test:operador", DAY, DAY)


def test_deduplication_ignores_navigation_noise(database):
    db, _, storage, source_id = database
    enqueue(db, source_id)
    first = run_once(db, collector=collect_documents(document(raw=b'<html>nav A</html>')), storage=storage)
    assert (first.status, first.new_count, first.reviewed_count) == ("succeeded", 1, 1)
    enqueue(db, source_id)
    second = run_once(db, collector=collect_documents(document(raw=b'<html>nav B</html>')), storage=storage)
    assert (second.new_count, second.modified_count, second.reviewed_count) == (0, 0, 1)
    assert db.scalar(select(func.count()).select_from(Publication)) == 1
    assert db.scalar(select(func.count()).select_from(Version)) == 1
    assert db.scalar(select(func.count()).select_from(Alert).where(Alert.catalog_id.is_(None))) == 1


def test_versions_and_reversions_reopen_decisions(database):
    db, _, storage, source_id = database
    item = CatalogItem(kind="familia", name="Familia configurable", keywords=["microactuador"])
    db.add(item); db.commit()
    for text in ("microactuador A", "microactuador B", "microactuador A"):
        enqueue(db, source_id)
        run = run_once(db, collector=collect_documents(document(text)), storage=storage)
        assert run.status == "succeeded"
        relation = db.scalar(select(Alert).where(Alert.catalog_id == item.id))
        assert relation.status == "pendiente"
        if text == "microactuador B":
            relation.status = "resuelta"
            relation.decision = "confirmada"
            relation.decided_by = "revisor:1"
            relation.decided_at = utcnow()
            relation.closure_reason = "Revisión de prueba documentada"
            db.commit()
    versions = db.scalars(select(Version).order_by(Version.sequence)).all()
    assert [v.sequence for v in versions] == [1, 2, 3]
    assert versions[0].content_hash == versions[2].content_hash != versions[1].content_hash
    assert storage.read(versions[0].evidence_key) == b"microactuador A"
    relation = db.scalar(select(Alert).where(Alert.catalog_id == item.id))
    assert relation.decision == "propuesta" and relation.decided_by is None
    history = db.scalars(select(Audit).where(Audit.action == "reabrir_por_version")).all()
    assert any(a.before["decision"] == "confirmada" and a.before["closure_reason"] for a in history)


def test_failed_query_keeps_last_success_and_can_recover(database):
    db, _, storage, source_id = database
    enqueue(db, source_id)
    run_once(db, collector=collect_documents(document()), storage=storage)
    successful_at = db.get(Source, source_id).last_success_at
    def fail(*args, **kwargs):
        raise CollectionError("Acceso de muestra denegado")
    enqueue(db, source_id)
    failed = run_once(db, collector=fail, storage=storage)
    source = db.get(Source, source_id)
    assert failed.status == "failed" and failed.error_count == 1
    assert source.last_success_at == successful_at and source.last_error
    assert source.last_attempt_at >= successful_at
    assert db.scalar(select(SourceRun).where(SourceRun.job_id == failed.id)).status == "failed"
    enqueue(db, source_id)
    recovered = run_once(db, collector=collect_documents(document()), storage=storage)
    assert recovered.status == "succeeded" and source.last_error is None


def test_partial_batch_preserves_errors_period_and_continuation(database):
    db, _, storage, source_id = database
    original = enqueue(db, source_id)
    cursor = {"queue": ["https://www.dof.gob.mx/nota_detalle.php?codigo=2"], "date": str(DAY)}
    partial = run_once(db, collector=collect_documents(document(), complete=False, continuation=cursor,
                                                     errors=["Tiempo de espera agotado"]), storage=storage)
    assert partial.id == original.id and partial.status == "partial"
    persisted_cursor = {**cursor, "source_config": {"kind": "dof", "urls": ["https://www.dof.gob.mx/index.php"]}}
    assert partial.new_count == 1 and partial.error_count == 1 and partial.continuation == persisted_cursor
    assert db.get(Source, source_id).last_success_at is None
    resumed = request_job(db, source_id, "test:operador", partial.period_start, partial.period_end, partial.continuation)
    def continuation_collector(kind, urls, start, end, continuation, **kwargs):
        assert (start, end, continuation) == (DAY, DAY, persisted_cursor)
        return Batch([document(identifier="CONTROLADO-2")], True, None, "Muestra completa")
    completed = run_once(db, collector=continuation_collector, storage=storage)
    assert completed.id == resumed.id and completed.status == "succeeded"
    assert db.scalar(select(func.count()).select_from(Publication)) == 2


def test_durable_queue_survives_new_session_and_prevents_duplicates(database):
    db, maker, storage, source_id = database
    job = enqueue(db, source_id)
    assert enqueue(db, source_id).id == job.id
    job_id = job.id
    with maker() as restarted:
        restored = restarted.get(Job, job_id)
        assert restored.status == "queued" and restored.period_start == DAY
        done = run_once(restarted, collector=collect_documents(document()), storage=storage)
        assert done.id == job_id and done.status == "succeeded"
    db.expire_all()
    assert db.get(Job, job_id).status == "succeeded"
    assert claim_job(db) is None


def test_dead_worker_marked_interrupted_without_false_success(database):
    db, _, _, source_id = database
    enqueue(db, source_id)
    job = claim_job(db)
    job.heartbeat_at = utcnow() - timedelta(minutes=10)
    job.continuation = {"date": str(DAY)}
    db.commit()
    assert recover_interrupted(db) == 1
    db.refresh(job)
    assert job.status == "interrupted" and job.active_key is None and job.continuation
    assert db.get(Source, source_id).last_success_at is None
    assert db.get(Source, source_id).last_error
    assert db.scalar(select(SourceRun).where(SourceRun.job_id == job.id)).status == "interrupted"


def test_recover_interrupted_handles_sqlite_naive_heartbeat_and_retries_schedule(database):
    db, _, _, source_id = database
    source = db.get(Source, source_id)
    source.schedule_enabled = True
    source.schedule_start = DAY
    source.next_due_at = utcnow() + timedelta(days=1)
    job = request_job(db, source_id, "scheduler", DAY, DAY)
    job = claim_job(db)
    job.heartbeat_at = utcnow() - timedelta(minutes=10)
    db.commit()
    job_id = job.id
    db.expire_all()
    assert db.get(Job, job_id).heartbeat_at.tzinfo is None

    assert recover_interrupted(db) == 1

    db.expire_all()
    interrupted = db.get(Job, job_id)
    source = db.get(Source, source_id)
    assert interrupted.status == "interrupted"
    assert source.next_due_at.replace(tzinfo=utcnow().tzinfo) <= utcnow()
    resumed_ids = schedule_due(db, now=utcnow())
    assert len(resumed_ids) == 1
    resumed = db.get(Job, resumed_ids[0])
    assert resumed.status == "queued" and resumed.requested_by == "scheduler"


def test_unmatched_documents_are_not_discarded(database):
    db, _, storage, source_id = database
    db.add(CatalogItem(kind="familia", name="Familia X", keywords=["término ausente"]))
    db.commit()
    enqueue(db, source_id)
    run_once(db, collector=collect_documents(document("Materia desconocida para el catálogo")), storage=storage)
    all_alerts = db.scalars(select(Alert)).all()
    assert len(all_alerts) == 1 and all_alerts[0].catalog_id is None
    assert all_alerts[0].decision == "propuesta"


def test_transparent_matching_norm_synonym_tariff_and_boundaries():
    item = SimpleNamespace(keywords=["bomba"], synonyms=["válvula"], watched_norms=["NOM-TEST"], tariff_code="85011001")
    result = suggest("Bombardero no es una coincidencia. Válvula; NOM-TEST; 8501.10.01", item)
    assert len(result) == 3
    assert all(match.reason and match.evidence for match in result)


def test_tariff_matching_distinguishes_exact_and_base_nico_matches():
    item = SimpleNamespace(keywords=[], synonyms=[], watched_norms=[], tariff_code="85011001", nico="12")
    exact = suggest("Fracción 8501.10.01 12", item)
    base = suggest("Fracción 8501.10.01 13", item)
    assert len(exact) == len(base) == 1
    assert "NICO configurados" in exact[0].reason
    assert "Fracción base configurada" in base[0].reason


def test_period_validation(database):
    db, _, _, source_id = database
    with pytest.raises(ValueError):
        request_job(db, source_id, "test", DAY, DAY - timedelta(days=1))
    with pytest.raises(ValueError):
        request_job(db, source_id, "test", DAY, DAY + timedelta(days=400))


def test_evidence_path_rejection(database):
    _, _, storage, _ = database
    with pytest.raises(ValueError):
        storage.read("../../secrets.env")


def test_demo_isolation_and_official_metrics(database, monkeypatch):
    from app import cli
    from app.config import Settings
    from app.main import app
    from app.db import get_db
    from app.auth import identity, Identity
    db, _, storage, source_id = database
    monkeypatch.setattr(cli, "get_storage", lambda: storage)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(environment="development", demo_mode=True, database_url="sqlite:///./data/demo.db"))
    cli.demo(db)
    assert db.scalar(select(func.count()).select_from(Publication).where(Publication.is_demo.is_(True))) == 1
    assert db.scalar(select(func.count()).select_from(Publication).where(Publication.is_demo.is_(False))) == 0
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[identity] = lambda: Identity("test", "test", "administrador", "development")
    try:
        with TestClient(app) as client:
            dash = client.get("/api/dashboard").json()
            assert dash["publications_detected"] == 0 and dash["demo_count"] == 1
            assert client.get("/api/publications").json()["total"] == 0
            assert client.get("/api/publications?is_demo=true").json()["total"] == 1
    finally:
        app.dependency_overrides.clear()
    # Official content in the same database blocks future demo loading.
    ingest_document(db, db.get(Source, source_id), document(), storage)
    db.commit()
    with pytest.raises(ValueError, match="datos oficiales"):
        cli.demo(db)


def test_main_flow_query_propose_review_and_evidence(database, monkeypatch):
    from app.main import app
    from app.db import get_db
    from app.auth import identity, Identity
    import app.storage as storage_module
    db, _, storage, source_id = database
    db.add(CatalogItem(kind="familia", name="Familia arbitraria", keywords=["microactuador"]))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[identity] = lambda: Identity("reviewer:controlado", "Revisor", "revisor", "development")
    monkeypatch.setattr(storage_module, "get_storage", lambda: storage)
    try:
        with TestClient(app) as client:
            response = client.post("/api/jobs", json={"source_id": source_id, "period_start": str(DAY), "period_end": str(DAY)})
            assert response.status_code == 202, response.text
            job_id = response.json()["id"]
            result = run_once(db, collector=collect_documents(document()), storage=storage)
            assert result.id == job_id and result.status == "succeeded"
            alerts = client.get("/api/alerts").json()["items"]
            proposed = next(alert for alert in alerts if alert["catalog_id"] is not None)
            assert proposed["decision"] == "propuesta" and "microactuador" in proposed["evidence"]
            review = client.patch(f'/api/alerts/{proposed["id"]}', json={"decision": "confirmada", "status": "resuelta", "closure_reason": "Revisión humana de muestra; evidencia evaluada"})
            assert review.status_code == 200, review.text
            assert review.json()["decided_by"] == "reviewer:controlado"
            assert review.json()["decided_at"]
            comment = client.post(f'/api/alerts/{proposed["id"]}/comments', json={"text": "Análisis de prueba documentado"})
            assert comment.status_code == 201
            pub = client.get(f'/api/publications/{proposed["publication_id"]}').json()
            evidence = client.get(pub["versions"][0]["evidence_url"])
            assert evidence.status_code == 200 and evidence.content == document().raw
            assert evidence.headers["content-type"] == "application/octet-stream"
            assert db.scalar(select(func.count()).select_from(Audit).where(Audit.action == "revisar_relacion")) == 1
    finally:
        app.dependency_overrides.clear()


def test_different_period_is_not_silently_lost(database):
    db, _, _, source_id = database
    original = enqueue(db, source_id)
    with pytest.raises(ValueError, match="otro periodo"):
        request_job(db, source_id, "test", DAY - timedelta(days=1), DAY)
    assert db.scalar(select(func.count()).select_from(Job)) == 1
    assert db.get(Job, original.id).period_start == DAY


def test_catalogue_reevaluation_creates_proposals_preserves_decisions(database):
    from app.jobs import reevaluate_all
    db, _, storage, source_id = database
    enqueue(db, source_id)
    run_once(db, collector=collect_documents(document()), storage=storage)
    assert db.scalar(select(func.count()).select_from(Alert)) == 1
    item = CatalogItem(kind="familia", name="Familia añadida después", keywords=["microactuador"])
    db.add(item); db.flush()
    assert reevaluate_all(db, "admin:prueba") == 1
    db.commit()
    relation = db.scalar(select(Alert).where(Alert.catalog_id == item.id))
    relation.decision, relation.status = "descartada", "resuelta"
    relation.decided_by, relation.decided_at = "revisor", utcnow()
    relation.closure_reason = "Descartada con evidencia de prueba"
    db.commit()
    assert reevaluate_all(db, "admin:prueba") == 0
    enqueue(db, source_id)
    run_once(db, collector=collect_documents(document()), storage=storage)
    assert relation.decision == "descartada" and relation.status == "resuelta"
    assert db.scalar(select(func.count()).select_from(Version)) == 1


def test_limit_only_partial_is_not_a_failed_query(database):
    db, _, storage, source_id = database
    enqueue(db, source_id)
    run = run_once(db, collector=collect_documents(document(), complete=False, continuation={"next": "remaining"}), storage=storage)
    source = db.get(Source, source_id)
    assert run.status == "partial" and run.error_count == 0
    assert source.last_error is None and source.last_success_at is None
    assert "parcial" in source.coverage


def test_resume_rejects_changed_source_configuration_and_preserves_snapshot(database):
    from copy import deepcopy
    db, _, storage, source_id = database
    original_urls = ["https://www.dof.gob.mx/index.php"]
    source = db.get(Source, source_id)
    cursor = {"pending": [{"url": "https://www.dof.gob.mx/nota_detalle.php?codigo=2"}]}
    unchanged_cursor = deepcopy(cursor)
    enqueue(db, source_id)
    partial = run_once(db, collector=collect_documents(document(), complete=False, continuation=cursor), storage=storage)
    snapshot = deepcopy(db.scalar(select(SourceRun).where(SourceRun.job_id == partial.id)).source_snapshot)
    assert cursor == unchanged_cursor  # Caller-owned collector state is never mutated.
    assert partial.continuation["source_config"] == {"kind": "dof", "urls": original_urls}
    assert snapshot["urls"] == original_urls and snapshot["kind"] == "dof"
    source.urls = ["https://www.dof.gob.mx/index.php?edicion=1"]
    db.commit()
    with pytest.raises(ValueError, match="configuración de la fuente cambió"):
        request_job(db, source_id, "operador", DAY, DAY, partial.continuation)
    assert db.scalar(select(SourceRun).where(SourceRun.job_id == partial.id)).source_snapshot == snapshot
    # Restarting the entire requested range is safe: deduplication preserves earlier documents.
    restarted = request_job(db, source_id, "operador", DAY, DAY)
    assert restarted.id != partial.id and restarted.continuation is None
