import hashlib

import httpx
import pytest

from app.deployment_check import check_deployment


@pytest.mark.parametrize("fault", [None, "version", "evidence", "worker", "scheduler"])
def test_deployment_probe_rejects_regressions_after_restart(fault):
    baseline = {
        "checked_at": "2026-10-01T00:00:00Z",
        "publication_count": 1,
        "scheduler_job_ids": ["old"],
        "sample": {"publication_id": 1, "version_id": 2, "sha256": hashlib.sha256(b"original").hexdigest()},
    }

    def handle(request):
        path = request.url.path
        data = {
            "/api/health": {"frontend": {"version": "wrong" if fault == "version" else "0.6.0"}},
            "/api/ready": {"status": "ready"},
            "/api/operations": {"codes": []},
            "/api/dashboard": {"sources": [{"active": True, "kind": "sidof", "publication_count": 1}]},
            "/api/jobs": {
                "items": [
                    {
                        "id": "old" if fault == "scheduler" else "new",
                        "requested_by": "scheduler",
                        "requested_at": "2026-10-02T00:00:00Z",
                        "status": "succeeded",
                    }
                ]
            },
            "/api/publications/1": {"versions": [{"id": 2}]},
        }
        if path == "/api/versions/2/evidence":
            return httpx.Response(200, content=b"corrupt" if fault == "evidence" else b"original")
        return httpx.Response(503 if path == "/api/ready" and fault == "worker" else 200, json=data[path])

    with httpx.Client(transport=httpx.MockTransport(handle), base_url="https://controlled.test") as client:
        result = check_deployment(client, "0.6.0", baseline, require_automatic=True)
    assert result["passed"] is (fault is None)
