"""Commands do not require a running API; run from backend with the virtualenv active."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .jobs import ingest_document, recover_interrupted, request_job, run_once, reevaluate_all
from .models import Audit, CatalogItem, Job, Publication, Source
from .storage import get_storage


INITIAL_SOURCES = (
    ("DOF / SIDOF", "dof", ["https://www.dof.gob.mx/index.php"],
     "Índice diario DOF: descubrimiento de notas y enlaces de edición visibles. Validación en vivo pendiente; no cubre cambios no enlazados ni garantiza todas las ediciones."),
    ("PLATIICA", "platiica", ['https://platiica.economia.gob.mx/normalizacion/nom-014-ener-2025/'],
     "Ficha NOM-014-ENER-2025 del piloto. Seguimiento de texto y enlaces, no descubrimiento global. Descarga por validar en esta instalación."),
    ("SNICE", "snice", ['https://www.snice.gob.mx/cs/avi/snice/seguridad.normatividad.html'],
     "Página de normatividad NOM del piloto. Conserva cambios de texto y enlaces; no consolida automáticamente el Anexo 2.4.1."),
    ("SIDOF · documento de referencia", 'sidof', ['https://sidof.segob.gob.mx/notas/docFuente/5758923'],
     "Documento conocido NOM-014-ENER-2025 del piloto; comprobar descarga y evidencia. No sustituye el descubrimiento diario DOF."),
)


def init_sources(db):
    for name, kind, urls, coverage in INITIAL_SOURCES:
        if db.scalar(select(Source).where(Source.kind == kind)) is None:
            terms = ['NOM-014-ENER-2025'] if kind in ('platiica','sidof') else ['Anexo 2.4.1'] if kind == 'snice' else []
            db.add(Source(name=name, kind=kind, urls=urls, coverage=coverage, active=True,expected_terms=terms))
    db.commit()


def configure_pilot_sources(db):
    """Fill only empty configurations. Never overwrite an administrator's URLs."""
    init_sources(db)
    for name, kind, urls, coverage in INITIAL_SOURCES:
        source = db.scalar(select(Source).where(Source.kind == kind).order_by(Source.id))
        if not source.urls:
            source.urls, source.coverage = urls, coverage
            source.expected_terms = ['NOM-014-ENER-2025'] if kind in ('platiica','sidof') else ['Anexo 2.4.1'] if kind == 'snice' else []
            db.add(Audit(actor='cli-operador',action='configurar_piloto',entity_type='sources',entity_id=str(source.id),after={'urls':urls}))
    db.commit()


def demo(db):
    settings = get_settings()
    if not settings.demo_mode or settings.environment != "development":
        raise ValueError("Demostración requiere ENVIRONMENT=development y DEMO_MODE=true")
    if not settings.database_url.startswith("sqlite:///") or "demo" not in Path(settings.database_url.removeprefix("sqlite:///")).name.lower():
        raise ValueError("Use una base SQLite separada cuyo nombre incluya 'demo', por ejemplo sqlite:///./data/demo.db")
    if db.scalar(select(Publication.id).where(Publication.is_demo.is_(False)).limit(1)) or db.scalar(select(CatalogItem.id).where(CatalogItem.is_demo.is_(False)).limit(1)):
        raise ValueError("La base contiene datos oficiales; use una base de demostración vacía y separada")
    from .collectors import Document
    source = db.scalar(select(Source).where(Source.kind == "demo"))
    if source is None:
        source = Source(name="DEMOSTRACIÓN · muestra sintética", kind="demo", urls=[], active=False,
                        coverage="Contenido sintético local; no es una fuente oficial ni ejecuta consultas de red.")
        db.add(source)
        db.flush()
    family = db.scalar(select(CatalogItem).where(CatalogItem.name == "DEMOSTRACIÓN · Componentes configurables"))
    if family is None:
        family = CatalogItem(kind="familia", name="DEMOSTRACIÓN · Componentes configurables", keywords=["componente de muestra"], is_demo=True)
        db.add(family)
        db.flush()
        subfamily = CatalogItem(kind="subfamilia", parent_id=family.id, name="DEMOSTRACIÓN · Subfamilia configurable", is_demo=True)
        db.add(subfamily)
        db.flush()
        db.add(CatalogItem(kind="producto", parent_id=subfamily.id, name="DEMOSTRACIÓN · Producto ficticio", model="MODELO-DEMO",
                           keywords=["componente de muestra"], is_demo=True))
    db.flush()
    doc = Document(official_id="DEMO-SINTETICO-001", url="", title="DEMOSTRACIÓN · Documento sintético para practicar la revisión",
                   content="Documento ficticio: componente de muestra. No establece obligación, fecha ni disposición oficial.",
                   raw=b"DEMO: documento sintetico local; no corresponde a una publicacion oficial.", media_type="text/plain")
    ingest_document(db, source, doc, get_storage(), is_demo=True)
    db.add(Audit(actor="cli-local", action="cargar_demostracion", entity_type="source", entity_id=str(source.id), after={"is_demo": True}))
    db.commit()


