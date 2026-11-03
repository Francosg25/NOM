#!/usr/bin/env bash
set -euo pipefail

# The package contains backend/ and frontend/dist/ as siblings.
cd "$(dirname "$0")/backend"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
