# Boletín 0.7.0

## Resumen de visitas

Novedades muestra las publicaciones de SIDOF incorporadas al portal, las que
tienen versiones guardadas nuevas y las fichas importadas de PLATIICA desde el
punto registrado en la visita anterior. Cada publicación se cuenta una vez;
una publicación nueva con varias copias sigue siendo una incorporación y no se
duplica en el contador de versiones nuevas. Las fichas antiguas importadas hoy
se identifican como incorporaciones al catálogo, sin presentarlas como normas
publicadas hoy.

La primera vez comienza el seguimiento desde el estado actual y no convierte
todo el histórico en novedades. Los botones del resumen filtran la lista por
el conjunto correspondiente, incluyendo publicaciones antiguas detectadas ahora.
Quitar la selección restaura el listado completo. El resumen mantiene su punto
de inicio al cambiar de pestaña dentro de la misma visita.

El punto de lectura usa el identificador de la última copia guardada y su hash,
junto con la fecha de visita. Se conserva en localStorage por navegador/origen,
sesión de identidad y modo real/demostración. No requiere iniciar sesión en el
modo portal. Marcar el resumen como revisado adelanta el punto de lectura; no
modifica documentos ni decisiones compartidas. Si el punto ya no existe o su
hash no coincide, se reinicia el seguimiento. Si el navegador bloquea ese
almacenamiento, se explica que el resumen dura solamente la visita actual.

Se consulta al abrir Novedades y cada minuto mientras esa vista está visible.
La consulta se pausa durante la lectura y al inspeccionar una ejecución. El
resumen usa metadatos: no carga los cuerpos completos de las NOM ni bloquea la
lista de publicaciones. Presenta la última consulta SIDOF completada con su
periodo, separada del estado de la ejecución más reciente, que puede estar en
curso o ser parcial. Un fallo del resumen mantiene disponibles las publicaciones.

## Ficha de publicación

La ventana de lectura muestra clave/identificador, estado informado por la
fuente, fecha oficial, entrada en vigor verificada, fuente y fecha de la copia
seleccionada. La ficha aparece cuando termina de cargar la información, evitando
presentar campos aún no recibidos como fechas faltantes.

El tipo «norma definitiva» no se convierte automáticamente en «vigente». Una
fecha de entrada en vigor se presenta como verificada cuando tiene fecha,
indicador de verificación y evidencia vigente para la copia actual. La evidencia
se puede desplegar. Cuando no se cuenta con esos datos se indica expresamente,
sin inferir una fecha del año incluido en la clave NOM. Los datos de la ficha
describen el registro actual; la fecha de la copia sigue la versión seleccionada.

## Comparación de versiones

Comparar versiones abre una vista de texto anterior/actual con eliminaciones
y adiciones resaltadas. Se elige una copia anterior a la versión seleccionada.
No se descarga ni compara automáticamente todo el histórico al abrir una NOM.

La comparación distingue texto idéntico, equivalencia tras unificar espacios y
caracteres Unicode equivalentes, cambios de texto, falta de texto extraíble y
documentos que superan el límite de comparación. Se conservan diferencias en
números, signos, acentos y mayúsculas. La equivalencia de texto extraído no
prueba que imágenes, tablas o el formato de las copias originales sean idénticos.
La vista ofrece ambas versiones y el enlace/copia original para su comprobación.

El servidor devuelve 12 bloques por página, con un máximo solicitado de 20.
La comparación admite hasta un millón de caracteres por copia y 3000 bloques.
Los bloques largos se dividen y el resaltado de palabras tiene un presupuesto
de trabajo y 160 segmentos como máximo por bloque. El resultado se conserva para
dos pares inmutables por proceso, identificado por base, IDs y hashes. Al avanzar
de página se verifican los metadatos y se reutiliza el resultado sin volver a
leer los textos completos. El navegador conserva cuatro páginas de comparación.
Documentos sin texto o fuera del límite siguen disponibles para lectura y descarga.

## Base de datos y operación

Se conserva la cadena de migraciones existente, incluida `fa91c2d6e842`. Se agregó
al modelo la tabla `notification_cursors` que esa cadena ya creaba, para que la
comprobación de esquema coincida con la base real. No se activa el envío de
correos ni se requiere una migración de esquema nueva para estas funciones.

Se conservan la caché de navegación 0.6.8, la lectura por partes y el monitor.
Las funciones de interfaz y los controles nuevos tienen textos en español e inglés;
el contenido oficial permanece en su idioma original.

## Verificación

- 38 pruebas de interfaz: resumen, persistencia y almacenamiento bloqueado,
  selección de incorporaciones, hash de navegación, fechas sin evidencia,
  comparación solicitada expresamente, paginación, respuestas tardías, texto
  seguro, traducción, lectura y sondeo existentes.
- 247 pruebas backend con cobertura total superior al mínimo exigido del 80 %.
- Resumen comprobado sin seleccionar `versions.content`, con aislamiento de datos
  reales/demostración y separación entre una revisión parcial y la última completa.
- Comparación comprobada con preservación de valores técnicos, páginas acotadas,
  rechazo de versiones pertenecientes a publicaciones diferentes y reutilización
  de resultados sin recargar los cuerpos de las versiones al pasar de página.
- Alembic `upgrade head` y `check`: sin operaciones de actualización pendientes.
- Ruff y Bandit ejecutados sobre la aplicación.

Playwright incluye el recorrido con resumen, ficha y comparación contra una API
real aislada para escritorio y móvil. El entorno actual bloquea el arranque de
Chromium (`socket() failed: Operation not permitted`), por lo que ese recorrido
y su apariencia visual quedan pendientes de ejecutar en Windows o un agente
con navegador habilitado. Las pruebas DOM no se presentan como mediciones del
renderizado del navegador ni de la instancia Azure del usuario.

## Probar y publicar

En la carpeta NOM, actualizar desde `PilotoAzure` y ejecutar `INICIAR_LOCAL.cmd`.
La interfaz se recompila si hace falta. Se mantiene el arranque sin cuenta para
el portal informativo. Para construir el paquete de App Service:

```bash
bash scripts/package-appservice.sh data/NOM_AppService_0.7.0.zip
python scripts/package_smoke.py data/NOM_AppService_0.7.0.zip
```

El ZIP contiene la interfaz compilada, las migraciones completas y los archivos
de arranque. Después del despliegue, `/api/health` debe identificar frontend y
backend 0.7.0. La aceptación de rendimiento y aspecto en Azure requiere abrir
esa instancia y comprobar las tres funciones tras recargar con Ctrl+F5.
