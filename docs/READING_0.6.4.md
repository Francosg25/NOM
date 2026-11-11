# Lectura de documentos 0.6.4

El lector anterior mostraba un texto plano que separaba cada fragmento HTML con un salto de línea. Por eso una palabra como `regulación` podía aparecer como `regulaci`, `ó`, `n`, y las celdas de una tabla se mostraban como líneas independientes.

El nuevo endpoint `/api/versions/{id}/reading` reconstruye una presentación pasiva desde la copia original conservada en la evidencia. Devuelve párrafos, encabezados, listas y tablas como datos JSON. La interfaz genera elementos React y no ejecuta el HTML oficial ni sus estilos o scripts. Conserva las celdas combinadas, superíndices y subíndices. Las figuras se cargan únicamente desde las rutas de imágenes oficiales de SIDOF; los enlaces antiguos a `sidofqa` se presentan mediante el host de producción que sirve esas mismas figuras.

La lectura usa una sola tipografía, fondo blanco, tamaño inicial de 18 px, ancho de texto limitado y separación entre párrafos. Los controles A−/A+ permiten ajustar entre 16 y 24 px y conservan esa preferencia en el navegador. Las tablas anchas tienen desplazamiento horizontal propio y se pueden enfocar con el teclado. Los controles permanecen disponibles al desplazarse por el documento.

No se reescriben la base, las versiones, las fechas ni la copia descargable. La mejora también funciona con NOM guardadas antes de instalar esta versión. Si falta la evidencia original, se mantiene disponible el texto conservado sin inventar una estructura para sus tablas o sus valores. Si no se puede cargar una figura, se indica que puede consultarse en la fuente oficial.

## Comprobación con la NOM de la captura

Se utilizó el JSON oficial de DOF:5802721, correspondiente a NOM-EM-023-SE-2026. Se comprobó que, después de excluir el título duplicado que ya muestra el lector, todos los caracteres del contenido se conservan salvo los espacios propios de la maquetación. La presentación mantiene 11 tablas, 52 filas, 210 celdas y 3 figuras. También se verificaron la palabra `regulación` y el encabezado `3.5. Cemento portland compuesto (CPC)`.

La [evidencia de la comprobación](evidence/nom-reading-2026-11-11.json) contiene el hash de la respuesta utilizada y los conteos. La primera figura de la NOM se comprobó accesible desde el host oficial de producción con respuesta HTTP 200 e imagen PNG.

Las pruebas automatizadas verifican preservación de cifras y unidades, uniones de fragmentos, celdas combinadas, ausencia de contenido ejecutable, acceso a versiones antiguas, conservación del original, cambio de tamaño y selección de versiones sin respuestas atrasadas. El ZIP comprueba la API de lectura antes y después de reiniciar y restaurar un respaldo.

El intento de ejecutar Chromium/Playwright en este entorno fue bloqueado por el aislamiento del navegador (`socket() failed: Operation not permitted`). Por ello no se declara validada aquí la inspección visual con navegador ni la batería de accesibilidad de navegador. Se validan los componentes, la compilación, el contenido estructurado y la API del paquete.

## Instalación

Publicar `NOM_AppService_0.6.4.zip` mediante el mismo procedimiento de Azure App Service. No requiere migración de base ni ejecutar comandos SSH. Comprobar `/api/health` con versión `0.6.4` y volver a abrir una NOM en el portal. El paquete incluye también las correcciones de recuperación SIDOF de 0.6.3.
