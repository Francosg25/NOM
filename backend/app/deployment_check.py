"""Read-only deployment/alert probe; baseline verifies saved evidence after restart."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .models import utcnow


def check_deployment(client, expected_version, baseline=None, require_automatic=False):
    checks, warnings = {}, []
    report = {"checked_at": utcnow().isoformat(), "checks": checks, "warnings": warnings}
    try:

        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        health = get("/api/health")
        checks["release"] = health.get("frontend", {}).get("version") == expected_version
        checks["ready"] = get("/api/ready").get("status") == "ready"
        state = get("/api/operations")
        warnings.extend(state.get("codes", []))
        overview = get("/api/dashboard")
        active = [s for s in overview["sources"] if s["active"]]
        expected_sources = {"sidof", "platiica_catalog"}
        active_kinds = {s["kind"] for s in active}
        checks["required_sources_active"] = (
            expected_sources.issubset(active_kinds) and active_kinds.issubset(expected_sources)
        )
        report["publication_count"] = sum(s.get("publication_count", 0) for s in active)
        runs = get("/api/jobs?page_size=200")["items"]
        report["scheduler_job_ids"] = [j["id"] for j in runs if j["requested_by"] == "scheduler"]
        if require_automatic:
            old = set((baseline or {}).get("scheduler_job_ids", []))
            checks["new_automatic_run"] = bool(baseline) and any(
                j["requested_by"] == "scheduler"
                and j["id"] not in old
                and j["requested_at"] > baseline["checked_at"]
                and j["status"] in ("succeeded", "partial")
                for j in runs
            )
        if baseline:
            checks["publication_count_preserved"] = (
                report["publication_count"] >= baseline["publication_count"]
            )
            sample = baseline.get("sample")
        else:
            items = get("/api/publications?source_kind=sidof&page_size=1")["items"]
            if not items:
                items = get("/api/publications?source_kind=platiica_catalog&page_size=1")["items"]
            sample = None
            if items:
                doc = get("/api/publications/" + str(items[0]["id"]))
                versions = [v for v in doc["versions"] if v.get("evidence_key")]
                if versions:
                    sample = {"publication_id": doc["id"], "version_id": versions[0]["id"]}
        if sample:
            publication_id, version_id = int(sample["publication_id"]), int(sample["version_id"])
            doc = get(f"/api/publications/{publication_id}")
            checks["sample_version_preserved"] = any(v["id"] == version_id for v in doc["versions"])
            response = client.get(f"/api/versions/{version_id}/evidence")
            response.raise_for_status()
            sha = hashlib.sha256(response.content).hexdigest()
            checks["sample_evidence_preserved"] = not sample.get("sha256") or sample["sha256"] == sha
            report["sample"] = {**sample, "sha256": sha}
        else:
            report["sample"] = None
            warnings.append("NO_SAVED_EVIDENCE_TO_VERIFY")
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        checks["probe_completed"] = False
    report["passed"] = bool(checks) and all(checks.values())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--require-automatic-run", action="store_true")
    parser.add_argument(
        "--strict-source", action="store_true", help="Exit 2 on upstream/scheduler warnings too"
    )
    parser.add_argument("--output", type=Path, default=Path("data/deployment-check.json"))
    args = parser.parse_args()
    origin = urlparse(args.url)
    if (
        origin.username
        or origin.password
        or origin.query
        or origin.fragment
        or origin.path not in ("", "/")
        or origin.scheme not in ("http", "https")
        or not origin.hostname
    ):
        parser.error("--url debe ser el origen del portal, sin credenciales ni rutas")
    if origin.scheme == "http" and origin.hostname not in ("localhost", "127.0.0.1", "::1"):
        parser.error("Use HTTPS para un servidor remoto")
    if args.require_automatic_run and not args.baseline:
        parser.error("--require-automatic-run requiere --baseline")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=30, follow_redirects=False) as client:
        report = check_deployment(client, args.version, baseline, args.require_automatic_run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] and not (args.strict_source and report["warnings"]) else 2)


if __name__ == "__main__":
    main()
