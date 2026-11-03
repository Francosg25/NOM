$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno. Utilice Python 3.12 o 3.13 autorizado.' }
}
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $Python -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación de Python' }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
Set-Location (Join-Path $ProjectRoot 'frontend')
npm ci
if ($LASTEXITCODE -ne 0) { throw 'Falló npm ci' }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación' }
Set-Location (Join-Path $ProjectRoot 'backend')
& $Python -m app.cli init-db
if ($LASTEXITCODE -ne 0) { throw 'Fallaron las migraciones' }
Write-Output 'Entorno preparado. Ejecute INICIAR_LOCAL.cmd para abrir el portal con su monitor integrado.'
