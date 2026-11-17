# Navegación 0.6.8

## Cambio

Antes, cada cambio entre Novedades y Catálogo NOM esperaba cuatro respuestas
(`/me`, `/dashboard`, `/publications` y `/jobs`). La lista no se mostraba hasta
recibir la última, aunque la API de publicaciones ya hubiera respondido.

Ahora las publicaciones se muestran independientemente del resumen, los trabajos
y la identidad. `/me` se consulta al iniciar la sesión o reintentar un error. El resumen
y los trabajos se cargan inicialmente y se actualizan con el sondeo existente
(5 segundos con trabajos activos; 60 segundos en reposo) o con la actualización
manual. Abrir una pestaña no reinicia esas consultas.

Los listados ya visitados se muestran desde memoria y se verifican nuevamente
en segundo plano al volver. La clave incluye fuente, búsqueda, página, fechas,
tipo, cambios y modo de demostración. Los datos de otra fuente o filtro nunca
se muestran mientras llega la nueva respuesta. La caché admite hasta 12 páginas,
solo dentro de la sesión del componente, sin localStorage ni almacenamiento en
disco, y se destruye al cambiar la sesión de autenticación o desmontar el portal.

Después de cargar una lista predeterminada, se prepara la primera página de la
otra fuente en segundo plano. Un clic durante esa preparación comparte la misma
solicitud. No se precargan todos los filtros ni todo el catálogo. Esta preparación
reutiliza resultados de hasta 30 segundos; volver a la pestaña y el sondeo activo
siempre verifican cambios. Solicitar una consulta de fuentes invalida las páginas
guardadas. Un error de actualización no elimina las publicaciones ya visibles.

Se mantiene la pausa del sondeo mientras se lee una NOM o se inspecciona una
consulta anterior, la cancelación de búsquedas abandonadas y la protección ante
respuestas tardías.

## Comprobaciones locales

- 26 pruebas de interfaz: lectura y sondeo existentes; API de resumen/usuario/
  trabajos detenida sin bloquear publicaciones; precarga compartida; retorno a
  una pestaña antes de responder su API; datos nuevos que sustituyen a los
  guardados; filtros/paginación independientes; cambio de sesión; caché acotada
  e invalidación; error en segundo plano sin perder el listado y recuperación de
  la identidad al reintentar un error.
- 51 pruebas de API, incluida la identificación de la versión 0.6.8.
- Compilación de producción con TypeScript y Vite.

La prueba Playwright adicional cubre escritorio y móvil con la segunda respuesta
SIDOF retenida hasta verificar que el listado guardado ya es visible. Este
entorno bloqueó el inicio de Chromium con `socket() failed: Operation not
permitted`; no se declara aprobada esa ejecución de navegador. Queda incluida
para ejecutarse en Windows o un agente con navegador disponible.

Los resultados anteriores prueban comportamiento con demoras controladas;
no son mediciones de la instancia Azure. La primera visita aún necesita la API.
Si sigue siendo lenta después de publicar 0.6.8, medir `/api/publications`,
`/api/dashboard` y `/api/jobs` por separado en Network y revisar CPU, memoria y
almacenamiento del App Service. Always On evita el arranque tras inactividad;
no corrige por sí solo consultas lentas mientras la aplicación está cargada.

## Publicación

Actualizar el código con `git pull --ff-only origin PilotoAzure` y usar
`INICIAR_LOCAL.cmd` para la prueba local. Para preparar Azure, con las dependencias
de frontend instaladas:

```bash
bash scripts/package-appservice.sh data/NOM_AppService_0.6.8.zip
```

Subir el ZIP completo desde Cloud Shell con los permisos corporativos de
despliegue ya habilitados:

```bash
az webapp deploy \
  --subscription ab029082-550e-447e-bec6-b0b363b1a8c7 \
  --resource-group rg-jess01-np-eus-np-scs-02-Mexico \
  --name rg-jess01-np-eus-np-scs-02-mexico-webapp \
  --src-path NOM_AppService_0.6.8.zip \
  --type zip
```

Comprobar `/api/health`: frontend y backend deben identificar 0.6.8. Recargar
con Ctrl+F5 y alternar Novedades/Catálogo NOM, verificando que los datos guardados
se muestran mientras la solicitud de publicaciones sigue en curso. Esta entrega
no cambia recursos, tamaño del plan ni ajustes de red o autenticación de Azure.
