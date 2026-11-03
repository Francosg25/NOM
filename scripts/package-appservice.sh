#!/usr/bin/env bash
# Build a ZIP for App Service Linux Python with Oryx build enabled.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="${1:-$project_root/data/nom-appservice.zip}"
mkdir -p "$(dirname "$output")"
output="$(cd "$(dirname "$output")" && pwd)/$(basename "$output")"

if [[ ! -d "$project_root/frontend/node_modules" ]]; then
  echo 'Instala primero las dependencias del frontend: (cd frontend && npm ci)' >&2
  exit 1
fi

(cd "$project_root/frontend" && npm run build)
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/backend" "$stage/frontend"
cp -R "$project_root/backend/app" "$project_root/backend/alembic" "$stage/backend/"
cp "$project_root/backend/alembic.ini" "$stage/backend/"
sed '/^pytest==/d' "$project_root/backend/requirements.txt" > "$stage/requirements.txt"
cp -R "$project_root/frontend/dist" "$stage/frontend/"
cp "$project_root/scripts/start-appservice.sh" "$stage/startup.sh"
find "$stage" -type d -name __pycache__ -prune -exec rm -rf '{}' +
find "$stage" -type f -name '*.pyc' -delete

# Python dependencies must be in requirements.txt at the ZIP root for Oryx.
(cd "$stage" && zip -qr "$output" .)
echo "Paquete App Service: $output"
