# Portal en Azure App Service Linux

La versión actual es 0.6.7 y el seguimiento activo utiliza el catálogo de NOM de PLATIICA y las publicaciones diarias de SIDOF. Los conectores antiguos DOF HTML, PLATIICA de fichas individuales y SNICE no se consultan; sus registros históricos se conservan desactivados.

El lector de 0.6.7 conserva la ventana centrada y muestra las NOM largas por partes, con Anterior, Siguiente y un selector. Solo dibuja la parte seleccionada; las tablas y las listas se conservan completas. El portal solicita metadatos de versiones y resúmenes de procesos, carga la copia elegida por separado y reutiliza hasta cuatro lecturas por sesión. Se eliminaron los desenfoques de las tarjetas y las ventanas. Consulta las mediciones y sus límites en [PERFORMANCE_0.6.7.md](PERFORMANCE_0.6.7.md).

La versión 0.6.4 incorpora un lector con párrafos, numeraciones, tablas, listas, superíndices, subíndices y figuras. El texto comienza en 18 px y puede ajustarse entre 16 y 24 px. La presentación se reconstruye desde la copia original ya guardada; las NOM existentes mejoran sin volver a consultar SIDOF ni modificar sus versiones. Consulta [READING_0.6.4.md](READING_0.6.4.md).

El estado de SIDOF distingue fechas sin índice verificable de errores de conexión y muestra las fechas cuyo índice se revisó en el historial disponible. Una fecha sin índice sigue pendiente cuando el calendario oficial no confirma expresamente la ausencia de publicación. Las publicaciones ya guardadas y las nuevas consultas siguen disponibles; el historial anterior no se reescribe.

La versión 0.6.3 recupera las referencias cuyo JSON está vacío desde la página correspondiente del PDF original de SIDOF. Verifica el diario, la fecha y la página, conserva sus hashes en el registro y evita duplicar una referencia de imagen cuando el índice ya contiene la misma NOM con texto. Los PDF oficiales tienen un límite separado de 64 MiB; las demás respuestas conservan el límite de 12 MiB y la validación HTTPS permanece activa.

Si el calendario API no informa días sin publicación, se comprueba el calendario visual enlazado por el portal SIDOF: debe deshabilitar expresamente la fecha y mostrar una edición anterior, sin ediciones ni notas contradictorias en la API. Un fin de semana o un HTTP 404 aislado no bastan. Esta evidencia aparece como calendario confirmado, separada de los días con índice revisado.

Al instalar esta versión, una fuente SIDOF con programación ya habilitada se vuelve a programar una sola vez para aplicar la recuperación. No requiere ejecutar SQL ni vaciar la base. Se conservan consultas históricas, documentos y frecuencias configuradas. Las consultas parciales anteriores permanecen como historial; el resultado de la nueva ejecución determina el estado actual. También se corrige la etiqueta de emergencia de las NOM-EM que la versión anterior presentó como definitivas.

La comprobación real de recuperación está documentada en [SIDOF_RECOVERY_0.6.3.md](SIDOF_RECOVERY_0.6.3.md).

La instalación sencilla utiliza el App Service existente: **Linux, Python 3.13, Basic B1, una instancia**. Sirve la web y ejecuta el monitor desde un solo proceso. No necesita crear PostgreSQL, Blob, Entra ni un WebJob.

## Preparar y publicar

1. En un equipo o agente con Node.js, ejecutar `cd frontend && npm ci && cd ..` y `bash scripts/package-appservice.sh`.
2. El archivo `data/nom-appservice.zip` contiene `backend/`, `frontend/dist/`, `startup.sh` y `requirements.txt` en la raíz. También incorpora el código de la interfaz y los comandos de prueba en Windows. No contiene datos locales, secretos ni entornos virtuales. No hace falta Node en App Service: la interfaz ya está compilada.
3. En App Service, configurar **SCM_DO_BUILD_DURING_DEPLOYMENT=true** y el comando de inicio **bash startup.sh**. Mantener Python 3.13 y habilitar **Always On**.
4. Publicar el ZIP mediante un método corporativo permitido o Azure CLI autenticada:

```bash
az webapp deploy --resource-group '<GRUPO_DE_RECURSOS>' --name '<NOMBRE_DE_WEB_APP>' --src-path data/nom-appservice.zip
```

No registrar nombres internos de recursos ni credenciales en el repositorio.

## Valores de arranque

El script establece estos valores solo si no se proporcionaron otros:

| Variable | Valor |
| --- | --- |
| ENVIRONMENT | production |
| AUTH_MODE | portal |
| DEV_AUTH_ENABLED | false |
| MONITOR_ENABLED | true |
| SCHEDULER_ENABLED | true |
| DATABASE_URL | sqlite:////home/nom-monitor/nom.db |
| STORAGE_BACKEND | local |
| STORAGE_PATH | /home/nom-monitor/evidence |

Si existen ajustes anteriores de Entra/Blob/PostgreSQL, revisar las variables efectivas para elegir estos valores. No copiar el modo local de administrador al despliegue público.

