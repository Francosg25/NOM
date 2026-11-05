"""Repeatable live acceptance check. No synthetic network response is injected."""

import hashlib
from datetime import date, timedelta
from sqlalchemy import func, select
from .jobs import request_job, run_once
from .models import Audit, Publication, Source, Version, utcnow
from .collectors.sidof import is_daily


def validate_expected(expected):
    if not isinstance(expected, dict) or any(
        k not in {"dof", "sidof", "platiica", "snice"} for k in expected
    ):
        raise ValueError("Inventario esperado: objeto JSON con claves dof, sidof, platiica o snice")
    if any(
        not isinstance(ids, list) or any(not isinstance(id, str) or not id.strip() for id in ids)
        for ids in expected.values()
    ):
        raise ValueError(
            "Cada inventario debe ser una lista de identificadores no vacíos; use [] para un día revisado sin publicaciones"
        )
    return expected


def verify_sources(db, storage, start, end, expected=None, max_batches=10):
    expected = validate_expected({} if expected is None else expected)
    if end < start or not 1 <= max_batches <= 100:
        raise ValueError("Periodo inválido o número de lotes fuera de 1 a 100")
    report = {
        "generated_at": utcnow().isoformat(),
        "period_start": str(start),
        "period_end": str(end),
        "passed": True,
        "coverage_verified": False,
        "sources": [],
    }
    for source in db.scalars(select(Source).where(Source.active.is_(True)).order_by(Source.id)).all():
        entry = {
            "source": source.name,
            "kind": source.kind,
            "urls": source.urls,
            "jobs": [],
            "passed": False,
            "evidence": [],
            "errors": [],
            "expected_ids": expected.get(source.kind),
            "daily_discovery": source.kind == "dof" or source.kind == "sidof" and is_daily(source.urls),
        }
        before = db.scalar(
            select(func.count(Version.id)).join(Publication).where(Publication.source_id == source.id)
        )
        continuation = None
        try:
            for _ in range(max_batches):
                job = request_job(db, source.id, "validation", start, end, continuation)
                job = run_once(db, storage=storage, job_id=job.id)
                if job is None:
                    raise ValueError(
                        "El trabajo ya fue tomado por otro consumidor; validar en una base aislada"
                    )
                entry["jobs"].append(
                    {
                        "id": job.id,
                        "status": job.status,
                        "new": job.new_count,
                        "modified": job.modified_count,
                        "reviewed": job.reviewed_count,
                    }
                )
                if job.error:
                    entry["errors"].append(job.error)
                continuation = job.continuation
                pending_days = (job.continuation or {}).get("queue", [])
                if (
                    job.status != "partial"
                    or job.error_count
                    and not any(not item.get("failed") for item in pending_days)
                ):
                    break
            entry["passed"] = job.status == "succeeded" and not entry["errors"]
            # Historical rows cannot stand in for documents observed in this run.
            # Observations are committed with the corresponding publication/version,
            # including unchanged documents, so a repeat is independently verifiable.
            job_ids = [j["id"] for j in entry["jobs"]]
            observations = db.scalars(
                select(Audit)
                .where(
                    Audit.entity_type == "job",
                    Audit.entity_id.in_(job_ids),
                    Audit.action == "observar_documento",
                )
                .order_by(Audit.id)
            ).all()
            observed = {o.after["official_id"]: o.after for o in observations}
            entry["observed_ids"] = sorted(observed)
            entry["unknown_publication_dates"] = sorted(
                id for id, o in observed.items() if not o["published_on"]
            )
            # Inventories refer to explicit publication dates, never detection dates.
            ids = sorted(
                id
                for id, o in observed.items()
                if o["published_on"] and start <= date.fromisoformat(o["published_on"]) <= end
            )
            entry["observed_ids_in_period"] = ids
            checks = db.scalars(
                select(Audit)
                .where(
                    Audit.entity_type == "job",
                    Audit.entity_id.in_(job_ids),
                    Audit.action == "revisar_indice_diario",
                )
                .order_by(Audit.id)
            ).all()
            entry["index_checks"] = [check.after for check in checks]
            entry["unresolved_ids"] = sorted(
                {item["id"] for check in checks for item in check.after.get("unresolved", [])}
            )
            if source.kind == "sidof" and is_daily(source.urls):
                checked_days = {check.after["day"] for check in checks}
                entry["missing_index_dates"] = sorted(
                    str(start + timedelta(days=i))
                    for i in range((end - start).days + 1)
                    if str(start + timedelta(days=i)) not in checked_days
                )
                if entry["missing_index_dates"]:
                    entry["passed"] = False
                    entry["errors"].append("Hay fechas SIDOF sin índice diario verificado en esta consulta")
            if not entry["daily_discovery"] and not observed:
                entry["passed"] = False
                entry["errors"].append("La consulta no observó ningún documento configurado")
            if entry["daily_discovery"] and entry["unknown_publication_dates"]:
                entry["passed"] = False
                entry["errors"].append("Hay notas DOF sin fecha de publicación verificable")
            if entry["expected_ids"] is not None:
                wanted = set(entry["expected_ids"])
                entry["missing_ids"] = sorted(wanted - set(ids))
                entry["extra_ids"] = sorted(set(ids) - wanted)
                entry["inventory_matches"] = not entry["missing_ids"] and not entry["extra_ids"]
                entry["passed"] &= entry["inventory_matches"]
            for official_id, observation in observed.items():
                version = db.get(Version, observation["version_id"])
                if not version or not version.evidence_key:
                    entry["passed"] = False
                    entry["errors"].append(f"Evidencia ausente: {official_id}")
                    continue
                raw = storage.read(version.evidence_key)
                digest = hashlib.sha256(raw).hexdigest()
                intact = version.evidence_key.endswith(digest + ".bin")
                entry["passed"] &= intact and not bool(version.processing_note)
                entry["evidence"].append(
                    {
                        "official_id": official_id,
                        "version_id": version.id,
                        "sha256": digest,
                        "bytes": len(raw),
                        "integrity": intact,
                        "processing_note": version.processing_note,
                    }
                )
            entry["versions_added"] = (
                db.scalar(
                    select(func.count(Version.id)).join(Publication).where(Publication.source_id == source.id)
                )
                - before
            )
        except Exception as exc:
            db.rollback()
            entry["errors"].append(str(exc)[:1500])
            entry["passed"] = False
        report["sources"].append(entry)
        report["passed"] &= bool(entry["passed"])
    report["passed"] &= bool(report["sources"])
    dof = [s for s in report["sources"] if s["daily_discovery"]]
    report["coverage_verified"] = bool(dof) and all(
        s["passed"] and s.get("inventory_matches", False) and not s.get("unresolved_ids") for s in dof
    )
    report["technical_passed"] = bool(report["passed"])
    report["passed"] = report["technical_passed"] and report["coverage_verified"]
    report["note"] = (
        "Una descarga válida no acredita cobertura integral ni aplicabilidad; contrastar inventario DOF y revisar catálogo con responsable JE."
    )
    return report
