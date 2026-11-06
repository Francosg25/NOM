import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { ReactNode } from "react";

type Language = "es" | "en";
const english: Record<string, string> = {
  "Consultar producto": "Product lookup",
  "REVISIÓN PRELIMINAR": "PRELIMINARY REVIEW",
  "Consultar por producto": "Search by product",
  "Ingresa una fracción arancelaria mexicana o describe el producto. Buscaremos coincidencias textuales en NOM vigentes del catálogo PLATIICA y publicaciones SIDOF guardadas.":
    "Enter a Mexican tariff code or describe the product. We will search current NOM records in the PLATIICA catalogue and saved SIDOF publications for text matches.",
  "Buscar por": "Search by",
  "Fracción arancelaria mexicana": "Mexican tariff code",
  "Descripción del producto": "Product description",
  "Fracción arancelaria / NICO": "Tariff code / NICO",
  "Descripción, materiales o uso": "Description, materials or use",
  "Ej. 8501.10.01 o 8501.10.01 00": "E.g. 8501.10.01 or 8501.10.01 00",
  "Ej. motor eléctrico de corriente continua para actuador":
    "E.g. DC electric motor for an actuator",
  "Buscar posibles coincidencias": "Search for possible matches",
  "Buscando…": "Searching…",
  "La fracción admite 8 dígitos o 10 con NICO. Para descripción, incluye tipo de producto, material y uso cuando los conozcas.":
    "The tariff code accepts 8 digits, or 10 with NICO. For descriptions, include product type, material and use when known.",
  "Coincidencias para revisar": "Matches to review",
  "{count} resultados": "{count} results",
  "Se revisaron {count} documentos de NOM vigentes y publicaciones SIDOF.":
    "{count} current NOM records and SIDOF publications were searched.",
  "Catálogo PLATIICA: {current} NOM vigentes entre {records} fichas guardadas.":
    "PLATIICA catalogue: {current} current NOMs among {records} saved records.",
  "Completar la cola del sitemap no demuestra que PLATIICA publique todas las fichas en esos sitemaps.":
    "Completing the sitemap queue does not prove that PLATIICA publishes every catalogue record in those sitemaps.",
  "La última revisión del sitemap no terminó correctamente o la actualización automática está desactivada.":
    "The latest sitemap review did not finish successfully, or automatic updates are disabled.",
  "{count} fichas pendientes de revisar.": "{count} records remain to be checked.",
  "Hay fichas con estado o producto/servicio incompleto; no se incluyen como NOM vigentes.":
    "Some records have incomplete status or product/service fields; they are not included as current NOMs.",
  "Estado oficial": "Official status",
  "Producto/servicio en PLATIICA": "Product/service in PLATIICA",
  "Coincidencias textuales en NOM vigentes guardadas desde PLATIICA y publicaciones SIDOF. No determinan aplicabilidad legal ni sustituyen la clasificación arancelaria o revisión de la disposición oficial.":
    "Text matches in current NOMs saved from PLATIICA and SIDOF publications. They do not determine legal applicability or replace tariff classification or review of the official instrument.",
  "No encontramos coincidencias en las publicaciones guardadas.":
    "No matches were found in saved publications.",
  "Esto no confirma que no existan NOM aplicables: el archivo puede estar incompleto o la publicación puede no mencionar esos términos.":
    "This does not confirm that no NOMs apply: the archive may be incomplete or a publication may not mention these terms.",
  "Coincidencia de fracción": "Tariff-code match",
  "Coincidencia de fracción base": "Base tariff-code match",
  "Coincidencia por descripción": "Description match",
  "Términos encontrados": "Matched terms",
  "Se muestran los primeros 30 resultados más relevantes.":
    "Showing the 30 most relevant results.",
  "Como administrador, puedes guardar esta entrada para que el monitor la compare con publicaciones actuales y futuras.":
    "As an administrator, you can save this entry so the monitor can compare it with current and future publications.",
  "Guardar para seguimiento": "Save for monitoring",
  "Guardando…": "Saving…",
  "Producto guardado para seguimiento automático de publicaciones y posibles coincidencias.":
    "Product saved for automatic monitoring of publications and possible matches.",
  "Seguimiento activo": "Monitoring active",
  "Actualizar coincidencias": "Refresh matches",
  "Las propuestas se generan al procesar publicaciones y requieren revisión humana; no son decisiones de aplicabilidad.":
    "Suggestions are generated as publications are processed and require human review; they are not applicability decisions.",
  "Aún no hay propuestas de coincidencia para este producto.":
    "There are no match suggestions for this product yet.",
  "Productos en seguimiento": "Products being monitored",
  "Selecciona un producto guardado": "Select a saved product",
  pendiente: "pending",
  propuesta: "suggested",
  en_revision: "in review",
  resuelta: "resolved",
  confirmada: "confirmed",
  descartada: "dismissed",
  "Ingresa una fracción mexicana de 8 dígitos, o 10 con NICO.":
    "Enter an 8-digit Mexican tariff code, or 10 digits with NICO.",
  "Agrega palabras descriptivas del producto, como tipo, material o uso.":
    "Add descriptive product words, such as type, material or use.",

  "Última descarga: {date}": "Last download: {date}",
  "Última descarga": "Last download",
  "Última revisión completa": "Last complete period check",
  "Publicaciones guardadas": "Saved publications",
  "Próxima consulta automática": "Next automatic check",
  "Fechas pendientes de verificar": "Dates still to be checked",
  "Hay fechas pendientes de verificar.": "Some dates still need checking.",
  "{count} publicaciones guardadas. Abre el detalle para ver qué falta revisar.":
    "{count} publications saved. Open the details to see what still needs checking.",
  "Revisión parcial del periodo": "Partial period check",
  "El servidor consulta esta fuente automáticamente según la frecuencia indicada. Puedes cerrar el navegador; el servidor debe seguir encendido.":
    "The server checks this source automatically at the listed interval. You can close the browser; the server must keep running.",

  "Publicaciones oficiales por fecha. Se guardan el texto disponible y una copia del original.":
    "Official publications by date. Available text and an original copy are saved.",
  "Hay publicaciones guardadas. La última revisión quedó incompleta.":
    "Publications have been saved. The latest check is incomplete.",
  "Estado de fuentes": "Source status",
  "Consultar SIDOF": "Check SIDOF",
  "Publicaciones NOM": "NOM publications",
  "Publicaciones oficiales de SIDOF.": "Official publications from SIDOF.",
  "PLATIICA aporta el catálogo base de NOM vigentes y SIDOF vigila publicaciones del DOF. Ninguna coincidencia determina aplicabilidad legal.":
    "PLATIICA provides the baseline catalogue of current NOMs, and SIDOF monitors DOF publications. A match does not determine legal applicability.",
  "PLATIICA aporta el catálogo de NOM y SIDOF revisa publicaciones del DOF.":
    "PLATIICA provides the NOM catalogue and SIDOF checks DOF publications.",
  "Busca una NOM por producto o revisa publicaciones y evidencia oficial.":
    "Search NOMs by product or review publications and official evidence.",
  "Una carga parcial no representa todo el catálogo. Consulta el estado para ver qué falta revisar.":
    "A partial import does not represent the full catalogue. Check the source status to see what remains.",
  "La revisión de SIDOF quedó pendiente.": "The SIDOF check is incomplete.",
  "Las publicaciones recuperadas siguen disponibles. Abre el detalle para ver qué falta revisar.":
    "Saved publications remain available. Open the details to see what still needs checking.",

  "Abrir el portal oficial de SIDOF": "Open the official SIDOF portal",
  "SIDOF · publicaciones diarias": "SIDOF · daily publications",
  diario: "daily",
  "Ver revisión diaria": "View daily check",
  "Revisión diaria SIDOF": "SIDOF daily check",
  "Qué se revisó": "What was checked",
  "Las notas son todas las publicaciones del diario, no todas son NOM. Las referencias sin texto o título requieren revisión adicional.":
    "Notes are all the gazette's publications, not all are NOM standards. References without text or a title need additional review.",
  "Todavía no hay un día completo registrado en este lote.":
    "No complete day has been recorded in this batch yet.",
  "{notes} notas revisadas · {selected} publicaciones seleccionadas":
    "{notes} notes checked · {selected} publications selected",
  "SIDOF declaró esta fecha sin publicación; no equivale a una garantía de cobertura integral.":
    "SIDOF declared no publication for this date; this does not guarantee complete coverage.",
  "{count} referencias pendientes de revisión":
    "{count} references need review",
  "El servicio no proporcionó título o texto suficiente para clasificarlas. No se descartaron como irrelevantes.":
    "The service did not provide enough title or text to classify them. They were not dismissed as irrelevant.",
  "SIDOF consulta ediciones y notas por fecha y selecciona publicaciones relacionadas con NOM y reglas de comercio exterior. La primera revisión cubre los últimos siete días. PLATIICA y SNICE siguen sus páginas configuradas. Las notas sin título ni texto quedan señaladas para revisión; encontrar todas las NOM aún requiere contraste con el DOF.":
    "SIDOF checks editions and notes by date and selects publications related to NOM standards and foreign trade rules. The first check covers the last seven days. PLATIICA and SNICE follow their configured pages. Notes without titles or text are flagged for review; finding every NOM still requires comparison with the DOF.",
  "coverage.sidof_daily":
    "Checks editions and notes by date through the official SIDOF API. Saves selected NOM and foreign trade publications, with counts and unresolved references in each daily check. Does not automatically determine product applicability.",
  "La conexión HTTPS falló al validar el certificado: puede no ser reconocido, estar vencido o tener una cadena incompleta. Esta fuente no pudo revisarse.":
    "HTTPS certificate validation failed: the certificate may be untrusted, expired or missing part of its chain. This source could not be checked.",
  "No se pudo negociar la conexión segura con el sitio o el proxy. La revisión sigue pendiente.":
    "A secure connection could not be negotiated with the website or proxy. The check remains pending.",
  "El servidor del portal no pudo cargar su configuración de certificados HTTPS. Revisa la configuración de certificados antes de volver a consultar.":
    "The portal server could not load its HTTPS certificate configuration. Check that configuration before trying again.",
  "El proxy de la red solicita una autenticación que el proceso del portal no tiene disponible. La revisión no pudo realizarse.":
    "The network proxy requires authentication that the portal process does not have available. The check could not be performed.",
  "La configuración del proxy no es válida o está incompleta para este proceso. La revisión sigue pendiente.":
    "The proxy configuration is invalid or incomplete for this process. The check remains pending.",
  "No se pudo conectar con la fuente a través del proxy configurado. La revisión sigue pendiente.":
    "Could not connect to the source through the configured proxy. The check remains pending.",
  "No se pudo resolver el nombre del sitio oficial. Revisa la resolución DNS y la configuración del proxy en el equipo o servidor donde corre el portal.":
    "The official website's hostname could not be resolved. Check DNS resolution and proxy configuration on the computer or server running the portal.",
  "Se agotó el tiempo para conectar con el sitio o el proxy. No se confirmó el acceso a la fuente.":
    "The connection to the website or proxy timed out. Access to the source was not confirmed.",
  "La conexión se abrió, pero la fuente no respondió a tiempo. La revisión quedó incompleta.":
    "The connection opened, but the source did not respond in time. The check is incomplete.",
  "Hay consultas recientes. Espera un minuto tras una revisión fallida o 15 minutos tras una revisión correcta antes de repetir.":
    "There are recent checks. Wait one minute after an unsuccessful check or 15 minutes after a successful check before trying again.",
  Novedades: "Latest publications",
  "Estado de las fuentes": "Source status",
  "Cómo funciona": "How it works",
  "LA GUÍA / NOM MONITOR": "THE GUIDE / NOM MONITOR",
  "De la publicación a la lectura": "From publication to reading",
  "El portal revisa páginas oficiales configuradas, guarda lo que encuentra y te permite leerlo después. Así se usa.":
    "The portal checks configured official pages, saves what it finds and lets you read it later. Here is how to use it.",
  "Consulta las fuentes": "Check the sources",
  "Pulsa Consultar fuentes. El servidor revisa las páginas registradas y guarda una copia de los documentos que puede recuperar. Con el monitor activo, repite la revisión según la frecuencia de cada fuente.":
    "Select Check sources. The server checks the registered pages and saves a copy of the documents it can retrieve. When monitoring is active, it repeats the check at each source's configured interval.",
  "Lee las publicaciones": "Read the publications",
  "En Novedades aparecen las publicaciones recuperadas. Busca una NOM o una palabra, filtra por fuente o fecha y abre un título para leer el documento.":
    "Latest publications shows the retrieved documents. Search for a NOM or a keyword, filter by source or date, and open a title to read the document.",
  "Comprueba el original": "Check the original",
  "Dentro de cada publicación puedes abrir el sitio oficial, descargar la copia consultada y ver las versiones guardadas. Usa el documento oficial para verificar cualquier obligación.":
    "Inside a publication, you can open the official website, download the retrieved copy and view saved versions. Use the official document to verify any obligation.",
  "CÓMO LEER EL RESULTADO": "UNDERSTANDING THE RESULTS",
  "Cada estado tiene un significado.": "Every status has a meaning.",
  "Primera copia": "First saved copy",
  "Se guardó el documento por primera vez. Puede ser una publicación antigua encontrada hoy.":
    "The document was saved for the first time. It may be an older publication found today.",
  "El contenido guardado cambió respecto a una copia anterior. No confirma por sí solo una modificación legal ni que aplique a tu producto.":
    "The saved content differs from an earlier copy. This alone does not confirm a legal amendment or that it applies to your product.",
  "La consulta terminó correctamente dentro de la cobertura configurada. No garantiza que se hayan encontrado todas las NOM.":
    "The check completed successfully within the configured coverage. It does not guarantee that every NOM was found.",
  "La fuente no pudo revisarse por completo. No significa que no existan novedades; se conserva la última copia válida.":
    "The source could not be checked completely. This does not mean there are no updates; the last valid copy is kept.",
  "QUÉ ESTÁS VIGILANDO": "WHAT YOU ARE MONITORING",
  "La cobertura depende de las páginas.": "Coverage depends on the pages.",
  "DOF sigue su índice diario. PLATIICA y SNICE siguen las fichas o páginas que se configuren. SIDOF permite seguir un documento conocido. La cobertura diaria de DOF aún requiere validación.":
    "DOF follows its daily index. PLATIICA and SNICE follow the configured records or pages. SIDOF tracks a known document. Daily DOF coverage still needs validation.",
  "Guardar un tema solo crea un acceso rápido a la búsqueda del archivo. El portal todavía no determina automáticamente qué norma aplica a cada producto JE ni envía avisos por correo.":
    "Saving a topic creates a shortcut to search the archive. The portal does not yet automatically determine which standard applies to each JE product or send email notifications.",
  "Español / English cambia todos los controles y la guía. Los documentos oficiales se conservan en el español original; no hay una traducción automática del texto legal.":
    "Español / English changes all controls and this guide. Official documents remain in their original Spanish; legal text is not automatically translated.",
  "Ver qué páginas se consultan": "See which pages are checked",
  "UN EJEMPLO DE USO": "AN EXAMPLE",
  "Si quieres revisar una norma: consulta las fuentes, busca su identificador —por ejemplo, NOM-014-ENER— y abre los resultados. Si la búsqueda está vacía, revisa el estado y las páginas de las fuentes antes de concluir que no hay publicaciones.":
    "To look up a standard, check the sources, search for its identifier — for example, NOM-014-ENER — and open the results. If the search is empty, check the sources' status and configured pages before concluding there are no publications.",
  "Ir a buscar publicaciones": "Go to publication search",
  "SIDOF · documento de referencia": "SIDOF · reference document",
  "No se pudieron consultar las fuentes.": "The sources could not be checked.",
  "La revisión tiene fuentes pendientes.":
    "Some sources still need to be checked.",
  "{failed} de {total} fuentes activas tienen una revisión incompleta. No se ha confirmado la ausencia de novedades.":
    "{failed} of {total} active sources have an incomplete check. The absence of updates has not been confirmed.",
  "Ver qué pasó": "See what happened",
  "Normativa mexicana,": "Mexican standards,",
  "a primera vista.": "at first glance.",
  "Consulta las fuentes, lee lo que se publicó y comprueba qué cambió en los documentos guardados.":
    "Check the sources, read what was published and see what changed in the saved documents.",
  "La revisión necesita atención": "The check needs attention",
  "Cómo empezar": "Getting started",
  "EMPIEZA AQUÍ": "START HERE",
  "Busca una publicación": "Find a publication",
  "Entiende los resultados": "Understand the results",
  "Aún no hay documentos recuperados.": "No documents have been retrieved yet.",
  "Las consultas a los sitios oficiales fallaron. Abre Estado de las fuentes para ver las direcciones y el motivo; puedes visitar cada sitio directamente.":
    "Checks of the official websites failed. Open Source status to see the addresses and the reason; you can visit each website directly.",
  "Revisar las conexiones": "Check the connections",
  "Busca en los documentos ya recuperados. No activa notificaciones.":
    "Searches documents already retrieved. Does not turn on notifications.",
  "¿Se pudo revisar?": "Did the check work?",
  "Detalle original del error": "Original error details (Spanish)",
  "Nota original del documento": "Original document note (Spanish)",
  "Revisión fallida; novedades sin confirmar":
    "Check failed; updates unconfirmed",
  "No se pudo conectar con el sitio oficial. Comprueba que esta computadora o servidor tenga acceso a esa dirección; después vuelve a consultar.":
    "Could not connect to the official website. Check that this computer or server can access that address, then try again.",
  "El sitio no permitió verificar sus reglas de consulta automática. Esta revisión quedó pendiente.":
    "The site's automated access rules could not be verified. This check remains pending.",
  "El sitio rechazó o limitó la consulta. Intenta de nuevo más tarde.":
    "The website rejected or limited the request. Please try again later.",
  "La revisión no pudo completarse. Abre la fuente oficial para comprobarla y consulta el detalle del error.":
    "The check could not be completed. Open the official source to check it directly and see the error details.",
  "El boletín": "The bulletin",
  "Explorar publicaciones": "Explore publications",
  "Las fuentes": "The sources",
  "Proyecto de norma": "Draft standard",
  "Norma definitiva": "Final standard",
  Modificación: "Amendment",
  Cancelación: "Cancellation",
  Acuerdo: "Agreement",
  Aviso: "Notice",
  Publicación: "Publication",
  "En espera": "Queued",
  Consultando: "Checking",
  Completada: "Completed",
  "Con error": "Failed",
  "Consulta parcial": "Partial check",
  Interrumpida: "Interrupted",
  Pendiente: "Pending",
  "Fecha por confirmar": "Date to be confirmed",
  "ARCHIVO / LECTURA": "ARCHIVE / READING",
  "Cerrar lectura": "Close reader",
  "Cambio detectado": "Change detected",
  "Muestra sintética": "Synthetic sample",
  "Sin fecha oficial confirmada": "Official date unconfirmed",
  "Detectado {date}": "Detected {date}",
  "Leer {title}": "Read {title}",
  "No se pudo completar la solicitud. Intenta de nuevo.":
    "The request could not be completed. Please try again.",
  "No se pudo conectar con el portal.": "Could not connect to the portal.",
  "Consultando las fuentes. Los resultados aparecerán aquí al terminar.":
    "Checking the sources. Results will appear here when the check is complete.",
  "Configura una fuente para comenzar.": "Configure a source to get started.",
  "Consulta en cola. Inicia el portal con MONITOR_ENABLED=true para procesarla.":
    "The check is queued. Start the portal with MONITOR_ENABLED=true to process it.",
  "No fue posible recuperar esta copia.":
    "This saved copy could not be retrieved.",
  "Seguimiento actualizado.": "Monitoring settings updated.",
  "Ir al contenido": "Skip to content",
  "MÉXICO / OBSERVATORIO REGULATORIO": "MEXICO / REGULATORY WATCH",
  "NOM Monitor, inicio": "NOM Monitor, home",
  "UN BOLETÍN DE JOHNSON ELECTRIC": "A JOHNSON ELECTRIC BULLETIN",
  "Lo que se publica.": "What is published.",
  "Lo que cambia.": "What is changing.",
  "NOM Monitor / México": "NOM Monitor / Mexico",
  "Consultando…": "Checking…",
  "Solicitando…": "Requesting…",
  "Consultar fuentes": "Check sources",
  Idioma: "Language",
  "Navegación principal": "Main navigation",
  "EDICIÓN LOCAL": "LOCAL EDITION",
  "CONSULTA ABIERTA": "OPEN ACCESS",
  "Volver a intentar": "Try again",
  "Esta instalación tiene acceso Microsoft habilitado.":
    "Microsoft sign-in is enabled for this installation.",
  "Iniciar sesión": "Sign in",
  "EL BOLETÍN": "THE BULLETIN",
  "Las normas cambian.": "Standards change.",
  "Sigue el movimiento.": "Stay in the know.",
  "Publicaciones oficiales, cambios y referencias para seguir la normativa mexicana desde un solo lugar.":
    "Official publications, changes and references to follow Mexican standards in one place.",
  "Revisión en curso": "Check in progress",
  "Última consulta correcta: {date}": "Last successful check: {date}",
  "La primera consulta está pendiente": "The first check is pending",
  "LA HEMEROTECA": "THE REFERENCE LIBRARY",
  "Busca por título, norma o palabras del documento. Cada publicación conserva su fuente y sus versiones.":
    "Search by title, standard or words in the document. Every publication keeps its source and version history.",
  "Buscar publicaciones": "Search publications",
  "Busca una NOM, un tema o una palabra…":
    "Search for a NOM, a topic or a keyword…",
  "Limpiar búsqueda": "Clear search",
  "ARCHIVO OFICIAL": "OFFICIAL ARCHIVE",
  "Filtrar por fuente": "Filter by source",
  "Todas las fuentes": "All sources",
  referencia: "reference",
  "Tu selección": "Your selection",
  "En portada": "In this edition",
  "El archivo": "The archive",
  "Cargando…": "Loading…",
  "{count} publicación": "{count} publication",
  "{count} publicaciones": "{count} publications",
  "Fecha oficial": "Official date",
  "Periodo de publicación": "Publication period",
  "Todas las fechas": "All dates",
  "Últimos 7 días": "Last 7 days",
  "Últimos 30 días": "Last 30 days",
  Tipo: "Type",
  "Tipo de publicación": "Publication type",
  "Todos los tipos": "All types",
  "Con cambios": "With changes",
  "Quitar filtros": "Clear filters",
  "Ninguna publicación coincide.": "No matching publications.",
  "Tu primera edición comienza aquí.": "Your first edition starts here.",
  "Prueba con otro tema o amplía el periodo. Las publicaciones sin fecha oficial no aparecen al filtrar por últimos días.":
    "Try another topic or a wider period. Publications without an official date are excluded from recent-date filters.",
  "Consulta las fuentes para empezar a reunir publicaciones oficiales. Aquí aparecerán sus títulos, fechas y cambios, sin datos de ejemplo.":
    "Check the sources to start collecting official publications. Their titles, dates and changes will appear here once retrieved.",
  "Ver todas las publicaciones": "View all publications",
  "Preparar el boletín": "Prepare the bulletin",
  MÉXICO: "MEXICO",
  "PRIMERA LECTURA": "FIRST READING",
  "Publicado {date}": "Published {date}",
  "Fecha oficial por confirmar": "Official date to be confirmed",
  "Abrir documento": "Open document",
  Anterior: "Previous",
  Siguiente: "Next",
  "Página {page} de {total}": "Page {page} of {total}",
  "Orden por fecha de publicación. Cuando la fecha oficial falta, se indica expresamente. Una detección de hoy puede corresponder a un documento anterior.":
    "Ordered by publication date. Missing official dates are marked explicitly. A document detected today may have been published earlier.",
  "01 / TU RADAR": "01 / YOUR RADAR",
  "Los temas": "The topics",
  "que te importan.": "that matter to you.",
  "Guarda palabras para volver a buscarlas con un clic.":
    "Save keywords to search for them again with one click.",
  "Nuevo tema de seguimiento": "New topic to follow",
  "Añade un tema…": "Add a topic…",
  "Guardar tema": "Save topic",
  "Quitar tema {topic}": "Remove topic {topic}",
  "Tu lista se guarda en este navegador.":
    "Your list is saved in this browser.",
  "02 / AL CIERRE": "02 / AT A GLANCE",
  "Las fuentes,": "The sources,",
  "a la vista.": "in plain sight.",
  "Requiere atención": "Needs attention",
  "Consulta correcta": "Successful check",
  "Sin consultar": "Not checked",
  "Primera revisión pendiente": "First check pending",
  "Ver cobertura y consultas": "See coverage and checks",
  "03 / EN EL CALENDARIO": "03 / ON THE CALENDAR",
  "Próximas fechas.": "Upcoming dates.",
  "DE DÓNDE VIENE LA INFORMACIÓN": "WHERE THE INFORMATION COMES FROM",
  "Documentos con origen": "Documents with a source",
  "El boletín sigue las páginas configuradas en estas fuentes. Aquí puedes ver cuándo se consultaron y si una revisión quedó incompleta.":
    "The bulletin follows the pages configured for these sources. See when they were checked and whether a check was incomplete.",
  "Consulta automática activa mientras el servidor esté encendido.":
    "Automatic checks are active while the server is running.",
  "La consulta automática está desactivada en esta ejecución.":
    "Automatic checks are turned off for this session.",
  "La frecuencia se indica por fuente.":
    "The frequency is listed for each source.",
  "Consulta incompleta": "Incomplete check",
  "Inventario oficial de fichas NOM. La carga inicial y las actualizaciones se procesan por lotes.":
    "Official inventory of NOM records. The initial import and updates are processed in batches.",
  "Publicaciones oficiales SIDOF por fecha. Se guardan el texto disponible y una copia del original.":
    "Official SIDOF publications by date. Available text and a copy of the original are saved.",
  "Fichas pendientes de revisar": "Records still to check",
  "Catálogo Mexicano de Normas · PLATIICA": "Mexican Standards Catalogue · PLATIICA",
  "Norma vigente": "Current standard",
  "NOM no vigente": "Non-current NOM",
  "Última consulta correcta": "Last successful check",
  "Pendiente de consultar": "Check pending",
  "Ver motivo de la consulta incompleta": "See why the check was incomplete",
  "Editar seguimiento": "Edit monitoring settings",
  "Páginas a consultar, una por línea": "Pages to check, one per line",
  "Frecuencia en horas": "Frequency in hours",
  "Consultar desde": "Check from",
  "Referencia esperada, opcional": "Expected reference, optional",
  "Revisión automática de esta fuente": "Check this source automatically",
  "Guardar seguimiento": "Save settings",
  "Último intento": "Last attempt",
  Frecuencia: "Frequency",
  "Cada {hours} h": "Every {hours} h",
  Manual: "Manual",
  "Registro de consultas": "Check history",
  "Últimas ejecuciones": "Recent runs",
  "Todavía no se ha solicitado una consulta.":
    "No check has been requested yet.",
  Fuente: "Source",
  "{new} nuevos · {changes} cambios": "{new} new · {changes} changes",
  " · {count} errores": " · {count} errors",
  Retomar: "Resume",
  "Un punto de consulta para la normativa mexicana.":
    "A reference point for Mexican standards.",
  "Ver muestras sintéticas": "Show synthetic samples",
  "Cerrar sesión": "Sign out",
  "PUBLICACIÓN OFICIAL": "OFFICIAL PUBLICATION",
  "Sin fecha confirmada": "Date unconfirmed",
  "DETECTADO EN EL BOLETÍN": "DETECTED IN THE BULLETIN",
  "Abrir en la fuente oficial": "Open the official source",
  "Documento conservado": "Saved document",
  "{count} versión": "{count} version",
  "{count} versiones": "{count} versions",
  "Versión {number}": "Version {number}",
  "Copia consultada el {date}. El texto se presenta tal como fue extraído de la fuente.":
    "Copy retrieved on {date}. The text is shown as extracted from the source.",
  "La fuente no ofreció texto extraíble. Abre el documento oficial o descarga la copia.":
    "The source did not provide extractable text. Open the official document or download the saved copy.",
  "Descargar copia consultada": "Download saved copy",
  "Todavía no hay una copia del documento disponible.":
    "No saved copy is available yet.",
  "Texto oficial en español": "Official text in Spanish",
  "La interfaz está en inglés. Los títulos y documentos oficiales se muestran en el español de la fuente.":
    "The interface is in English. Official titles and documents are shown in their original Spanish.",
  "Notas originales de la fuente": "Original source notes (Spanish)",
  "coverage.dof":
    "Daily DOF index: discovers linked notes and editions. Live daily coverage still needs verification.",
  "coverage.platiica":
    "Tracks the configured PLATIICA standard pages and their document links. Does not discover the complete catalogue.",
  "coverage.platiica_catalog":
    "Discovers NOM records through the official PLATIICA sitemaps and incrementally refreshes pages whose lastmod changed. Completion applies to the discovered sitemap queue; it does not certify legal applicability.",
  "coverage.snice":
    "Tracks the configured SNICE regulatory pages and their links. Does not automatically consolidate Annex 2.4.1.",
  "coverage.sidof":
    "Tracks a known SIDOF reference document. Does not replace discovery through the daily DOF index.",
  "coverage.demo":
    "Synthetic samples for practising with the portal. This source does not retrieve official publications.",
};
type Translator = (
  message: string,
  params?: Record<string, string | number>,
) => string;
type Locale = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: Translator;
  format: (value?: string | null, time?: boolean) => string;
};
const Context = createContext<Locale | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => {
    const requested = new URLSearchParams(location.search).get("lang");
    if (requested === "en" || requested === "es") return requested;
    try {
      return localStorage.getItem("nom-language") === "en" ? "en" : "es";
    } catch {
      return "es";
    }
  });
  useEffect(() => {
    document.documentElement.lang = language;
    document.title =
      language === "en"
        ? "norma. — The NOM Monitor bulletin"
        : "norma. — El boletín de NOM Monitor";
    try {
      localStorage.setItem("nom-language", language);
    } catch {
      /* Optional preference storage. */
    }
    const url = new URL(location.href);
    url.searchParams.set("lang", language);
    history.replaceState(null, "", url);
  }, [language]);
  const t: Translator = useCallback(
    (message, params = {}) => {
      const translated =
        language === "en" ? english[message] || message : message;
      return translated.replace(/\{(\w+)\}/g, (match, key) =>
        String(params[key] ?? match),
      );
    },
    [language],
  );
  const format = useCallback(
    (value?: string | null, time = false) => {
      if (!value) return t("Pendiente");
      const date = new Date(
        value.length === 10
          ? `${value}T12:00:00Z`
          : /Z$|[+-]\d\d:\d\d$/.test(value)
            ? value
            : `${value}Z`,
      );
      if (Number.isNaN(date.valueOf())) return t("Fecha por confirmar");
      return new Intl.DateTimeFormat(language === "en" ? "en-US" : "es-MX", {
        timeZone: value.length === 10 ? "UTC" : "America/Mexico_City",
        day: "numeric",
        month: "short",
        year: "numeric",
        ...(time ? { hour: "2-digit", minute: "2-digit" } : {}),
      }).format(date);
    },
    [language, t],
  );
  return (
    <Context.Provider value={{ language, setLanguage, t, format }}>
      {children}
    </Context.Provider>
  );
}

export function useLanguage() {
  const value = useContext(Context);
  if (!value) throw new Error("Missing language provider");
  return value;
}
