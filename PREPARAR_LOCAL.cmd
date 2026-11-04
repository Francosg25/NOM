@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 goto :failed
if not exist ".env" copy ".env.example" ".env" >nul
if not exist "frontend\dist\portal-release.json" (
  call ACTUALIZAR_INTERFAZ.cmd
  if errorlevel 1 goto :failed
)
echo.
echo Preparacion terminada. Ejecuta INICIAR_LOCAL.cmd.
pause
exit /b 0
:failed
echo.
echo No se completo la preparacion. Revisa el error de arriba.
echo Python debe estar autorizado para ejecutarse en esta computadora.
pause
exit /b 1
