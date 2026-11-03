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
payload="$stage/app"
mkdir -p "$payload/backend" "$payload/frontend"
cp -R "$project_root/backend/app" "$project_root/backend/alembic" "$payload/backend/"
cp "$project_root/backend/alembic.ini" "$payload/backend/"
sed '/^pytest==/d' "$project_root/backend/requirements.txt" > "$payload/requirements.txt"
cp -R "$project_root/frontend/dist" "$payload/frontend/"
cp "$project_root/scripts/start-appservice.sh" "$payload/startup.sh"
find "$stage" -type d -name __pycache__ -prune -exec rm -rf '{}' +
find "$stage" -type f -name '*.pyc' -delete

# Python dependencies must be in requirements.txt at the ZIP root for Oryx.
(cd "$payload" && zip -qr "$stage/package.zip" .)
mv "$stage/package.zip" "$output"
echo "Paquete App Service: $output"
