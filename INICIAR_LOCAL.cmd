@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero ejecuta PREPARAR_LOCAL.cmd.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\start_local.py --check-frontend >nul 2>nul
if errorlevel 1 (
  echo Actualizando la interfaz de esta carpeta antes de iniciar...
  call "%~dp0ACTUALIZAR_INTERFAZ.cmd"
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" scripts\start_local.py
if errorlevel 1 pause
