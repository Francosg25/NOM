#!/usr/bin/env bash
set -euo pipefail

# The package contains backend/ and frontend/dist/ as siblings.
export ENVIRONMENT="${ENVIRONMENT:-production}"
export AUTH_MODE="${AUTH_MODE:-portal}"
export DEV_AUTH_ENABLED="${DEV_AUTH_ENABLED:-false}"
export MONITOR_ENABLED="${MONITOR_ENABLED:-true}"
export SCHEDULER_ENABLED="${SCHEDULER_ENABLED:-true}"
export DATABASE_URL="${DATABASE_URL:-sqlite:////home/nom-monitor/nom.db}"
export STORAGE_BACKEND="${STORAGE_BACKEND:-local}"
export STORAGE_PATH="${STORAGE_PATH:-/home/nom-monitor/evidence}"
cd "$(dirname "$0")/backend"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
