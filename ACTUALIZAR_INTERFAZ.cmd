@echo off
setlocal
cd /d "%~dp0frontend"
where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo Se necesita Node.js para recompilar la interfaz.
  pause
  exit /b 1
)
call npm.cmd ci
if errorlevel 1 goto :failed
call npm.cmd run build
if errorlevel 1 goto :failed
echo.
echo Interfaz actualizada. Cierra el servidor anterior con Ctrl+C.
echo Despues ejecuta INICIAR_LOCAL.cmd y recarga con Ctrl+F5.
exit /b 0
:failed
echo No se pudo recompilar. Revisa el error de arriba.
pause
exit /b 1
