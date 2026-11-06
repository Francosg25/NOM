# norma. · NOM Monitor

Versión **0.6.0**. Monitor de NOM con el catálogo oficial PLATIICA como inventario y SIDOF para revisar publicaciones diarias del DOF; interfaz Español/English y una lectura sencilla: una tipografía, fondo claro, búsqueda y publicaciones en una sola columna.

Esta versión añade respaldos/restauración verificables, supervisión del monitor, sonda de despliegue, pruebas de navegador/accesibilidad y dependencias transitivas fijadas con hashes. Mantiene la instalación sencilla. [Operación y aceptación Azure](docs/OPERATIONS.md) · [Calidad y dependencias](docs/QUALITY.md) · [Revisión experta de cobertura](docs/COVERAGE_REVIEW.md). El despliegue y la aceptación reales siguen pendientes.

## Iniciar en Windows

1. Cierra el servidor anterior con Ctrl+C. Extrae todo el ZIP; no ejecutes los comandos dentro del archivo comprimido.
2. Ejecuta **PREPARAR_LOCAL.cmd**.
3. Ejecuta **INICIAR_LOCAL.cmd** y abre http://127.0.0.1:8000.

El ZIP incluye la interfaz compilada. No requiere Node para abrirlo. Usa Python 3.12 o 3.13 autorizado. Si actualizas una instalación existente, conserva su `.env` y la carpeta `data`; no borres la base ni las copias descargadas. Al actualizar desde Git, ejecuta ACTUALIZAR_INTERFAZ.cmd antes de iniciar.

## Actualización automática

El servidor consulta SIDOF cada hora y sincroniza el sitemap del catálogo PLATIICA diariamente, también cuando nadie visita el portal. La carga inicial del catálogo se procesa por lotes y puede tardar; si se interrumpe, el trabajo conserva su continuación. Una ficha que requiere revisión no detiene la descarga de las demás: se reintenta por separado y la carga permanece parcial hasta resolverla. Cerrar el navegador no detiene las consultas. En local, la computadora y el servidor deben permanecer encendidos y sin suspenderse. En App Service, habilita Always On y conserva MONITOR_ENABLED=true y SCHEDULER_ENABLED=true. El portal muestra el estado, las fichas pendientes y la última ejecución. Una cola completa solo cubre las fichas incluidas en los sitemaps consultados; contrasta la carga con el catálogo oficial antes de afirmar cobertura completa.

## Uso

- **Consultar fuentes** solicita una revisión de las fuentes activas: SIDOF revisa los últimos siete días y PLATIICA sincroniza el catálogo por lotes. La programación automática continúa según la frecuencia de cada fuente.
- **Novedades** muestra las publicaciones recuperadas ordenadas por fecha oficial. La fecha de detección se conserva por separado.
- **Buscar publicaciones** permite buscar por NOM o palabra, fecha, tipo y cambios guardados.
- **Catálogo NOM** lista las fichas importadas desde PLATIICA, vigentes y no vigentes, con estado y ámbito de producto. Esta vista no incluye las publicaciones SIDOF y solo refleja lo que ya se importó; revisa **Estado de fuentes** y la cobertura antes de considerarla un inventario completo.
- **Consultar producto** busca coincidencias textuales en NOM vigentes guardadas desde PLATIICA y en publicaciones SIDOF usando una fracción mexicana de 8 dígitos (o 10 con NICO) o una descripción. Muestra estado, ámbito de producto/servicio y evidencia para revisión. Una persona con rol administrador puede guardar la entrada en el catálogo para reevaluar publicaciones y proponer coincidencias; requieren revisión humana.
- Abre un título para leer su contenido, consultar versiones, descargar la copia original y visitar SIDOF.
- **Estado de fuentes** muestra la carga inicial, la programación y el historial de PLATIICA y SIDOF.

La consulta por producto no relaciona automáticamente una fracción con una NOM: PLATIICA no proporciona esa tabla en las fichas consultadas. Una coincidencia textual es una pista, no una determinación de aplicabilidad. Guardar un producto requiere permisos de administrador y registra sus datos en el catálogo local para el seguimiento futuro. Las revisiones parciales pueden haber guardado documentos válidos; las fichas sin estado o sin ámbito de producto quedan señaladas y no se presentan como NOM vigentes.

La actualización conserva las publicaciones y trabajos históricos de fuentes anteriores, pero la búsqueda actual usa el conector del catálogo PLATIICA y SIDOF. No se borran documentos para cambiar de fuente.

## Local y Azure

La instalación usa FastAPI, React, SQLite y archivos locales. Abre sin cuenta. La edición local puede habilitarse con la configuración de desarrollo; el visitante de producción es lector.

En **App Service Linux/Python 3.13**, usa `startup.sh`, una instancia y un proceso web; la base y evidencia se guardan bajo `/home/nom-monitor`. Always On mantiene la aplicación cargada. No requiere Foundry, Entra, Blob, Docker ni un trabajador externo. El despliegue en la instancia real continúa pendiente de prueba.

Para generar el ZIP desde un clon con dependencias frontend instaladas:

```bash
bash scripts/package-appservice.sh
```

Windows usa validación nativa de certificados mediante truststore. Ejecuta **DIAGNOSTICAR_CONEXION.cmd** para comprobar la API SIDOF; se guarda `data/diagnostico_conexion.json`. No se desactiva HTTPS ni se aceptan certificados desconocidos automáticamente.

## English

SIDOF is the bulletin's only active source. Select English at the top. Search, filters, reading, versions and daily-check details remain available; official documents stay in Spanish. Product lookup searches saved publication text by a Mexican tariff code (8 digits, or 10 with NICO) or product description and shows evidence for human review. Administrators can save entries for ongoing monitoring and review proposed matches. It does not use an official tariff database or decide applicability. Legacy source records are retained, with their monitoring disabled. Partial checks may save valid publications and do not establish complete NOM coverage.

[SIDOF diario](docs/SIDOF_DAILY.md) · [Conexiones](docs/CONNECTION.md) · [Azure](docs/AZURE.md) · [Validación](docs/VALIDATION.md)
