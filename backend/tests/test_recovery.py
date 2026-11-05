"""Recovery proves publication, evidence and resumable queue survival."""

import json
import sqlite3
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.collectors import Document
from app.jobs import ingest_document, request_job
from app.models import Base, Job, Publication, Source, Version
from app.recovery import create_backup, restore_backup, verify_backup
from app.storage import LocalEvidenceStore


@pytest.fixture
def installation(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'live.db'}")
    Base.metadata.create_all(engine)
    store = LocalEvidenceStore(tmp_path / "evidence")
    with Session(engine) as db:
        source = Source(name="Controlled SIDOF", kind="sidof", urls=[])
        db.add(source)
        db.flush()
        doc = Document(
            "CONTROLLED",
            "https://sidof.segob.gob.mx/notas/docFuente/1",
            "Controlled NOM publication",
            "Original stored text",
            raw=b"evidence",
        )
        ingest_document(db, source, doc, store)
        db.commit()
        request_job(
            db,
            source.id,
            "test",
            date(2026, 10, 1),
            date(2026, 10, 2),
            {
                "source_config": {"kind": "sidof", "urls": []},
                "queue": [{"day": "2026-10-01", "failed": True}],
            },
        )
    yield engine, store
    engine.dispose()


def test_online_snapshot_restores_originals_queue_and_versions(installation, tmp_path):
    engine, store = installation
    manifest = create_backup(engine, store, tmp_path / "backup")
    # A later write must not silently leak into the snapshot.
    with Session(engine) as db:
        db.scalar(select(Publication)).title = "Changed after backup"
        db.commit()
    restore_backup(tmp_path / "backup", tmp_path / "recovered")
    recovered = create_engine(f"sqlite:///{tmp_path / 'recovered/nom.db'}")
    with Session(recovered) as db:
        assert db.scalar(select(Publication)).title == "Controlled NOM publication"
        version = db.scalar(select(Version))
        assert version.content == "Original stored text"
        assert LocalEvidenceStore(tmp_path / "recovered/evidence").read(version.evidence_key) == b"evidence"
        job = db.scalar(select(Job))
        assert job.status == "queued" and job.continuation["queue"][0]["failed"]
    recovered.dispose()
    assert manifest["counts"] == {"publications": 1, "versions": 1, "jobs": 1}


@pytest.mark.parametrize("damage", ["missing", "changed", "database", "manifest", "traversal", "extra"])
def test_damaged_backup_never_publishes_a_restore(installation, tmp_path, damage):
    engine, store = installation
    backup = tmp_path / "backup"
    manifest = create_backup(engine, store, backup)
    key = next(k for k in manifest["files"] if k.startswith("evidence/"))
    if damage == "missing":
        (backup / key).unlink()
    elif damage == "changed":
        (backup / key).write_bytes(b"corrupt")
    elif damage == "database":
        (backup / "nom.db").write_bytes(b"broken sqlite")
    elif damage == "manifest":
        manifest["counts"]["publications"] += 1
    elif damage == "traversal":
        manifest["files"]["../outside"] = "bad"
    else:
        (backup / "unlisted.txt").write_text("unexpected")
    (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        restore_backup(backup, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_backup_and_restore_refuse_existing_destination(installation, tmp_path):
    engine, store = installation
    backup = tmp_path / "backup"
    create_backup(engine, store, backup)
    with pytest.raises(ValueError, match="carpeta nueva"):
        create_backup(engine, store, backup)
    with pytest.raises(ValueError, match="carpeta nueva"):
        restore_backup(backup, backup)
    assert verify_backup(backup)["counts"]["publications"] == 1


def test_backup_refuses_corrupt_live_evidence(installation, tmp_path):
    engine, store = installation
    with Session(engine) as db:
        key = db.scalar(select(Version.evidence_key))
    (store.root / key).write_bytes(b"broken")
    with pytest.raises(ValueError, match="hash"):
        create_backup(engine, store, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()
