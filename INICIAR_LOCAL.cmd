@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero ejecuta PREPARAR_LOCAL.cmd.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\start_local.py
if errorlevel 1 pause
