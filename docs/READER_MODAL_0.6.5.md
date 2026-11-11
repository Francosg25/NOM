# Ventana de lectura 0.6.5

## Cambio visible

Al abrir una NOM aparece inmediatamente una ventana centrada, con fondo atenuado, bordes redondeados y una transición de entrada. La tarjeta usa el mismo tipo de letra y los colores del portal. Su ancho máximo es 940 px y su altura se adapta a la pantalla. En móvil conserva márgenes y el desplazamiento del documento queda dentro de la ventana.

La cabecera identifica la vista como **LECTURA DE NORMA** y permite cerrar con el botón o Escape. Al cerrar, el foco regresa al título que abrió la NOM. El título, la fecha y el enlace oficial ocupan una cabecera compacta. Los controles de tamaño permanecen disponibles durante la lectura. Las versiones anteriores se eligen mediante un selector; las fechas técnicas de la copia quedan dentro de una sección desplegable.

Una respuesta de carga tardía no puede volver a abrir la ventana después de cerrarla.

## Correcciones de integración

- La API de publicación entrega la estructura de lectura de la última versión en la misma respuesta. La interfaz utiliza esa estructura sin depender de otra petición para el primer documento.
- Las copias JSON antiguas se reconocen aunque hayan sido guardadas como HTML o con un parámetro charset en el tipo de contenido.
- Cuando no existe estructura HTML recuperable, el lector distribuye las líneas antiguas en párrafos y une numeraciones y fragmentos reconocibles de palabras. Solo cambia espacios/saltos: conserva letras, signos y cifras. No deduce tablas perdidas ni altera el texto o los hashes guardados en la base.
- Se permite en la política de imágenes el host oficial `https://sidof.segob.gob.mx`, que el componente ya valida para figuras PNG/JPG/GIF/WebP. La política anterior impedía que esas figuras aparecieran. Scripts y conexiones de API siguen restringidos al propio portal.
- La portada se devuelve con `Cache-Control: no-store` para evitar conservar una entrada de interfaz antigua tras un despliegue.
- Health identifica por separado la versión del proceso Python y la de los archivos de la interfaz. El comprobador de despliegue exige ambas versiones y el lector `modal-v2`, y recupera la presentación de una muestra antes/después de reiniciar o restaurar.

## Comprobar el despliegue

1. Publicar `NOM_AppService_0.6.5.zip` en la App Service existente.
2. Reiniciar esa misma App Service después del despliegue para cargar el nuevo proceso Python.
3. Comprobar `/api/health`: `frontend.version` y `backend.version` deben ser `0.6.5`; `backend.document_reader` debe ser `modal-v2`.
4. Recargar el portal con Ctrl+F5 y abrir una NOM. Debe aparecer la ventana centrada con **LECTURA DE NORMA**.

No se requiere migración ni comandos SSH. El paquete conserva las mejoras de recuperación SIDOF y del lector estructurado de las versiones anteriores.

## Verificación y límite de este entorno

Las pruebas de componentes comprueban la apertura inmediata del modal, el foco, Escape, la cancelación de respuestas atrasadas, el uso de la lectura incluida en la publicación y la distribución de texto antiguo. Las pruebas de API verifican las copias con tipos de contenido antiguos, la cabecera de imágenes, los datos enviados junto con la publicación y las versiones reales del proceso.

Se preparó una vista local con los componentes de la aplicación y la NOM oficial DOF:5802721. El navegador del entorno rechazó el protocolo `file:` por su política de URL. No se intentó eludir esa restricción y no se declara comprobada aquí la apariencia visual en un navegador. La revisión de la instancia Azure requiere su URL completa; la comprobación del ZIP sí utiliza un servidor HTTP aislado con la API real, reinicio y restauración.