El modo portal permite consultar publicaciones y solicitar una revisión sin iniciar sesión. Cambiar URLs, catálogos o decisiones conserva permisos de edición; el visitante es lector. El inicio aplica migraciones e inicializa SIDOF sin publicaciones inventadas y programa solo esa fuente cuando no existe una fecha de programación previa.

## Persistencia y consultas

El código de Python puede ejecutarse desde una carpeta temporal de Oryx. Por eso **base y documentos se guardan bajo /home/nom-monitor**, fuera del contenido desplegado. En el App Service Linux integrado, comprobar que el almacenamiento persistente de /home esté habilitado; si corresponde a la configuración, usar `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`.

Usar una instancia, `--workers 1` y el monitor integrado para este piloto con SQLite. El modo de diario de SQLite en producción es DELETE para no usar WAL sobre el volumen compartido. No se ha validado escalado a varias instancias. El monitor se detiene si se apaga o descarga el App Service; Always On mantiene cargada la app. La cola y las consultas pendientes permanecen en SQLite. Los intervalos fallidos se reintentan sin interpretar un error como ausencia de cambios.

No hace falta instalar el trabajador externo. Si se elige hacerlo más adelante, desactivar `MONITOR_ENABLED` en la web.

## Comprobar en la instancia real

- `/api/health` responde y la portada carga sin pantalla de acceso.
- Español / English cambia interfaz, fechas y la guía Cómo funciona / How it works.
- `/api/health` identifica la compilación en `frontend.version` y `frontend.source_sha256`. En esta versión, también debe devolver `backend.version: 0.6.7` y `backend.document_reader: modal-v2`. Ambos números de versión deben corresponder a la marca v0.6.7 de la pantalla. El comprobador de despliegue falla si solo se actualizaron los archivos de la interfaz.
- “Consultar SIDOF” deja una ejecución y después resultados o un error visible.
- Una copia del documento se puede recuperar después de reiniciar la aplicación.
- Se conserva la base al volver a publicar el ZIP.
- La API diaria `https://sidof.segob.gob.mx/dof/sidof` es accesible desde Azure con TLS verificado y las reglas de robots. Una instalación nueva revisa catorce días y después se programa cada hora. Una instalación existente conserva su programación previa.
- “Ver revisión diaria” muestra conteos y referencias pendientes. Buscar `NOM-EM-023-SE-2026` después de consultar el 2 de noviembre de 2026 permite repetir la comprobación conocida; la ventana automática puede requerir ampliar fechas si se prueba más adelante.
- Las fuentes históricas DOF HTML, PLATIICA y SNICE no forman parte de la comprobación de despliegue actual.

El paquete preparado y las pruebas locales no equivalen a un despliegue real. No se crearon ni modificaron recursos Azure durante esta preparación.

Documentación: [Python y archivos persistentes bajo /home](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python), [Always On](https://learn.microsoft.com/en-us/azure/app-service/configure-common), [publicar ZIP con compilación](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip).

## Operación diaria sin visitas

Mantener MONITOR_ENABLED=true y SCHEDULER_ENABLED=true, y ambas fuentes activas con su programación habilitada (SIDOF cada hora y PLATIICA diariamente). Habilitar Always On en la configuración del App Service para mantener cargada la aplicación sin tráfico. La publicación del ZIP no activa por sí sola Always On.

En Estado de fuentes se muestran SIDOF y el Catálogo PLATIICA, incluida la cantidad de fichas pendientes de la carga por lotes. Para aceptar el despliegue, cerrar el navegador y comprobar después que aparezcan ejecuciones nuevas solicitadas por scheduler y que el historial/evidencia sobreviva a un reinicio. Contrastar el inventario recuperado con el catálogo oficial antes de afirmar cobertura completa. No se ha ejecutado este despliegue desde este entorno: no hay una identidad Azure configurada.

Para cargar la NOM conocida del 2 de noviembre en una instalación Azure ya creada, abrir SSH de la misma App Service una vez publicada esta versión. Esperar a que la consulta SIDOF activa termine y ejecutar desde el directorio `backend` de la aplicación, con la misma variable `DATABASE_URL=sqlite:////home/nom-monitor/nom.db` del proceso web:

```bash
DATABASE_URL=sqlite:////home/nom-monitor/nom.db python -m app.cli backfill-sidof --start 2026-11-02 --end 2026-11-03
```

El monitor consume la tarea en segundo plano. Comprobar en el historial SIDOF que se revisó el 2 de noviembre y buscar `NOM-EM-023-SE-2026` en Novedades. Si la tarea devuelve que ya hay una ejecución activa, esperar a que termine y repetir el comando. La carga conserva publicaciones existentes y no interpreta un 404 aislado como ausencia oficial.

Referencia: https://learn.microsoft.com/es-es/azure/app-service/configure-common

La aceptación de esta versión debe seguir [OPERATIONS.md](OPERATIONS.md): sonda antes/después de reiniciar, ejecución automática sin visitas y restauración en una carpeta separada. Health check puede apuntar a `/api/ready`; `/api/operations` distingue fallos locales de revisiones parciales de SIDOF.
