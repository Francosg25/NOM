@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero realiza la preparacion del README.
  pause
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo Primero ejecuta npm ci y npm run build dentro de frontend.
  pause
  exit /b 1
)
pushd backend
set MONITOR_ENABLED=true
set SCHEDULER_ENABLED=true
start "NOM - web" ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
start "" http://127.0.0.1:8000
popd
