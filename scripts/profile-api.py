"""Profile an isolated synthetic history using a supplied official HTML/JSON sample.

No external requests or production database access. The fixture represents 12
versions, 12 jobs with 823 queued records each, and 300 large index audit records.
Timings are local API measurements, not measurements of Azure or browser paint.
"""

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.evidence.read_bytes()
    with tempfile.TemporaryDirectory(prefix="nom-performance-") as temp:
        os.environ.update(
            ENVIRONMENT="test",
            AUTH_MODE="portal",
            MONITOR_ENABLED="false",
            SCHEDULER_ENABLED="false",
            DATABASE_URL="sqlite:///" + temp + "/probe.db",
            STORAGE_PATH=temp + "/evidence",
        )
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
        from bs4 import BeautifulSoup
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db import SessionLocal, engine
        from app.models import Base, Source, Publication, Version, Job, Audit
        from app.storage import get_storage

        Base.metadata.create_all(engine)
        note = json.loads(raw)["Nota"]
        note = note[0] if isinstance(note, list) else note
        text = BeautifulSoup(note["cadenaContenido"], "html.parser").get_text(
            "\n", strip=True
        )
        key = get_storage().put(raw, "application/json")
        with SessionLocal() as db:
            source = Source(
                name="Controlled performance fixture", kind="sidof", urls=[]
            )
            db.add(source)
            db.flush()
            pub = Publication(
                source_id=source.id,
                official_id="CONTROLLED-PERFORMANCE",
                url="https://sidof.segob.gob.mx/",
                title=note["titulo"],
            )
            db.add(pub)
            db.flush()
            for sequence in range(1, 13):
                version = Version(
                    publication_id=pub.id,
                    sequence=sequence,
                    content=text,
                    content_hash=str(sequence),
                    evidence_key=key,
                    media_type="application/json",
                )
                db.add(version)
                db.flush()
            pub.current_version_id = version.id
            for sequence in range(12):
                db.add(
                    Job(
                        id="controlled-" + str(sequence),
                        source_id=source.id,
                        requested_by="controlled",
                        status="succeeded",
                        period_start=date(2026, 11, 2),
                        period_end=date(2026, 11, 11),
                        continuation={
                            "queue": [
                                {
                                    "url": "https://controlled.invalid/normalizacion/controlled-record-"
                                    + str(i),
                                    "day": "2026-11-02",
                                }
                                for i in range(823)
                            ]
                        },
                    )
                )
            for index in range(300):
                db.add(
                    Audit(
                        actor="controlled",
                        entity_type="job",
                        entity_id="controlled-0",
                        action="revisar_indice_diario",
                        after={
                            "day": "2026-11-" + str(index % 10 + 1).zfill(2),
                            "declared_no_publication": index % 10 in (6, 7),
                            "recovered_references": [
                                {"title": "Controlled fixture " * 200}
                                for _ in range(20)
                            ],
                        },
                    )
                )
            db.commit()
            publication_id, version_id = pub.id, version.id
        result = {
            "version": app.version,
            "sample_sha256": hashlib.sha256(raw).hexdigest(),
            "fixture": {
                "versions": 12,
                "jobs": 12,
                "queue_per_job": 823,
                "index_audits": 300,
            },
            "endpoints": {},
        }
        with TestClient(app) as client:
            for endpoint in [
                f"/api/publications/{publication_id}?include_content=false",
                f"/api/versions/{version_id}/reading",
                "/api/jobs?page_size=12&summary=true",
                "/api/dashboard",
            ]:
                times = []
                for _ in range(4):
                    started = time.perf_counter()
                    response = client.get(endpoint)
                    times.append((time.perf_counter() - started) * 1000)
                    response.raise_for_status()
                result["endpoints"][endpoint] = {
                    "cold_ms": round(times[0], 2),
                    "warm_median_ms": round(statistics.median(times[1:]), 2),
                    "decoded_bytes": len(response.content),
                    "wire_bytes": int(
                        response.headers.get("content-length", len(response.content))
                    ),
                }
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        engine.dispose()


if __name__ == "__main__":
    main()
