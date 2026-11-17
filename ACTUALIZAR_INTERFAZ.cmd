@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0frontend"
if errorlevel 1 (
  echo No se encontro la carpeta frontend junto a este comando.
  pause
  exit /b 1
)
where node.exe >nul 2>nul
if errorlevel 1 goto :no_node
where npm.cmd >nul 2>nul
if errorlevel 1 goto :no_node
node.exe "..\scripts\check-frontend-lock.mjs"
if errorlevel 1 goto :failed
call npm.cmd --prefix . ci --include=dev
if errorlevel 1 goto :failed
call npm.cmd --prefix . run build
if errorlevel 1 goto :failed
popd
echo.
echo Interfaz actualizada. Cierra el servidor anterior con Ctrl+C.
echo Despues ejecuta INICIAR_LOCAL.cmd y recarga con Ctrl+F5.
exit /b 0
:no_node
echo Se necesita Node.js con npm para recompilar la interfaz.
popd
pause
exit /b 1
:failed
popd
echo No se pudo recompilar. Revisa el error de arriba.
pause
exit /b 1
