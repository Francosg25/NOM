# norma. · NOM Monitor

Versión **0.6.0**. Boletín de publicaciones relacionadas con NOM, con **SIDOF como única fuente activa**, interfaz Español/English y una lectura sencilla: una tipografía, fondo claro, búsqueda y publicaciones en una sola columna.

Esta versión añade respaldos/restauración verificables, supervisión del monitor, sonda de despliegue, pruebas de navegador/accesibilidad y dependencias transitivas fijadas con hashes. Mantiene la instalación sencilla. [Operación y aceptación Azure](docs/OPERATIONS.md) · [Calidad y dependencias](docs/QUALITY.md) · [Revisión experta de cobertura](docs/COVERAGE_REVIEW.md). El despliegue y la aceptación reales siguen pendientes.

## Iniciar en Windows

1. Cierra el servidor anterior con Ctrl+C. Extrae todo el ZIP; no ejecutes los comandos dentro del archivo comprimido.
2. Ejecuta **PREPARAR_LOCAL.cmd**.
3. Ejecuta **INICIAR_LOCAL.cmd** y abre http://127.0.0.1:8000.

El ZIP incluye la interfaz compilada. No requiere Node para abrirlo. Usa Python 3.12 o 3.13 autorizado. Si actualizas una instalación existente, conserva su `.env` y la carpeta `data`; no borres la base ni las copias descargadas. Al actualizar desde Git, ejecuta ACTUALIZAR_INTERFAZ.cmd antes de iniciar.

## Actualización automática

El servidor consulta SIDOF cada hora por defecto, también cuando nadie visita el portal. Cerrar el navegador no detiene las consultas. En local, la computadora y el servidor deben permanecer encendidos y sin suspenderse. En App Service, habilita Always On y conserva MONITOR_ENABLED=true y SCHEDULER_ENABLED=true. El portal muestra próxima consulta automática, última descarga, última revisión completa y fechas pendientes. Las nuevas publicaciones aparecen al volver a abrir el portal. Consultar SIDOF es una actualización manual adicional.

## Uso

- **Consultar SIDOF** solicita una consulta de los últimos siete días. El servidor también consulta automáticamente con la frecuencia configurada, mientras permanezca encendido.
- **Novedades** muestra las publicaciones recuperadas ordenadas por fecha oficial. La fecha de detección se conserva por separado.
- **Buscar publicaciones** permite buscar por NOM o palabra, fecha, tipo y cambios guardados.
- Abre un título para leer su contenido, consultar versiones, descargar la copia original y visitar SIDOF.
- **Estado de SIDOF** muestra la programación y el historial. Ver revisión diaria permite inspeccionar fechas, notas y referencias pendientes.

Las revisiones parciales pueden haber guardado publicaciones válidas. SIDOF es una fuente oficial, pero que una consulta termine no garantiza cobertura integral, ni determina aplicabilidad a productos JE. Las notas sin información suficiente y las fechas no verificadas quedan pendientes.

La actualización desactiva DOF HTML, PLATIICA y SNICE y cancela sus consultas en cola. Conserva las publicaciones, evidencia y trabajos históricos. El boletín filtra por SIDOF; los registros anteriores siguen disponibles en la API para trazabilidad. No se borran documentos para cambiar de fuente.

## Local y Azure

La instalación usa FastAPI, React, SQLite y archivos locales. Abre sin cuenta. La edición local puede habilitarse con la configuración de desarrollo; el visitante de producción es lector.

En **App Service Linux/Python 3.13**, usa `startup.sh`, una instancia y un proceso web; la base y evidencia se guardan bajo `/home/nom-monitor`. Always On mantiene la aplicación cargada. No requiere Foundry, Entra, Blob, Docker ni un trabajador externo. El despliegue en la instancia real continúa pendiente de prueba.

Para generar el ZIP desde un clon con dependencias frontend instaladas:

```bash
bash scripts/package-appservice.sh
```

Windows usa validación nativa de certificados mediante truststore. Ejecuta **DIAGNOSTICAR_CONEXION.cmd** para comprobar la API SIDOF; se guarda `data/diagnostico_conexion.json`. No se desactiva HTTPS ni se aceptan certificados desconocidos automáticamente.

## English

SIDOF is the bulletin's only active source. Select English at the top. Search, filters, reading, versions and daily-check details remain available; official documents stay in Spanish. The simpler interface uses one type family and a single column. Legacy source records are retained, with their monitoring disabled. Partial checks may save valid publications and do not establish complete NOM coverage or product applicability.

[SIDOF diario](docs/SIDOF_DAILY.md) · [Conexiones](docs/CONNECTION.md) · [Azure](docs/AZURE.md) · [Validación](docs/VALIDATION.md)
