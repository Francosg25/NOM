@echo off
setlocal
cd /d "%~dp0backend"
if not exist "..\.venv\Scripts\python.exe" exit /b 1
rem Esta ventana debe permanecer abierta. Solo consulta fuentes habilitadas.
set SCHEDULER_ENABLED=true
..\.venv\Scripts\python.exe -m app.cli worker --poll --schedule
