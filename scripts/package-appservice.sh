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
mkdir -p "$payload/backend" "$payload/frontend" "$payload/scripts" "$payload/docs"
cp -R "$project_root/backend/app" "$project_root/backend/alembic" "$payload/backend/"
cp -R "$project_root/backend/tests" "$payload/backend/"
cp "$project_root/backend/alembic.ini" "$payload/backend/"
cp "$project_root/backend/requirements.txt" "$project_root/backend/requirements-azure.txt" "$project_root/backend/requirements-azure.lock" "$project_root/backend/requirements-dev.txt" "$project_root/backend/requirements.in" "$project_root/backend/requirements-dev.in" "$project_root/backend/pyproject.toml" "$payload/backend/"
cp "$project_root/backend/requirements.txt" "$payload/requirements.txt"
cp -R "$project_root/frontend/dist" "$payload/frontend/"
cp -R "$project_root/frontend/src" "$payload/frontend/"
cp "$project_root/frontend/package.json" "$project_root/frontend/package-lock.json" "$project_root/frontend/tsconfig.json" "$project_root/frontend/vite.config.ts" "$project_root/frontend/index.html" "$payload/frontend/"
cp "$project_root/frontend/vitest.config.ts" "$project_root/frontend/playwright.config.ts" "$payload/frontend/"
cp -R "$project_root/frontend/e2e" "$payload/frontend/"
cp "$project_root/scripts/frontend-build.mjs" "$project_root/scripts/start_local.py" "$payload/scripts/"
cp "$project_root/scripts/setup.sh" "$project_root/scripts/setup.ps1" "$project_root/scripts/start-appservice.sh" "$project_root/scripts/package-appservice.sh" "$payload/scripts/"
cp "$project_root/scripts/e2e_server.py" "$project_root/scripts/package_smoke.py" "$payload/scripts/"
cp "$project_root/PREPARAR_LOCAL.cmd" "$project_root/ACTUALIZAR_INTERFAZ.cmd" "$project_root/INICIAR_LOCAL.cmd" "$project_root/DIAGNOSTICAR_CONEXION.cmd" "$project_root/.env.example" "$project_root/README.md" "$payload/"
cp -R "$project_root/docs/." "$payload/docs/"
cp "$project_root/scripts/start-appservice.sh" "$payload/startup.sh"
find "$stage" -type d -name __pycache__ -prune -exec rm -rf '{}' +
find "$stage" -type f -name '*.pyc' -delete

# Python dependencies must be in requirements.txt at the ZIP root for Oryx.
(cd "$payload" && zip -qr "$stage/package.zip" .)
mv "$stage/package.zip" "$output"
echo "Paquete App Service: $output"
