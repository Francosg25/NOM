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
..\.venv\Scripts\python.exe -m app.cli init-db
if errorlevel 1 exit /b 1
start "NOM - trabajador" ..\.venv\Scripts\python.exe -m app.cli worker --poll
start "NOM - web" ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
start "" http://127.0.0.1:8000
popd
