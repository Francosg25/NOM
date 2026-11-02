# JE NOM Monitor

Primera versión de una aplicación interna en español para detectar y revisar disposiciones relacionadas con productos de Johnson Electric. Incluye React/TypeScript/Vite, FastAPI, migraciones Alembic, catálogo configurable, evidencia versionada, propuestas explicables y una cola persistente con trabajador independiente. No requiere Docker ni un servicio de IA.

**Una coincidencia es un posible impacto para revisión, no una conclusión legal ni una autorización de importación.** La cobertura es limitada: tres URLs del piloto se descargaron y verificaron en vivo; el índice diario DOF sigue pendiente por HTTP 503 en robots.txt; consulte [fuentes y cobertura](docs/SOURCES.md).

## Arranque local en Windows

Requisitos: Python 3.12 y Node.js 22 LTS o compatible con Vite (en este entorno también se validó Node 24). Las instalaciones deben estar autorizadas por TI. No se requiere activar un entorno virtual ni cambiar la política de ejecución de PowerShell. Si no se permite ejecutar scripts, use estos comandos directamente en PowerShell desde la raíz del repositorio:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env  # solo si .env todavía no existe
cd frontend
npm ci
npm run build
cd ..\backend
..\.venv\Scripts\python.exe -m app.cli init-db
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abra el puerto local 8000 en su navegador. El backend sirve la interfaz compilada. En otra terminal PowerShell, desde `backend/`, inicie el consumidor de trabajos:

```powershell
..\.venv\Scripts\python.exe -m app.cli worker --poll
```

Si TI permite scripts, `scripts/setup.ps1` reúne la preparación y respeta un `.env` existente. No configura Azure ni inicia programación automática.

`.env.example` activa **autenticación de desarrollo exclusivamente local** y el rol administrador para poder probar la aplicación. La interfaz muestra ese modo y permite comprobar otros roles. No exponga esta configuración a la red ni la copie a producción. Sin activación explícita del modo local, la API exige un token Entra. La configuración de producción rechaza modo local, demo, SQLite y almacenamiento local.

En Linux/macOS: `bash scripts/setup.sh`, después, desde `backend/`, `../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` y en otra terminal `../.venv/bin/python -m app.cli worker --poll`.

Para desarrollo con recarga, ejecutar la API con `--reload` y `npm run dev` desde `frontend/`. Vite dirige `/api` al puerto 8000. En producción se usa la compilación, sin servidor Vite.

## Recorrido principal

1. En **Productos**, cree familias, subfamilias y productos. Puede guardar datos incompletos; la interfaz informa lo faltante. Defina palabras clave, sinónimos, normas vigiladas, fracción y responsables. Desactive registros para conservar el historial.
2. En **Fuentes y ejecuciones**, revise cobertura y configure URLs concretas para PLATIICA/SNICE. No use una portada como prueba de cobertura. DOF inicia con un índice diario; SIDOF tiene un conector separado para el documento de referencia conocido. PLATIICA y SNICE incluyen las URLs del piloto. `configure-pilot` completa configuraciones vacías existentes.
3. Solicite una revisión manual indicando fechas. La API devuelve un trabajo en cola; el trabajador debe estar corriendo. Consulte estado, contadores, errores y continuación. La frecuencia se aplica si la fuente tiene programación habilitada y se ejecuta el trabajador con `--schedule` y `SCHEDULER_ENABLED=true`.
4. En **Publicaciones**, filtre y consulte contenido, fecha de publicación si está disponible, fecha de detección, versiones y descarga de evidencia autenticada. Una publicación encontrada hoy puede ser antigua.
5. En **Alertas**, revise propuestas y la bandeja general. Asigne responsables, comente y confirme o descarte relaciones con justificación. Solo un revisor puede confirmar aplicabilidad. Las versiones nuevas reabren revisiones y conservan el historial en auditoría.
6. Verifique fechas de entrada en vigor con evidencia de la disposición oficial antes de mostrarlas como próximas. No se calculan automáticamente fechas legales.

Si una consulta falla, queda visible y el periodo sigue pendiente. Reanude trabajos parciales, fallidos o interrumpidos desde la interfaz; no los interprete como ausencia de cambios. Las interrupciones se detectan al vencer el arrendamiento (120 segundos) cuando el trabajador o una nueva solicitud verifica la cola.

## Operación por línea de comandos

Desde `backend/`, usando el Python del entorno virtual:

```text
python -m app.cli init-db
python -m app.cli init-sources
python -m app.cli enqueue 1 --start 2026-01-01 --end 2026-01-02
python -m app.cli worker --once
python -m app.cli enqueue 1 --resume ID_DEL_TRABAJO
python -m app.cli worker --poll
python -m app.cli reevaluate
```

