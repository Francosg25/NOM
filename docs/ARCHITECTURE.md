# Arquitectura del boletín

React/TypeScript/Vite y FastAPI forman una sola aplicación. El servidor sirve el frontend compilado y contiene un monitor en segundo plano para una instalación de una instancia.

## Lectura y diseño

La interfaz es un boletín: cabecera editorial, navegación horizontal, portada, archivo y fuentes. No usa la estructura de panel lateral y tarjetas KPI de una aplicación analítica. Incluye temas guardados por navegador y una vista de lectura con historial. Español e inglés comparten las mismas consultas; solo cambian las etiquetas y el formato de fechas. El texto oficial se conserva en español sin una traducción automática atribuida a la fuente.

## Datos y consultas

SQLite conserva publicaciones, versiones y cola. Los archivos se guardan en carpetas locales con claves SHA-256. En App Service ambos viven bajo /home/nom-monitor. SQLite de producción usa diario DELETE; se opera con una instancia y un proceso web. PostgreSQL y Blob son adaptadores opcionales para otra escala; no son requisitos del portal.

Con MONITOR_ENABLED=true, el ciclo de vida de FastAPI aplica migraciones, registra fuentes y arranca un hilo que consume la cola durable. SCHEDULER_ENABLED=true permite encolar consultas según su frecuencia. En el primer arranque las fuentes sin fecha inicial se habilitan desde el día actual; una fuente ya configurada conserva su elección. Cerrar el navegador no detiene el monitor; apagar el servidor sí. Para usar el trabajador CLI externo se desactiva el integrado.

Las consultas se deduplican por fuente activa. El botón del portal consulta únicamente fuentes existentes y fechas actuales, con un mínimo de 15 minutos entre solicitudes por fuente. Los errores dejan intervalos pendientes; los intervalos programados parciales se reanudan. Cada observación enlaza la ejecución, el documento y la versión observada, incluso sin cambios. Se conservan las reversiones A → B → A.

## Acceso

AUTH_MODE=portal es el valor por defecto: lectura sin cuenta ni token. El visitante puede consultar y solicitar una actualización acotada. No adquiere permisos para cambiar fuentes o decisiones, aunque envíe una cabecera de rol. En desarrollo local se puede activar el administrador con DEV_AUTH_ENABLED=true. Entra/Easy Auth queda como opción explícita, sin MSAL ni registros obligatorios para el portal.

## Alcance de la información

Las fechas oficiales, de detección y de vigencia se distinguen. No se infiere vigencia automáticamente. La lista reciente se ordena por fecha oficial, coloca las fechas desconocidas al final y permite filtrar 7/30 días. Los extractos son texto de la fuente, no resúmenes generados por IA. Un cambio de versión puede corresponder a texto o enlaces y no acredita por sí solo un cambio legal.

DOF aporta descubrimiento del índice diario; PLATIICA, SNICE y SIDOF siguen sus páginas configuradas. La validación anterior conservó tres documentos reales y dejó DOF pendiente por robots.txt HTTP 503. No se afirma cobertura de todas las normas. El catálogo y las propuestas JE anteriores continúan disponibles por API/CLI como funciones adicionales.
