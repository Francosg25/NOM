"""Verified SQLite snapshots and non-destructive recovery into a new directory.

SQLite's online backup API defines the database snapshot. Evidence is immutable
and written before its database reference, so referenced files can be copied
afterwards even while the monitor continues ingesting new publications.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy.engine import Engine

from .models import utcnow
from .storage import EvidenceStore, check_key


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_database(path: Path) -> dict:
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("La base no supera la comprobación de integridad")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("La base contiene referencias inválidas")
        keys = [
            row[0]
            for row in db.execute("SELECT DISTINCT evidence_key FROM versions WHERE evidence_key IS NOT NULL")
        ]
        counts = {
            "publications": db.execute("SELECT count(*) FROM publications").fetchone()[0],
            "versions": db.execute("SELECT count(*) FROM versions").fetchone()[0],
            "jobs": db.execute("SELECT count(*) FROM jobs").fetchone()[0],
        }
        # Publication.current_version_id is deliberately not a DB foreign key.
        if db.execute(
            "SELECT p.id FROM publications p LEFT JOIN versions v "
            "ON v.id=p.current_version_id AND v.publication_id=p.id "
            "WHERE p.current_version_id IS NOT NULL AND v.id IS NULL"
        ).fetchone():
            raise ValueError("Una publicación referencia una versión inválida")
    return {"keys": sorted(check_key(key) for key in keys), "counts": counts}


def _new_destination(destination: Path) -> Path:
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("El destino debe ser una carpeta nueva; no se sobrescriben datos")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def create_backup(engine: Engine, storage: EvidenceStore, destination: Path) -> dict:
    if engine.dialect.name != "sqlite":
        raise ValueError(
            "Este respaldo es para SQLite; PostgreSQL requiere pg_dump y su procedimiento propio"
        )
    destination = _new_destination(destination)
    with tempfile.TemporaryDirectory(prefix=".nom-backup-", dir=destination.parent) as temp:
        stage = Path(temp)
        database = stage / "nom.db"
        with engine.connect() as connection, sqlite3.connect(database) as target:
            connection.connection.driver_connection.backup(target)
        snapshot = inspect_database(database)
        files = {"nom.db": digest(database)}
        for key in snapshot["keys"]:
            raw = storage.read(key)
            expected = Path(key).stem
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("La evidencia no coincide con su hash: " + key)
            path = stage / "evidence" / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            files["evidence/" + key] = expected
        manifest = {
            "format": 1,
            "created_at": utcnow().isoformat(),
            "counts": snapshot["counts"],
            "files": files,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        # Rename on the same filesystem publishes only a complete snapshot.
        stage.rename(destination)
    return manifest


def verify_backup(source: Path) -> dict:
    source = source.resolve()
    manifest_path = source / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("El respaldo no admite enlaces simbólicos")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("Formato de respaldo no compatible")
    files = manifest["files"]
    actual = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != {*files, "manifest.json"}:
        raise ValueError("El respaldo contiene archivos no inventariados o ausentes")
    for name, expected in files.items():
        if name != "nom.db":
            if not name.startswith("evidence/"):
                raise ValueError("Ruta no válida en el respaldo")
            check_key(name.removeprefix("evidence/"))
        path = source / name
        if any(p.is_symlink() for p in [path, *path.parents] if p != source.parent):
            raise ValueError("El respaldo no admite enlaces simbólicos")
        if not path.is_file() or digest(path) != expected:
            raise ValueError("Archivo ausente o alterado: " + name)
    if "nom.db" not in files:
        raise ValueError("Falta la base de datos del respaldo")
    snapshot = inspect_database(source / "nom.db")
    expected_files = {"nom.db", *("evidence/" + key for key in snapshot["keys"])}
    if set(files) != expected_files or manifest.get("counts") != snapshot["counts"]:
        raise ValueError("El inventario del respaldo no coincide con su base")
    # The content-addressed filename is a second check, independent of manifest.
    for key in snapshot["keys"]:
        if files["evidence/" + key] != Path(key).stem:
            raise ValueError("Hash de evidencia inválido")
    return manifest


def restore_backup(source: Path, destination: Path) -> dict:
    destination = _new_destination(destination)
    # Copy first, then validate the copy; a concurrently changed source cannot
    # invalidate a successful check before the restored directory is published.
    with tempfile.TemporaryDirectory(prefix=".nom-restore-", dir=destination.parent) as temp:
        stage = Path(temp) / "restored"
        shutil.copytree(source, stage, symlinks=True)
        manifest = verify_backup(stage)
        stage.rename(destination)
    return manifest
