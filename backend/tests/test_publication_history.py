"""Controlled archive records: dates, exact references, lazy bodies and durable indexing."""

from datetime import date
import re

import pytest
import test_api

from sqlalchemy import event, select

from app.collectors import Document
from app.jobs import ingest_document
from app.models import Audit, Job, Publication, PublicationHistoryIndex, Source, Version
from app.publication_history import index_history_batch, pending_count, primary_codes, reference_matches
from test_api import ADMIN, READER


@pytest.fixture
def api(tmp_path, monkeypatch):
    yield from test_api.api.__wrapped__(tmp_path, monkeypatch)


CODE = "NOM-016-ENER-2016"


def test_migration_preserves_existing_records_and_notification_cursors(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.orm import Session
    from app import db as database
    from app.models import NotificationCursor

    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    monkeypatch.setattr(database, "engine", engine)
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "fa91c2d6e842")
        with Session(engine) as db:
            source = Source(name="Conservar fuente", kind="sidof", urls=[])
            db.add(source)
            db.flush()
            db.add(
                Publication(
                    source_id=source.id, official_id="PRESERVE", title=CODE, url="https://sidof.segob.gob.mx/"
                )
            )
            db.add(NotificationCursor(name="preserve", last_event_id=42))
            db.commit()
        command.upgrade(config, "head")
        command.check(config)
        assert "publication_history_index" in inspect(engine).get_table_names()
        with Session(engine) as db:
            assert db.get(NotificationCursor, "preserve").last_event_id == 42
            assert db.scalar(select(Publication.official_id)) == "PRESERVE"
        command.downgrade(config, "fa91c2d6e842")
        assert "publication_history_index" not in inspect(engine).get_table_names()
        with Session(engine) as db:
            assert db.get(NotificationCursor, "preserve").last_event_id == 42
    finally:
        engine.dispose()


def seed_history(sessions):
    with sessions() as db:
        sidof = Source(name="SIDOF controlado", kind="sidof", urls=["https://sidof.segob.gob.mx/dof/sidof"])
        catalog = Source(name="PLATIICA controlada", kind="platiica_catalog", urls=[])
        db.add_all([sidof, catalog])
        db.flush()
        anchor = Publication(
            source_id=catalog.id,
            official_id=f"PLATIICA:{CODE}",
            title=f"{CODE} · Ficha controlada",
            url="https://platiica.economia.gob.mx/",
            kind="norma_vigente",
        )
        db.add(anchor)
        db.flush()
        rows = []
        for number, (title, body, published, demo) in enumerate(
            [
                (f"PROY-{CODE} · Proyecto controlado", "Texto de prueba", date(2015, 1, 2), False),
                (
                    "Aviso controlado",
                    "La referencia NOM–016 – ENER – 2016 aparece en el texto.",
                    date(2020, 2, 29),
                    False,
                ),
                ("NOM-016-ENER-2015 · Otro año", "Sin referencia al año buscado.", date(2020, 2, 29), False),
                (
                    "NOM-EM-016-ENER-2016 · Otra clave",
                    "Sin referencia a la norma ordinaria.",
                    date(2020, 3, 1),
                    False,
                ),
                (f"{CODE} · Muestra demo", "Texto de prueba", date(2020, 2, 29), True),
                (f"{CODE} · Fecha sin confirmar", "Texto de prueba", None, False),
            ],
            1,
        ):
            pub = Publication(
                source_id=sidof.id,
                official_id=f"CONTROLLED:{number}",
                title=title,
                url="https://sidof.segob.gob.mx/",
                kind="aviso",
                published_on=published,
                is_demo=demo,
            )
            db.add(pub)
            db.flush()
            version = Version(
                publication_id=pub.id,
                sequence=1,
                content=body,
                content_hash=f"controlled-{number}",
                media_type="text/plain",
            )
            db.add(version)
            db.flush()
            pub.current_version_id = version.id
            rows.append(pub.id)
        db.commit()
        return anchor.id, rows, sidof.id


def test_reference_parser_preserves_year_emergency_issuer_and_original_context():
    value = "Mención: PROY-NOM‐016‐ENER‐2016, NOM-EM-016-ENER-2016 y NOM-051-SCFI/SSA1-2010."
    matches = dict(reference_matches(value))
    assert set(matches) == {CODE, "NOM-EM-016-ENER-2016", "NOM-051-SCFI/SSA1-2010"}
    assert "PROY-NOM‐016‐ENER‐2016" in matches[CODE]
    assert not list(reference_matches("NOM-016-ENER-20160 o ANOM-016-ENER-2016"))


def test_existing_records_index_in_small_batches_and_history_keeps_exact_evidence(api):
    client, sessions, _, _ = api
    anchor, rows, _ = seed_history(sessions)
    with sessions() as db:
        assert pending_count(db) == 5
        assert index_history_batch(db, limit=1) == 1
        assert pending_count(db) == 4
        while index_history_batch(db):
            pass
        assert pending_count(db) == 0
    statements = []
    engine = sessions.kw["bind"]

    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", track)
    try:
        result = client.get(f"/api/history/publications/{anchor}", headers=READER).json()
    finally:
        event.remove(engine, "before_cursor_execute", track)
    assert [item["id"] for item in result["items"]] == [rows[0], rows[1], rows[5]]
    assert result["items"][1]["reference_location"] == "text"
    assert "NOM–016 – ENER – 2016" in result["items"][1]["reference_snippet"]
    assert result["items"][0]["excerpt"] == ""
    assert not any(re.search(r"\bversions\.content\b", sql.lower()) for sql in statements)
    assert (
        client.get(
            f"/api/history/publications/{anchor}?norm_code=NOM-016-ENER-2015", headers=READER
        ).status_code
        == 422
    )
    assert client.get("/api/history/publications/99999", headers=READER).status_code == 404


