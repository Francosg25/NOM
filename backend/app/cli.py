"""Commands do not require a running API; run from backend with the virtualenv active."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .jobs import ingest_document, request_job, run_once, reevaluate_all
from .models import Audit, CatalogItem, Job, Publication, Source, utcnow
from .collectors.sidof import API_BASE
from .storage import get_storage


INITIAL_SOURCES = (
    (
        "SIDOF · publicaciones diarias",
        "sidof",
        [API_BASE],
        "SIDOF diario: ediciones y notas por fecha. Selecciona NOM y reglas de comercio exterior; conserva el detalle JSON oficial. No determina aplicabilidad a productos.",
    ),
)


def init_sources(db):
    for name, kind, urls, coverage in INITIAL_SOURCES:
        if db.scalar(select(Source).where(Source.kind == kind)) is None:
            terms = (
                ["NOM-014-ENER-2025"] if kind == "platiica" else ["Anexo 2.4.1"] if kind == "snice" else []
            )
            db.add(
                Source(
                    name=name,
                    kind=kind,
                    urls=urls,
                    coverage=coverage,
                    active=True,
                    expected_terms=terms,
                    frequency_hours=1 if kind == "sidof" else 24,
                )
            )
    db.commit()
    upgrade_sidof_source(db)
    retire_legacy_sources(db)


def retire_legacy_sources(db):
    """SIDOF-only portal; keep historical documents and jobs for traceability."""
    for source in db.scalars(select(Source).where(Source.kind != "sidof", Source.kind != "demo")):
        if source.active or source.schedule_enabled:
            source.active = False
            source.schedule_enabled = False
            source.next_due_at = None
            db.add(
                Audit(
                    actor="sistema",
                    action="retirar_fuente",
                    entity_type="sources",
                    entity_id=str(source.id),
                    after={"active": False, "preserved_publications": True},
                )
            )
        for job in db.scalars(select(Job).where(Job.source_id == source.id, Job.status == "queued")):
            job.status = "cancelled"
            job.active_key = None
            job.finished_at = utcnow()
            job.error = "Fuente retirada: el portal utiliza únicamente SIDOF."
    db.commit()


def upgrade_sidof_source(db):
    """Upgrade only the unmodified pilot reference; retain records and user choices."""
    source = db.scalar(select(Source).where(Source.kind == "sidof").order_by(Source.id))
    if (
        not source
        or source.urls != ["https://sidof.segob.gob.mx/notas/docFuente/5758923"]
        or source.expected_terms != ["NOM-014-ENER-2025"]
    ):
        return False
    if db.scalar(select(Job.id).where(Job.source_id == source.id, Job.active_key.is_not(None))):
        return False
    before = {
        "urls": source.urls,
        "expected_terms": source.expected_terms,
        "schedule_start": str(source.schedule_start),
    }
    source.urls, source.expected_terms = [API_BASE], []
    source.name = "SIDOF · publicaciones diarias"
    source.coverage = INITIAL_SOURCES[-1][3]
    lookback = utcnow().astimezone(ZoneInfo("America/Mexico_City")).date() - timedelta(days=6)
    source.schedule_start = min(source.schedule_start, lookback) if source.schedule_start else None
    if source.frequency_hours == 24:
        source.frequency_hours = 1
    source.next_due_at = None
    source.last_success_at, source.last_error = None, None
    db.add(
        Audit(
            actor="sistema",
            action="activar_sidof_diario",
            entity_type="sources",
            entity_id=str(source.id),
            before=before,
            after={"urls": source.urls, "expected_terms": [], "preserved_publications": True},
        )
    )
    db.commit()
    return True


def configure_pilot_sources(db):
    """Fill only empty configurations. Never overwrite an administrator's URLs."""
    init_sources(db)
    for name, kind, urls, coverage in INITIAL_SOURCES:
        source = db.scalar(select(Source).where(Source.kind == kind).order_by(Source.id))
        if not source.urls:
            source.urls, source.coverage = urls, coverage
            source.expected_terms = (
                ["NOM-014-ENER-2025"] if kind == "platiica" else ["Anexo 2.4.1"] if kind == "snice" else []
            )
            db.add(
                Audit(
                    actor="cli-operador",
                    action="configurar_piloto",
                    entity_type="sources",
                    entity_id=str(source.id),
                    after={"urls": urls},
                )
            )
    db.commit()