El rango anterior es un ejemplo de consulta retrospectiva, no una afirmación de publicaciones en esas fechas. `init-db` aplica migraciones y registra fuentes sin inventar publicaciones. La cola se conserva en SQLite local o PostgreSQL en producción; reiniciar la API no ejecuta ni borra trabajos. Hay una sola consulta activa por fuente. Se conserva continuación en límites de procesamiento y se exige reanudación explícita.

`worker --once` devuelve código 0 al completar o si no hay trabajo, 1 ante fallo/interrupción y 2 si queda parcial. `reevaluate` propone relaciones faltantes contra documentos ya guardados sin sobrescribir decisiones humanas. Los cambios de catálogo desde la API encolan una reevaluación durable y por lotes. Mantenga el trabajador activo para procesarla; no bloquean el guardado ni cambian decisiones humanas. Las reglas de familia y subfamilia se heredan a productos con el origen indicado en la propuesta.

## Demostración opcional y separada

No se precargan documentos oficiales. Para practicar sin red, detenga sus procesos locales y configure **una base separada** en la terminal antes de iniciar todos los procesos:

```powershell
$env:ENVIRONMENT = 'development'
$env:DEMO_MODE = 'true'
$env:DATABASE_URL = 'sqlite:///./data/demo.db'
$env:STORAGE_PATH = './data/demo-evidence'
python -m app.cli init-db
python -m app.cli demo
```

Use el ejecutable real del entorno virtual en lugar de `python` si no lo tiene activado. Inicie la API con las mismas variables y seleccione demostración en los filtros. Los documentos son sintéticos, sin fechas ni enlaces oficiales inventados. Los indicadores oficiales excluyen demostraciones. No se permite este modo en producción. Para volver a datos oficiales, cierre esas terminales y reinicie sin las variables de demo.

## Validación y documentación

Desde `backend/`: `python -m pytest -q`. Desde `frontend/`: `npm run build`. Las pruebas no necesitan red ni servicios de Azure. [Resultados y limitaciones](docs/VALIDATION.md) describe lo ejecutado y lo pendiente, incluido el recorrido principal con muestras controladas.

- [Arquitectura y decisiones](docs/ARCHITECTURE.md)
- [Fuentes y cobertura](docs/SOURCES.md)
- [Compilación y preparación de Azure App Service](docs/AZURE.md)
- API OpenAPI en `/api/docs`; las operaciones de datos exigen identidad y rol. Consulte `/api/audit` con rol revisor o administrador para cambios históricos.

Se consultó `NOM_Monitor_Piloto.zip` y se incorporaron sus URLs de referencia. Consulte [aceptación del piloto](docs/PILOT_ACCEPTANCE.md) para las capturas reales, hashes, repetición sin duplicados, configuración automática y pendientes de JE. No se desplegaron recursos ni se modificó infraestructura de Azure.

## Piloto verificable y acceso corporativo

`python -m app.cli pilot-catalog` carga una muestra pública identificada como borrador: 3 familias, 4 subfamilias y 4 fichas por completar. No inventa números de parte, clasificación arancelaria ni responsables. Requiere completar el catálogo real y revisar las propuestas en Alertas.

`python -m app.cli validate-sources --start AAAA-MM-DD --end AAAA-MM-DD --expected inventario_revisado.json`
comprueba la observación actual, evidencia y contraste del periodo. En el detalle
de cada ejecución se pueden consultar los documentos y recuperar la versión
observada, incluso si no hubo cambios. La aceptación devuelve código 2 mientras
falle una fuente o falte el inventario DOF revisado; no acredita cobertura a partir
de documentos históricos guardados.

La interfaz integra inicio de sesión y renovación de tokens con MSAL. Configurar `ENTRA_TENANT_ID`, `ENTRA_AUDIENCE`, `ENTRA_CLIENT_ID` y `ENTRA_SCOPES` según [Azure y Entra](docs/AZURE.md). El usuario utiliza “Iniciar sesión con Microsoft”; no pega tokens en producción. Es necesaria la configuración real del tenant y las asignaciones de roles.

En Windows, después de preparar el entorno: `INICIAR_LOCAL.cmd` inicia la aplicación y el trabajador. `INICIAR_AUTOMATICO.cmd` ejecuta explícitamente el trabajador con programación; mantenga un solo programador o instálelo como proceso supervisado según el alojamiento. No se instala un servicio ni se registra una tarea automáticamente.
