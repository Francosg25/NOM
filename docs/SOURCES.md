# Fuentes y cobertura de recopilación

Esta versión propone relaciones para revisión humana; no determina aplicabilidad
legal ni autorización de importación. «Completa» en una ejecución significa que
se agotó la cola de esa consulta configurada. No significa cobertura normativa completa.

## Estado de validación

El 2 de noviembre de 2026 el entorno negó la conexión HTTPS a
`www.dof.gob.mx/robots.txt`: el proxy devolvió `CONNECT 403 Forbidden` (Envoy).
No hubo respuesta del servidor oficial y no se intentó eludir la restricción.
Las pruebas del parser usan muestras sintéticas identificadas como tales; no son
capturas descargadas de publicaciones oficiales. La validación en vivo de DOF,
PLATIICA y SNICE queda **pendiente**. Tampoco se tuvo acceso al archivo
`NOM_Monitor_Piloto.zip`; no se afirma haber revisado sus tres URLs.

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

## PLATIICA

Seguimiento de **fichas/documentos concretos** configurados por el administrador
en `platiica.economia.gob.mx`. No hay descubrimiento global de nuevas fichas.
La URL normalizada es la identidad provisional cuando no existe un identificador
oficial extraíble; no se presenta ese identificador técnico como número de NOM.
Una portada sin ruta no se admite como sustituto de una ficha. Deben configurarse
las URLs reales del piloto o fichas verificadas antes de usar este canal.

## SNICE

Seguimiento de **publicaciones concretas HTML o PDF** en `www.snice.gob.mx` o
`snice.gob.mx`. No se implementó un feed no verificado ni se afirma descubrir
todas sus novedades. No se considera la portada un inventario de publicaciones.
Se deben registrar enlaces oficiales específicos y confirmar el canal autorizado
de novedades antes de ampliar el descubrimiento. Los periodos registrados para
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