def demo(db):
    settings = get_settings()
    if not settings.demo_mode or settings.environment != "development":
        raise ValueError("Demostración requiere ENVIRONMENT=development y DEMO_MODE=true")
    if (
        not settings.database_url.startswith("sqlite:///")
        or "demo" not in Path(settings.database_url.removeprefix("sqlite:///")).name.lower()
    ):
        raise ValueError(
            "Use una base SQLite separada cuyo nombre incluya 'demo', por ejemplo sqlite:///./data/demo.db"
        )
    if db.scalar(select(Publication.id).where(Publication.is_demo.is_(False)).limit(1)) or db.scalar(
        select(CatalogItem.id).where(CatalogItem.is_demo.is_(False)).limit(1)
    ):
        raise ValueError("La base contiene datos oficiales; use una base de demostración vacía y separada")
    from .collectors import Document

    source = db.scalar(select(Source).where(Source.kind == "demo"))
    if source is None:
        source = Source(
            name="DEMOSTRACIÓN · muestra sintética",
            kind="demo",
            urls=[],
            active=False,
            coverage="Contenido sintético local; no es una fuente oficial ni ejecuta consultas de red.",
        )
        db.add(source)
        db.flush()
    family = db.scalar(
        select(CatalogItem).where(CatalogItem.name == "DEMOSTRACIÓN · Componentes configurables")
    )
    if family is None:
        family = CatalogItem(
            kind="familia",
            name="DEMOSTRACIÓN · Componentes configurables",
            keywords=["componente de muestra"],
            is_demo=True,
        )
        db.add(family)
        db.flush()
        subfamily = CatalogItem(
            kind="subfamilia",
            parent_id=family.id,
            name="DEMOSTRACIÓN · Subfamilia configurable",
            is_demo=True,
        )
        db.add(subfamily)
        db.flush()
        db.add(
            CatalogItem(
                kind="producto",
                parent_id=subfamily.id,
                name="DEMOSTRACIÓN · Producto ficticio",
                model="MODELO-DEMO",
                keywords=["componente de muestra"],
                is_demo=True,
            )
        )
    db.flush()
    doc = Document(
        official_id="DEMO-SINTETICO-001",
        url="",
        title="DEMOSTRACIÓN · Documento sintético para practicar la revisión",
        content="Documento ficticio: componente de muestra. No establece obligación, fecha ni disposición oficial.",
        raw=b"DEMO: documento sintetico local; no corresponde a una publicacion oficial.",
        media_type="text/plain",
    )
    ingest_document(db, source, doc, get_storage(), is_demo=True)
    db.add(
        Audit(
            actor="cli-local",
            action="cargar_demostracion",
            entity_type="source",
            entity_id=str(source.id),
            after={"is_demo": True},
        )
    )
    db.commit()


def apply_migrations():
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")


