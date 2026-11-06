# Arquitectura del boletín

El seguimiento activo usa el Catálogo Mexicano de Normas de PLATIICA como inventario y SIDOF para publicaciones diarias del DOF. Las fuentes antiguas se desactivan de forma idempotente, sin borrar documentos ni evidencias. La interfaz mantiene el boletín SIDOF y muestra el estado de sincronización PLATIICA por separado.

React/TypeScript/Vite y FastAPI forman una sola aplicación. El servidor sirve el frontend compilado y contiene un monitor en segundo plano para una instalación de una instancia.

## Lectura y diseño

La interfaz es un boletín: cabecera editorial, navegación horizontal, portada, archivo y fuentes. No usa la estructura de panel lateral y tarjetas KPI de una aplicación analítica. Incluye temas guardados por navegador y una vista de lectura con historial. Español e inglés comparten las mismas consultas; solo cambian las etiquetas y el formato de fechas. El texto oficial se conserva en español sin una traducción automática atribuida a la fuente.

## Datos y consultas

SQLite conserva publicaciones, versiones y cola. Los archivos se guardan en carpetas locales con claves SHA-256. En App Service ambos viven bajo /home/nom-monitor. SQLite de producción usa diario DELETE; se opera con una instancia y un proceso web. PostgreSQL y Blob son adaptadores opcionales para otra escala; no son requisitos del portal.

Con MONITOR_ENABLED=true, el ciclo de vida de FastAPI aplica migraciones, registra ambas fuentes y arranca un hilo que consume la cola durable. SCHEDULER_ENABLED=true habilita SIDOF cada hora y PLATIICA diariamente. En el primer arranque, la carga PLATIICA descubre sus fichas NOM en los sitemaps y procesa una cola durable por lotes; las revisiones posteriores descargan fichas con `lastmod` nuevo y vuelven a revisar las que no publican esa fecha. Solo el agotamiento de la cola observada se marca como sincronizado; no prueba que el sitemap incluya todas las fichas. Una configuración de programación ya existente conserva sus fechas y elección. Cerrar el navegador no detiene el monitor; apagar el servidor sí. Para usar el trabajador CLI externo se desactiva el integrado.

Las consultas se deduplican por fuente activa. El botón del portal revisa los últimos siete días de SIDOF. Después de un fallo se permite reintentar tras un minuto desde la finalización; después de una consulta correcta se mantienen 15 minutos entre solicitudes. Los errores dejan intervalos pendientes; los intervalos programados parciales se reanudan. Cada observación enlaza la ejecución, el documento y la versión observada, incluso sin cambios. Se conservan las reversiones A → B → A. La identidad de una publicación es única por fuente e identificador; no se afirma deduplicación entre dos conectores diferentes.

## Acceso

AUTH_MODE=portal es el valor por defecto: lectura sin cuenta ni token. El visitante puede consultar y solicitar una actualización acotada. No adquiere permisos para cambiar fuentes o decisiones, aunque envíe una cabecera de rol. En desarrollo local se puede activar el administrador con DEV_AUTH_ENABLED=true. Entra/Easy Auth queda como opción explícita, sin MSAL ni registros obligatorios para el portal.

## Alcance de la información

Las fechas oficiales, de detección y de vigencia se distinguen. No se infiere vigencia automáticamente. La lista reciente se ordena por fecha oficial, coloca las fechas desconocidas al final y permite filtrar 7/30 días. Los extractos son texto de la fuente, no resúmenes generados por IA. Un cambio de versión puede corresponder a texto o enlaces y no acredita por sí solo un cambio legal.

La vista **Consultar producto** (`POST /api/product-search`) acepta una fracción mexicana de 8 dígitos o 10 con NICO, o una descripción. Busca de forma textual en las versiones actuales de NOM vigentes de PLATIICA y publicaciones SIDOF, devuelve fragmentos y términos de coincidencia, y excluye demostraciones, fichas no vigentes y estado desconocido. La búsqueda descriptiva normaliza acentos y ordena por proporción de términos encontrados; no es búsqueda semántica. Un administrador puede guardar la entrada en `catalog`; esto encola la reevaluación histórica y permite que futuras versiones propongan alertas. Las coincidencias por fracción son textuales; no se consulta una tabla oficial que relacione fracciones con NOM. Las propuestas requieren revisión humana. Un resultado vacío tampoco acredita que no haya una NOM aplicable.

SIDOF diario consulta el manifiesto de ediciones, las notas de cada fecha y el detalle de las seleccionadas o sin título. Valida identidad, fecha y diario; conserva JSON como evidencia y texto extraído para búsqueda. Cada día registra conteos, IDs seleccionados, referencias sin clasificación y hashes de los índices. GET /api/jobs/{id} expone index_checks para el lector del portal. Una referencia pendiente no impide guardar una NOM válida, pero impide aprobar la cobertura completa. [Contrato y límites](SIDOF_DAILY.md).

Los conectores DOF HTML, PLATIICA de fichas individuales y SNICE permanecen como código y datos históricos; el nuevo conector `platiica_catalog` es el que sincroniza el inventario.

## Calidad operativa · 0.6.0

`routers/publications.py` agrupa búsqueda, revisión y evidencia; `routers/operations.py` expone readiness y señales operativas. `schemas.py` y los helpers extraídos por Copilot evitan que esos dominios dependan de main. La refactorización mantiene rutas y contratos. `recovery.py` implementa snapshot SQLite y restauración verificada; `observability.py` guarda un pulso durable del monitor/worker mediante una migración nueva. El resto de routers puede separarse gradualmente. Consulte OPERATIONS.md antes de escalar; esta versión mantiene una instancia y no acredita alta disponibilidad.
