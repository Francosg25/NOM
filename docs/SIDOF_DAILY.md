# SIDOF diario · versión 0.4.0

SIDOF es el canal principal para descubrir publicaciones por fecha. Se mantiene
la instalación sencilla: un servidor FastAPI, SQLite y archivos locales. No
requiere Foundry ni nuevos servicios Azure.

## Flujo del portal

1. Ejecuta `PREPARAR_LOCAL.cmd` y después `INICIAR_LOCAL.cmd` desde el ZIP
   actualizado. Cierra antes el servidor anterior. Abre http://127.0.0.1:8000.
2. La primera revisión SIDOF cubre hoy y los seis días anteriores, empezando por
   los más recientes. Por defecto se programa cada hora mientras el servidor
   esté activo. El botón **Consultar fuentes** vuelve a solicitar siete días.
3. Busca una NOM o abre una publicación. El lector muestra texto, fecha oficial,
   versiones, enlace oficial y descarga de la respuesta JSON original.
4. En **Estado de las fuentes → Registro de consultas → Ver revisión diaria**
   aparecen los días terminados, notas examinadas, IDs seleccionados y vínculos
   a referencias sin clasificación. Los errores mantienen sus fechas y colas
   pendientes; no se presentan como ausencia de novedades.

Los controles y este recorrido en la guía del portal están disponibles en
**Español / English**. Los documentos oficiales conservan su español original.
La primera consulta puede tardar varios minutos sin impedir el uso del portal.

## Contrato de la fuente

Los manuales SIDOF v1.0 de diciembre de 2018 describen entornos de ejemplo
`sidofqa.segob.gob.mx`. La integración usa el dominio de producción, comprobado
con respuestas reales y HTTPS verificado:

| Operación | URL bajo `https://sidof.segob.gob.mx/dof/sidof` |
| --- | --- |
| Ediciones por fecha | `/diarios/porFecha/DD-MM-YYYY` |
| Notas por fecha | `/notas/DD-MM-YYYY` |
| Detalle original | `/notas/nota/CODIGO` |
| Declaraciones de días sin publicación, si están disponibles | `/diarios/AAAA` → `FechasSinPublicacion` |

Se validan `messageCode=200`, `response=OK`, las listas matutina, vespertina y
extraordinaria y la correspondencia entre código, fecha y diario. Una respuesta
HTML inesperada, una edición sin notas o una identidad contradictoria deja
pendiente esa fecha. No se interpreta un HTTP 404 como día sin publicación.

Se seleccionan títulos con NOM, Norma Oficial Mexicana, Anexo 2.4.1 o reglas y
criterios de comercio exterior, incluidos proyectos, modificaciones y
cancelaciones. No se presenta una NMX como NOM. También se consulta el detalle
de cada nota sin título. Si no hay título/encabezado o texto suficiente, queda
una referencia pendiente con enlace y huella SHA-256. Una NOM identificada sin
texto queda visible como publicación pendiente de procesamiento.

Las publicaciones seleccionadas conservan el JSON original y el texto extraído
de `Nota.cadenaContenido`. La descarga es `.json`. Los PDF de diario completo
no se presentan como PDF individual de una NOM. No se incluye OCR ni traducción
automática del texto legal.

## Continuidad y actualizaciones

Cada lote limita peticiones y documentos. El cursor conserva días y detalles
pendientes; una fecha fallida no impide consultar otras fechas. Se procesan
primero las más recientes. Los límites sin fallo continúan automáticamente.
Los errores se reintentan con la frecuencia configurada; si quedan fechas aún
sin intentar, se procesan antes de esperar. Un fallo histórico no congela las
consultas futuras: el siguiente ciclo revisa la ventana de siete días y
conserva los trabajos anteriores para inspección o reanudación explícita.

Tras completar un intervalo, la programación consulta hoy y ayer para revisar
nuevas ediciones o cambios recientes. Las correcciones anteriores a esa ventana
requieren una consulta manual ampliada por API/CLI. La repetición no crea una
versión si el contenido y título guardados no cambiaron. La unicidad se aplica
por fuente e identificador, no entre conectores distintos.

La actualización automática sustituye únicamente el SIDOF de referencia
original si sus URLs y referencias esperadas no se modificaron. Conserva su
ID, documentos y decisiones; respeta fuentes desactivadas y ajustes propios.
No reemplaza un trabajo activo ni una configuración personalizada.

## Prueba real del 3 de noviembre de 2026

La comprobación se ejecutó contra producción con el cliente real, sin inyectar
respuestas sintéticas, en SQLite y un almacén de evidencia aislados. Se respetó
robots y se mantuvo TLS verificado.

| Comprobación | Resultado |
| --- | --- |
| 2 de noviembre | Diario `330565`, 35 notas; seleccionada `DOF:5802721` / **NOM-EM-023-SE-2026** |
| Texto y evidencia | JSON original de 397 958 bytes; texto extraído de 58 945 caracteres; fecha oficial 2026-11-02 |
| Repetición del 2 de noviembre | Mismo inventario y evidencia íntegra; cero versiones adicionales |
| Ventana 28 de octubre–3 de noviembre | Cinco publicaciones seleccionadas: `5802362`, `5802465`, `5802604`, `5802610`, `5802721` |
| Días examinados con índice completo | 28, 29 y 30 de octubre; 2 y 3 de noviembre: 523 notas en total |
| Referencias sin título/texto suficiente | 51 en esos cinco días; ocho corresponden al 2 de noviembre |
| 31 de octubre y 1 de noviembre | Edición por fecha devuelve HTTP 404. El calendario anual consultado no declara esas fechas sin publicación; permanecen pendientes |

La consulta del 2 de noviembre aprueba persistencia, integridad e inventario
esperado de la NOM conocida, pero **no aprueba cobertura integral** por las ocho
referencias pendientes. La ventana de siete días también conserva errores de
las dos fechas citadas. Estos resultados no prueban aplicabilidad a productos JE.

El ZIP no incorpora la base ni documentos descargados de esta validación. En una
instalación nueva, el portal obtiene su propio contenido de las fuentes reales.

## English

SIDOF daily discovery uses the verified production API. Initial and manual
checks cover the last seven days, newest first; scheduled checks run hourly
while the server is active. Open **Source status → View daily check** to inspect
checked notes, selected publication IDs and unresolved references. Downloaded
copies contain the original JSON; official text remains in Spanish.

The live test retrieved NOM-EM-023-SE-2026 and repeated it without adding a
duplicate version. Eight untitled, textless references remain unresolved on
November 2. Two dates in the seven-day window returned HTTP 404; they remain
pending and do not prevent valid publications from other dates being saved.
Complete NOM coverage and product applicability have not been established.