def main():
    parser = argparse.ArgumentParser(description="JE NOM Monitor · herramientas de operación")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Aplicar migraciones y registrar fuentes iniciales sin publicaciones")
    sub.add_parser("init-sources", help="Registrar fuentes iniciales de forma idempotente")
    sub.add_parser(
        "reevaluate",
        help="Proponer relaciones nuevas con el catálogo actual sin alterar decisiones existentes",
    )
    sub.add_parser("demo", help="Cargar muestra sintética únicamente en base de demostración separada")
    backup = sub.add_parser("backup", help="Respaldar SQLite y evidencia en una carpeta nueva con hashes")
    backup.add_argument("--destination", type=Path, required=True)
    restore = sub.add_parser(
        "restore", help="Verificar y restaurar en una carpeta NUEVA; no sustituye la instalación activa"
    )
    restore.add_argument("--source", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    sub.add_parser(
        "configure-pilot",
        help="Completar fuentes vacías con las URLs verificables del piloto, sin sobrescribir configuración",
    )
    sub.add_parser(
        "pilot-catalog",
        help="Cargar borradores de familias públicas JE, sin inventar PN, fracción ni responsable",
    )
    verify = sub.add_parser(
        "validate-sources", help="Consulta real, persistencia, integridad y comparación contra IDs esperados"
    )
    verify.add_argument("--start", type=date.fromisoformat, required=True)
    verify.add_argument("--end", type=date.fromisoformat, required=True)
    verify.add_argument(
        "--expected", type=Path, help='JSON: {"dof": ["DOF:..."]}; inventario manual del periodo'
    )
    verify.add_argument("--output", type=Path, default=Path("data/validation.json"))
    verify.add_argument("--max-batches", type=int, default=10)
    enq = sub.add_parser("enqueue", help="Solicitar una revisión persistente")
    enq.add_argument("source_id", type=int)
    enq.add_argument("--start", type=date.fromisoformat)
    enq.add_argument("--end", type=date.fromisoformat)
    enq.add_argument("--resume", help="ID de un trabajo parcial/interrumpido/fallido que debe reanudarse")
    worker = sub.add_parser("worker", help="Procesar cola persistente; no programa consultas por sí mismo")
    mode = worker.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Ejecutar un trabajo y terminar")
    mode.add_argument("--poll", action="store_true", help="Atender la cola hasta recibir una señal de parada")
    worker.add_argument("--interval", type=int, default=3)
    worker.add_argument(
        "--schedule",
        action="store_true",
        help="Atender programación habilitada; exige SCHEDULER_ENABLED=true",
    )
    args = parser.parse_args()
    if args.command in ("backup", "restore"):
        from .recovery import create_backup, restore_backup
        from .db import engine

        try:
            result = (
                create_backup(engine, get_storage(), args.destination)
                if args.command == "backup"
                else restore_backup(args.source, args.destination)
            )
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        print(json.dumps({"status": "ok", "counts": result["counts"]}, ensure_ascii=False))
        return
    if args.command == "init-db":
        apply_migrations()
    with SessionLocal() as db:
        if args.command in ("init-db", "init-sources"):
            init_sources(db)
            print("Fuentes registradas; ninguna publicación se ha inventado ni descargado.")
        elif args.command == "reevaluate":
            count = reevaluate_all(db, "cli-operador")
            db.commit()
            print(f"Nuevas propuestas: {count}; decisiones existentes conservadas.")
        elif args.command == "demo":
            demo(db)
            print("Muestra sintética cargada en base de demostración separada.")
        elif args.command == "configure-pilot":
            configure_pilot_sources(db)
            print(
                "URLs del piloto configuradas; se preservaron configuraciones existentes. Programación sin activar."
            )
        elif args.command == "pilot-catalog":
            from .pilot import seed_catalog

            print(
                f"Borradores públicos añadidos: {seed_catalog(db)}. Faltan datos reales y revisión del responsable JE."
            )
        elif args.command == "validate-sources":
            from .verification import validate_expected, verify_sources

            if not 1 <= args.max_batches <= 100:
                parser.error("--max-batches debe estar entre 1 y 100")
            try:
                expected = validate_expected(
                    json.loads(args.expected.read_text(encoding="utf-8")) if args.expected else {}
                )
            except (ValueError, OSError) as exc:
                parser.error(str(exc))
            report = verify_sources(db, get_storage(), args.start, args.end, expected, args.max_batches)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            sys.exit(0 if report["passed"] else 2)
        elif args.command == "enqueue":
            continuation = None
            start, end = args.start, args.end
            if args.resume:
                previous = db.get(Job, args.resume)
                if (
                    previous is None
                    or previous.source_id != args.source_id
                    or previous.status not in ("partial", "interrupted", "failed")
                ):
                    parser.error(
                        "El trabajo a reanudar debe pertenecer a la fuente y estar parcial, interrumpido o fallido"
                    )
                continuation, start, end = previous.continuation, previous.period_start, previous.period_end
            job = request_job(db, args.source_id, "cli-operador", start, end, continuation)
            print(f"Trabajo {job.id}: {job.status}; periodo {job.period_start} a {job.period_end}.")
        elif args.command == "worker":
            from .operations import advance_schedule, reevaluate_batch, schedule_due

            if args.schedule and not get_settings().scheduler_enabled:
                parser.error(
                    "--schedule requiere SCHEDULER_ENABLED=true; habilite también cada fuente y su fecha inicial"
                )
            if not 1 <= args.interval <= 60:
                parser.error("--interval debe estar entre 1 y 60 segundos")
            try:
                while True:
                    from .observability import record_pulse

                    record_pulse(db, name="worker")
                    if args.schedule:
                        schedule_due(db)
                    job = run_once(db)
                    advance_schedule(db, job)
                    record_pulse(db, name="worker")
                    reevaluation = reevaluate_batch(db)
                    if reevaluation:
                        print(f"Reevaluación: {reevaluation}", flush=True)
                    if job:
                        print(
                            f"{job.id} {job.status}: revisados={job.reviewed_count} nuevos={job.new_count} modificados={job.modified_count} errores={job.error_count}",
                            flush=True,
                        )
                    if args.once:
                        if job is None:
                            print("No hay trabajos pendientes.")
                        elif job.status == "partial":
                            sys.exit(2)
                        elif job.status in ("failed", "interrupted"):
                            sys.exit(1)
                        break
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("Worker detenido; un trabajo interrumpido se detectará por su arrendamiento vencido.")


if __name__ == "__main__":
    main()
