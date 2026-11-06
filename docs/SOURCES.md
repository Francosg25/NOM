# Fuentes y cobertura de recopilación

El seguimiento combina el Catálogo Mexicano de Normas de PLATIICA con publicaciones diarias de SIDOF. PLATIICA proporciona el inventario de fichas; SIDOF detecta publicaciones y cambios del DOF. Las fuentes antiguas DOF HTML, PLATIICA de fichas individuales y SNICE se desactivan sin borrar sus registros históricos. El diagnóstico de red consulta SIDOF; no valida la cobertura del catálogo PLATIICA.

Esta versión propone relaciones para revisión humana; no determina aplicabilidad
legal ni autorización de importación. «Completa» en una ejecución significa que
se agotó la cola de esa consulta configurada. No significa cobertura normativa completa.

## Estado de validación

La versión 0.4.0 incorpora la API diaria SIDOF como canal principal. La consulta
real del 3 de noviembre recuperó **DOF:5802721 / NOM-EM-023-SE-2026**, publicada
el 2 de noviembre. Se consultaron las 35 notas de ese día: una seleccionada y
ocho referencias sin título ni texto pendientes de revisión. La repetición y
persistencia se documentan en [SIDOF diario](SIDOF_DAILY.md). No se declara
cobertura integral mientras existan referencias sin clasificar.

### Antecedente del piloto de referencia

El 2 de noviembre de 2026 se consultó el ZIP del piloto y el programa descargó
las tres URLs concretas de SIDOF, PLATIICA y SNICE. Se guardaron las capturas
originales en el almacén de evidencia, se verificó su SHA-256 al recuperarlas y se repitió la consulta sin
crear versiones duplicadas. Los informes están en [aceptación](PILOT_ACCEPTANCE.md).
El índice diario DOF sigue pendiente: robots.txt devolvió HTTP 503, no se eludió
ese fallo y el resultado global no se marca como aprobado. Las muestras sintéticas
y los extractos de capturas oficiales están separados en los tests. En el
repositorio público estos extractos están reducidos y usan HTML mínimo preparado
para pruebas; no incluyen los metadatos ni contactos de las respuestas íntegras.

Antes de habilitar una fuente en producción se deben permitir los destinos
oficiales necesarios, verificar sus condiciones de uso y robots, guardar muestras
obtenidas con permiso y contrastar el resultado con una revisión manual de un
periodo conocido, incluidas ediciones extraordinarias y días sin publicaciones.
No se inventaron APIs ni se presentó una portada como inventario completo.

## DOF / SIDOF

El adaptador DOF construye consultas de índices diarios HTML en
`https://www.dof.gob.mx/index.php?year=AAAA&month=MM&day=DD` para el periodo
solicitado. Reconoce enlaces explícitos a `nota_detalle.php?codigo=...`, conserva
el identificador `DOF:codigo` y normaliza parámetros de navegación para evitar
duplicados. Recorre los enlaces de índices del mismo día, páginas y ediciones
adicionales cuando están publicados como enlaces HTML. El contenido se toma de
`#DivDetalle`, `.DetaDoc`, `article` o `main`, con extracción general marcada si
es necesario. No se interpretan scripts para descubrir enlaces ocultos.

La configuración DOF admite un único índice base; no se ignoran URLs adicionales.
Las ediciones y páginas del mismo día se descubren desde ese índice.

Limitaciones concretas: este formato requiere validación con el sitio vigente;
no garantiza ediciones no enlazadas, publicaciones detrás de JavaScript, anexos
no enlazados, sistemas alternos, correcciones históricas fuera del periodo ni
equivalencia con SIDOF. El hostname de SIDOF está permitido, pero no se presume
que su estructura sea compatible: un índice SIDOF no se acepta como índice DOF.
Un índice sin notas y sin texto explícito de ausencia se considera estructura
desconocida y deja el periodo pendiente, nunca «sin cambios».

## Catálogo NOM de PLATIICA

El conector `platiica_catalog` consulta el índice oficial
`/normalizacion/wp-sitemap.xml`, sus sitemaps de entradas y las fichas cuya ruta
es `/normalizacion/nom-.../`. Conserva también fichas no vigentes para mantener
el historial; la búsqueda de producto solo incluye fichas cuyo estado explícito
es `Vigente`. Cada versión guarda la clave, título, estado, fechas y el campo
oficial de producto/servicio, además del texto, enlaces y copia HTML de evidencia.

La primera carga es una cola durable por lotes. Se reanuda tras interrupciones y
los errores quedan pendientes, no se confunden con una ficha ausente. En las
revisiones posteriores se vuelven a descargar las fichas cuyo `lastmod` del
sitemap cambió; si falta esa fecha, la ficha se vuelve a revisar. Una pasada
completa significa solamente que se agotó la cola de las fichas detectadas en
los sitemaps consultados. No demuestra que PLATIICA incluya todas las NOM ni que
cada estado esté correctamente informado. Antes de declarar completa la carga,
contrastar independientemente el conjunto y el conteo con el catálogo oficial y
resolver las fichas con estado o ámbito de producto incompleto.

La fracción arancelaria no se trata como una relación oficial con una NOM:
PLATIICA no proporciona esa tabla en la ficha. La búsqueda ofrece coincidencias
textuales explicables y no determina aplicabilidad ni clasificación legal.

## PLATIICA de fichas concretas (conector anterior)

Seguimiento de **fichas/documentos concretos** configurados por el administrador
en `platiica.economia.gob.mx`. No hay descubrimiento global de nuevas fichas.
La URL normalizada es la identidad provisional cuando no existe un identificador
oficial extraíble; no se presenta ese identificador técnico como número de NOM.
Una portada sin ruta no se admite como sustituto de una ficha. Este conector anterior se conserva solo para historial; el inventario actual se
obtiene desde `platiica_catalog`.

