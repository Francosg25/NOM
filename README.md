# norma. · JE NOM Monitor

Un portal para leer publicaciones y cambios de la normativa mexicana. Interfaz en **Español / English**, con búsqueda, filtros por fecha/fuente/tipo, temas guardados y lectura de documentos con historial.

El portal abre directamente. La instalación sencilla usa **SQLite y archivos locales**, y el servidor consulta las fuentes en segundo plano. No requiere Entra, Blob Storage, PostgreSQL, Foundry, Docker ni un WebJob.

## Probar en Windows

La versión actual es **0.3.0**: encabezado **norma.**, fondo papel, navegación horizontal y selector visible **Español / English**. Una barra lateral verde con Productos/Alertas corresponde a la interfaz anterior.

Desde el ZIP, extrae todo en una carpeta y ejecuta **PREPARAR_LOCAL.cmd**, después **INICIAR_LOCAL.cmd**. El ZIP incluye la interfaz compilada; para esa prueba solo necesitas Python 3.12 o 3.13 autorizado. [Instrucciones completas ES/EN](docs/LOCAL.md).

Si actualizas desde Git, usa la rama **feature/piloto-verificable**; cierra el servidor anterior, ejecuta **ACTUALIZAR_INTERFAZ.cmd** y vuelve a abrir **INICIAR_LOCAL.cmd**. El arranque comprueba la compilación y evita abrir una versión anterior que siga ocupando el puerto.

Para preparar manualmente un clon, necesitas también Node.js compatible con Vite (se validó Node 24). Desde la carpeta del repositorio, en PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
cd frontend
npm ci
npm run build
cd ..
.\INICIAR_LOCAL.cmd
```

Si tienes Python 3.12, usa `py -3.12` en el primer comando. Abre http://127.0.0.1:8000. Solo necesitas la ventana del portal: aplica las migraciones, registra las fuentes y atiende la cola automáticamente. Las consultas comienzan tras el arranque y se repiten según la frecuencia de cada fuente. No inicies además el trabajador antiguo.

Si ya existe un `.env`, añade `AUTH_MODE=portal`, `MONITOR_ENABLED=true` y `SCHEDULER_ENABLED=true`. No borres la base existente. `DEV_AUTH_ENABLED=true` y `DEV_DEFAULT_ROLE=administrador` permiten editar el seguimiento localmente, sin pantalla de acceso. El despliegue público utiliza lectura abierta; la edición de fuentes y decisiones no se habilita al visitante.

Para arrancar manualmente, desde `backend/`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Con las variables del ejemplo, ese proceso ya incluye el monitor. En Linux/macOS: `bash scripts/setup.sh`, después `cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.

## El recorrido

1. **El boletín** muestra las publicaciones por fecha oficial. La detección tiene su propia fecha; encontrar hoy una norma antigua no la convierte en nueva.
2. **Explorar publicaciones** busca en títulos, identificadores y texto conservado. Puedes filtrar últimos 7/30 días, fuente, tipo o documentos con versiones nuevas.
3. **Tu radar** guarda palabras en el navegador para repetir búsquedas; no crea una cuenta ni implica cobertura automática de todos los productos JE.
4. **Las fuentes** muestra páginas vigiladas, frecuencia, errores y consultas. En local, “Editar seguimiento” ajusta URLs y frecuencia.
5. **Consultar fuentes** solicita una revisión de las páginas configuradas. Se reutiliza una consulta en curso y se evita repetir una fuente dentro de 15 minutos.
6. Al abrir un documento puedes leer el texto extraído, ver versiones, descargar la copia y abrir la fuente oficial.

El selector **Español / English** recuerda el idioma y admite `?lang=en` o `?lang=es`. La guía **Cómo funciona / How it works** explica el recorrido y los estados. Los controles, explicaciones y mensajes de conexión se muestran en ambos idiomas; los títulos, documentos y detalles originales de las fuentes conservan su idioma.

## Azure App Service

El paquete está adaptado a **Linux/Python 3.13, una instancia y un proceso web**. `startup.sh` usa SQLite en `/home/nom-monitor/nom.db`, archivos en `/home/nom-monitor/evidence` y el monitor integrado. Habilita Always On para que siga consultando sin visitas. Consulta [despliegue sencillo](docs/AZURE.md).

```bash
bash scripts/package-appservice.sh
```

El ZIP incorpora la interfaz compilada y `requirements.txt` en la raíz para Oryx. No incluye bases, `.env`, credenciales ni entornos virtuales.

## Qué fuentes cubre

DOF descubre notas enlazadas en su índice diario. PLATIICA sigue las fichas configuradas, SNICE sus páginas configuradas y SIDOF un documento de referencia conocido. **No se ha acreditado cobertura de todas las normas recientes**: el índice diario DOF devolvió HTTP 503 en robots.txt durante la validación previa. El portal conserva y muestra ese fallo; no lo interpreta como ausencia de novedades.

[Fuentes y límites](docs/SOURCES.md) · [Evidencia del piloto](docs/PILOT_ACCEPTANCE.md) · [Arquitectura](docs/ARCHITECTURE.md) · [Validación](docs/VALIDATION.md)

## Desarrollo y opciones

Desde `backend/`: `python -m pytest -q`. Desde `frontend/`: `npm run build`. No requieren servicios Azure. El catálogo JE y las propuestas anteriores siguen disponibles en la API/CLI para usos adicionales, fuera de la navegación principal del boletín.

Para un trabajador externo, desactiva `MONITOR_ENABLED` y utiliza `python -m app.cli worker --poll --schedule`; no ejecutes ambos modos a la vez. PostgreSQL, Entra/Easy Auth y el adaptador Blob son opcionales. Para Blob se instalan dependencias adicionales con `pip install -r backend/requirements-azure.txt`.

Las muestras sintéticas requieren una base separada cuyo nombre incluya `demo`, `ENVIRONMENT=development` y `DEMO_MODE=true`. `python -m app.cli demo` no carga normas oficiales ni se ejecuta al iniciar el portal.