def test_new_versions_replace_old_references_without_changing_other_publications(api):
    client, sessions, _, store = api
    anchor, _, source_id = seed_history(sessions)
    with sessions() as db:
        source = db.get(Source, source_id)
        document = Document(
            "CHANGING",
            "https://sidof.segob.gob.mx/",
            "Aviso controlado",
            f"Referencia {CODE}",
            date(2021, 1, 1),
            raw=b"first",
        )
        ingest_document(db, source, document, store)
        db.commit()
        pub = db.scalar(select(Publication).where(Publication.official_id == "CHANGING"))
        assert db.get(PublicationHistoryIndex, pub.id).version_id == pub.current_version_id
        first = client.get(f"/api/history/publications/{anchor}", headers=READER).json()
        assert pub.id in [item["id"] for item in first["items"]]
        document.content = "Ahora menciona NOM-016-ENER-2015"
        document.raw = b"second"
        ingest_document(db, source, document, store)
        db.commit()
        second = client.get(f"/api/history/publications/{anchor}", headers=READER).json()
        assert pub.id not in [item["id"] for item in second["items"]]


def test_date_range_is_inclusive_with_stable_order_and_keeps_catalog_separate(api):
    client, sessions, _, _ = api
    anchor, rows, _ = seed_history(sessions)
    result = client.get(
        "/api/publications?source_kind=sidof&published_since=2020-02-29&published_until=2020-02-29&direction=asc&sort=published&page_size=1",
        headers=READER,
    ).json()
    assert result["total"] == 2 and result["items"][0]["id"] == rows[1]
    assert result["items"][0]["norm_codes"] == []  # A body citation does not identify the record.
    second = client.get(
        "/api/publications?source_kind=sidof&published_since=2020-02-29&published_until=2020-02-29&direction=asc&sort=published&page_size=1&page=2",
        headers=READER,
    ).json()
    assert second["items"][0]["id"] == rows[2]
    assert (
        client.get(
            "/api/publications?published_since=2021-01-01&published_until=2020-01-01", headers=READER
        ).status_code
        == 422
    )
    assert client.get("/api/publications?direction=invalid", headers=READER).status_code == 422
    catalog = client.get("/api/publications?source_kind=platiica_catalog", headers=READER).json()
    assert catalog["total"] == 1 and catalog["items"][0]["id"] == anchor


def test_coverage_counts_observed_days_without_claiming_all_days_between_bounds(api):
    client, sessions, _, _ = api
    _, _, source_id = seed_history(sessions)
    with sessions() as db:
        job = Job(
            id="controlled-check",
            source_id=source_id,
            requested_by="test",
            period_start=date(2020, 1, 1),
            period_end=date(2020, 12, 31),
            status="partial",
        )
        db.add(job)
        db.flush()
        for day, unresolved, absent in [
            ("2020-01-01", [], False),
            ("2020-01-02", ["DOF:missing"], False),
            ("2020-01-03", [], True),
        ]:
            db.add(
                Audit(
                    actor="test",
                    action="revisar_indice_diario",
                    entity_type="job",
                    entity_id=job.id,
                    after={"day": day, "unresolved": unresolved, "declared_no_publication": absent},
                )
            )
        db.commit()
    result = client.get("/api/history/coverage?year=2020", headers=READER).json()
    assert result["total"] == 5 and result["verified_days"] == 2
    assert result["incomplete_days"] == 1 and result["no_publication_days"] == 1
    assert result["years"] == [{"year": 2020, "count": 3}, {"year": 2015, "count": 1}]
    assert (
        client.get("/api/history/coverage?year=2020&is_demo=true", headers=READER).json()["verified_days"]
        == 0
    )


def test_history_paginates_twenty_five_records_and_empty_identity_is_not_guessed(api):
    client, sessions, _, _ = api
    anchor, _, source_id = seed_history(sessions)
    with sessions() as db:
        for index in range(27):
            pub = Publication(
                source_id=source_id,
                official_id=f"PAGED:{index}",
                title=f"{CODE} · prueba {index}",
                url="https://sidof.segob.gob.mx/",
                published_on=date(2020, 1, 1),
            )
            db.add(pub)
            db.flush()
            version = Version(
                publication_id=pub.id,
                sequence=1,
                content="",
                content_hash=f"page-{index}",
                media_type="text/plain",
            )
            db.add(version)
            db.flush()
            pub.current_version_id = version.id
        db.commit()
        while index_history_batch(db):
            pass
    page1 = client.get(f"/api/history/publications/{anchor}", headers=READER).json()
    page2 = client.get(f"/api/history/publications/{anchor}?page=2", headers=READER).json()
    assert page1["total"] == 30 and len(page1["items"]) == 25 and len(page2["items"]) == 5
    assert not {item["id"] for item in page1["items"]} & {item["id"] for item in page2["items"]}
    assert primary_codes(type("P", (), {"title": "Aviso", "official_id": "DOF:123"})()) == []


def test_historical_import_uses_existing_role_and_period_guards(api):
    client, sessions, _, _ = api
    _, _, source_id = seed_history(sessions)
    body = {"source_id": source_id, "period_start": "2020-01-01", "period_end": "2020-01-31"}
    assert client.post("/api/jobs", headers=READER, json=body).status_code == 403
    assert (
        client.post("/api/jobs", headers=ADMIN, json={**body, "period_end": "2021-12-31"}).status_code == 422
    )
    response = client.post("/api/jobs", headers=ADMIN, json=body)
    assert response.status_code == 202 and response.json()["status"] == "queued"