## SNICE

Seguimiento de **publicaciones concretas HTML o PDF** en `www.snice.gob.mx` o
`snice.gob.mx`. No se implementó un feed no verificado ni se afirma descubrir
todas sus novedades. No se considera la portada un inventario de publicaciones.
Se configura la página de normatividad del piloto, que no equivale a descargar el Anexo 2.4.1. Registrar enlaces específicos y confirmar un canal de novedades antes de ampliar el descubrimiento. Los periodos registrados para
estos monitores indican cuándo se solicitó la comprobación, no una búsqueda
retrospectiva garantizada del portal.

## Fechas, evidencia y límites

- Consultas y registros de trabajos se conservan en UTC; la interfaz los muestra
  en `America/Mexico_City`.
- La publicación se extrae exclusivamente de campos de fecha explícitos o del
  rótulo `DOF: DD/MM/AAAA`. No se sustituye por detección ni por fechas arbitrarias
  del texto. La entrada en vigor requiere verificación humana y evidencia; los
  conectores no la infieren.
- Los bytes recuperados se entregan al almacén de evidencia. El texto útil se
  compara con la última versión, de modo que una reversión A→B→A conserva tres
  versiones en el servicio de persistencia, aunque A haya aparecido antes.
- Descarga máxima: 12 MiB; PDF: extracción de hasta 150 páginas. PDF escaneado,
  ilegible o parcial genera un pendiente explícito. No se incluye OCR automático.
- Timeout de conexión 10 s, operación HTTP 20 s; hasta tres intentos ante fallos
  de red/timeout o HTTP 429/502/503/504, con espera acotada. Cada lote limita
  documentos y peticiones. Un límite devuelve cola de continuación, no éxito
  completo. Los errores conservan los documentos ya procesados y la URL fallida.
- Se conserva el día/periodo y las colas pendientes. Reanudar un cursor exige el
  mismo tipo de fuente, URLs y periodo. Si cambia la configuración, se exige
  reiniciar el periodo completo para no omitir documentos. Una revisión retrospectiva usa un periodo nuevo;
  sólo se marcan completos los días cuyo índice y enlaces se agotaron.

## Acceso responsable y seguridad

`SafeFetcher` requiere TLS verificado, HTTPS, hosts oficiales exactos, puerto 443,
sin credenciales en URL, sin direcciones privadas y sin saltar de una agencia a
otra por redirección. Comprueba DNS público inmediatamente antes de cada petición.
Se recomienda además restringir salida a estos hosts en Azure y en el proxy: un
proxy puede resolver nombres por su cuenta. No hay un campo para habilitar hosts
arbitrarios desde la API. Cada destino redirigido vuelve a validarse.

Se consulta `robots.txt` y se respeta `Disallow` y `Crawl-delay`. HTTP 404 en robots
se interpreta como reglas no publicadas (RFC 9309); cualquier otro estado distinto
de 200 suspende la consulta. Una demora mayor a 30 s exige revisar programación.
Se aplica una separación mínima de un segundo entre peticiones y no se intenta
sortear CAPTCHA, autenticación o bloqueos. No se desactiva TLS. `robots.txt` no
sustituye la comprobación de condiciones de uso por el administrador.

Para habilitar validación en vivo se requieren, según URLs configuradas:
`www.dof.gob.mx`, `dof.gob.mx`, `sidof.segob.gob.mx`,
`platiica.economia.gob.mx`, `www.snice.gob.mx`, `snice.gob.mx`.
Agregar dominios al borrador no aplica permisos a la instancia en ejecución.

## SIDOF diario, documentos conocidos y proxy

El conector `sidof` admite dos configuraciones. La predeterminada es una única
base `https://sidof.segob.gob.mx/dof/sidof`, con descubrimiento por fecha. Usa
`diarios/porFecha/DD-MM-YYYY`, `notas/DD-MM-YYYY` y `notas/nota/CODIGO`.
Para respuestas completamente vacías contrasta `diarios/AAAA` y exige una fecha
declarada sin publicación. Todas las ediciones declaradas deben aportar notas.
Se comprueban códigos, fechas y pertenencia a diario antes de guardar datos.

Selecciona títulos con NOM, Norma Oficial Mexicana, Anexo 2.4.1 o reglas y
criterios de comercio exterior. Las NMX no se incluyen automáticamente como
NOM. Las notas sin título se consultan individualmente; si el detalle tampoco
permite clasificarlas quedan pendientes con vínculo oficial y hash. Los
errores y límites mantienen un cursor de continuación, sin saltar el detalle
fallido. La evidencia de cada publicación seleccionada es el JSON íntegro
recuperado, no un PDF individual inventado.

La configuración con URLs `notas/docFuente/...` conserva el monitor de documentos
conocidos. El documento piloto `DOF:5758923` permanece almacenado al actualizar
la fuente predeterminada; no se cambia la configuración de un monitor personalizado.

Las fuentes conocidas incluyen referencias esperadas. Si una página deja de
contenerlas, el trabajador conserva el fallo y no sustituye la evidencia válida
por una portada u otra respuesta. Las referencias se incluyen en la instantánea
del trabajo y en el control de reanudación.

Con `SOURCE_DNS_MODE=local` se comprueba DNS local público. `proxy` requiere
un proxy configurado en el entorno que resuelva y controle destinos. Los hosts,
TLS y redirecciones siguen restringidos. Véase PILOT_ACCEPTANCE.md.
