@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero ejecuta PREPARAR_LOCAL.cmd.
  pause
  exit /b 1
)
pushd backend
"..\.venv\Scripts\python.exe" -m app.diagnostics --output ..\data\diagnostico_conexion.json
set diagnostic_result=%errorlevel%
popd
echo.
echo Si se genero el informe, esta en data\diagnostico_conexion.json.
echo Un resultado pendiente no significa que no haya normas nuevas.
pause
exit /b %diagnostic_result%
