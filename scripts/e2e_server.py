"""Isolated real API for browser tests. Never reads/writes the user's database."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def run():
    with tempfile.TemporaryDirectory(prefix='nom-e2e-') as temp:
        os.environ.update(ENVIRONMENT='test', AUTH_MODE='portal', DEV_AUTH_ENABLED='false',
            MONITOR_ENABLED='false', SCHEDULER_ENABLED='false', DEMO_MODE='false',
            DATABASE_URL='sqlite:///' + str(Path(temp) / 'nom.db'), STORAGE_BACKEND='local',
            STORAGE_PATH=str(Path(temp) / 'evidence'), FRONTEND_DIST=str(ROOT / 'frontend/dist'))
        from app.cli import apply_migrations
        from app.db import SessionLocal
        from app.collectors import Document
        from app.jobs import ingest_document
        from app.models import Source
        from app.storage import get_storage
        from datetime import date
        import uvicorn
        apply_migrations()
        with SessionLocal() as db:
            source = Source(name='SIDOF · publicaciones diarias', kind='sidof',
                            urls=['https://sidof.segob.gob.mx/dof/sidof'],
                            last_error='2026-10-01: HTTP 404 (controlled fixture)')
            db.add(source)
            db.flush()
            for number, title in enumerate(('Controlled NOM motor', 'Controlled NOM pump'), 1):
                ingest_document(db, source, Document('CONTROLLED-' + str(number),
                    'https://sidof.segob.gob.mx/notas/docFuente/' + str(number),
                    title, 'Controlled sample text; this is not an official NOM.',
                    date(2026, 10, number), kind='proyecto', raw=b'controlled original'), get_storage())
            db.commit()
        uvicorn.run('app.main:app', host='127.0.0.1', port=8765)


if __name__ == '__main__':
    run()