def main():
    parser = argparse.ArgumentParser(description="JE NOM Monitor · herramientas de operación")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Aplicar migraciones y registrar fuentes iniciales sin publicaciones")
    sub.add_parser("init-sources", help="Registrar fuentes iniciales de forma idempotente")
    sub.add_parser("reevaluate", help="Proponer relaciones nuevas con el catálogo actual sin alterar decisiones existentes")
    sub.add_parser("demo", help="Cargar muestra sintética únicamente en base de demostración separada")
    sub.add_parser('configure-pilot', help='Completar fuentes vacías con las URLs verificables del piloto, sin sobrescribir configuración')
    sub.add_parser('pilot-catalog', help='Cargar borradores de familias públicas JE, sin inventar PN, fracción ni responsable')
    verify = sub.add_parser('validate-sources', help='Consulta real, persistencia, integridad y comparación contra IDs esperados')
    verify.add_argument('--start', type=date.fromisoformat, required=True)
    verify.add_argument('--end', type=date.fromisoformat, required=True)
    verify.add_argument('--expected', type=Path, help='JSON: {"dof": ["DOF:..."]}; inventario manual del periodo')
    verify.add_argument('--output', type=Path, default=Path('data/validation.json'))
    verify.add_argument('--max-batches', type=int, default=10)
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
    worker.add_argument('--schedule', action='store_true', help='Atender programación habilitada; exige SCHEDULER_ENABLED=true')
    args = parser.parse_args()
    if args.command == "init-db":
        from alembic import command
        from alembic.config import Config
        root = Path(__file__).resolve().parents[1]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        command.upgrade(config, "head")
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
        elif args.command == 'configure-pilot':
            configure_pilot_sources(db)
            print('URLs del piloto configuradas; se preservaron configuraciones existentes. Programación sin activar.')
        elif args.command == 'pilot-catalog':
            from .pilot import seed_catalog
            print(f'Borradores públicos añadidos: {seed_catalog(db)}. Faltan datos reales y revisión del responsable JE.')
        elif args.command == 'validate-sources':
            from .verification import validate_expected, verify_sources
            if not 1 <= args.max_batches <= 100: parser.error('--max-batches debe estar entre 1 y 100')
            try:
                expected = validate_expected(json.loads(args.expected.read_text(encoding='utf-8')) if args.expected else {})
            except (ValueError, OSError) as exc:
                parser.error(str(exc))
            report = verify_sources(db, get_storage(), args.start, args.end, expected, args.max_batches)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False,indent=2))
            sys.exit(0 if report['passed'] else 2)
        elif args.command == "enqueue":
            continuation = None
            start, end = args.start, args.end
            if args.resume:
                previous = db.get(Job, args.resume)
                if previous is None or previous.source_id != args.source_id or previous.status not in ("partial", "interrupted", "failed"):
                    parser.error("El trabajo a reanudar debe pertenecer a la fuente y estar parcial, interrumpido o fallido")
                continuation, start, end = previous.continuation, previous.period_start, previous.period_end
            job = request_job(db, args.source_id, "cli-operador", start, end, continuation)
            print(f"Trabajo {job.id}: {job.status}; periodo {job.period_start} a {job.period_end}.")
        elif args.command == "worker":
            from .operations import advance_schedule, reevaluate_batch, schedule_due
            if args.schedule and not get_settings().scheduler_enabled:
                parser.error('--schedule requiere SCHEDULER_ENABLED=true; habilite también cada fuente y su fecha inicial')
            if not 1 <= args.interval <= 60:
                parser.error("--interval debe estar entre 1 y 60 segundos")
            try:
                while True:
                    if args.schedule: schedule_due(db)
                    job = run_once(db)
                    advance_schedule(db,job)
                    reevaluation = reevaluate_batch(db)
                    if reevaluation: print(f'Reevaluación: {reevaluation}',flush=True)
                    if job:
                        print(f"{job.id} {job.status}: revisados={job.reviewed_count} nuevos={job.new_count} modificados={job.modified_count} errores={job.error_count}", flush=True)
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
