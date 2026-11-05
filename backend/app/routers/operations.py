"""Infrastructure readiness is separate from upstream SIDOF availability."""

from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..observability import operational_status

router = APIRouter(prefix="/api", tags=["operations"])


@router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    settings = get_settings()
    codes = []
    try:
        db.execute(text("SELECT 1"))
        status = operational_status(db, settings)
        if "WORKER_UNAVAILABLE" in status["codes"]:
            codes.append("WORKER_UNAVAILABLE")
    except Exception:
        codes.append("DATABASE_UNAVAILABLE")
    if settings.storage_backend == "local":
        try:
            root = Path(settings.storage_path)
            root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=root) as stream:
                stream.write(b"health")
                stream.flush()
        except OSError:
            codes.append("STORAGE_UNAVAILABLE")
    else:
        codes.append("STORAGE_READINESS_UNSUPPORTED")
    # Do not recycle the app merely because SIDOF returned a 404 or timeout.
    return JSONResponse(
        {"status": "not_ready" if codes else "ready", "codes": codes}, status_code=503 if codes else 200
    )


@router.get("/operations")
def operations(db: Session = Depends(get_db)):
    try:
        return JSONResponse(jsonable_encoder(operational_status(db, get_settings())))
    except Exception:
        # Public health output contains codes, never URLs, credentials or errors.
        return JSONResponse({"status": "unavailable", "codes": ["DATABASE_UNAVAILABLE"]}, status_code=503)
