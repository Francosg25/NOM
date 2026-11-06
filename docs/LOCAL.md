# Probar NOM Monitor / Run NOM Monitor locally

El portal utiliza PLATIICA para sincronizar las fichas del catálogo NOM y SIDOF para revisar publicaciones diarias del DOF. La carga inicial del catálogo se procesa por lotes y puede tardar; consulta la página de estado y no interpretes una carga parcial como catálogo completo. Las instrucciones de arranque se mantienen.

## Español

La versión **0.4.1** tiene un encabezado grande **norma.**, fondo color papel y navegación horizontal. Arriba están los botones **Español** y **English**. Incluye consulta diaria SIDOF y validación nativa de certificados de Windows. Al actualizar, ejecuta PREPARAR_LOCAL.cmd para instalar la dependencia de Windows. Si ves una barra lateral verde con Inicio, Alertas y Productos, estás viendo una versión anterior.

### Primera vez desde el ZIP

1. Extrae todo el ZIP en una carpeta nueva. No ejecutes los archivos dentro del archivo comprimido.
2. Ejecuta `PREPARAR_LOCAL.cmd`. Usa Python instalado y autorizado. El ZIP ya incluye la interfaz compilada; no requiere Node para esta primera prueba.
3. Ejecuta `INICIAR_LOCAL.cmd`.
4. Espera a que se abra <http://127.0.0.1:8000>. Mantén abierta la consola y usa Ctrl+C para detenerla.

La consola comprueba que la interfaz corresponde al código de la carpeta. Si el puerto 8000 ya está ocupado, avisa para que cierres el servidor anterior. No abre otra sesión sobre ese servidor.

Para abrir directamente en inglés: <http://127.0.0.1:8000/?lang=en>. Para español: <http://127.0.0.1:8000/?lang=es>. La elección se recuerda en el navegador.

### Si usas Git o cambiaste el código

Los cambios de esta entrega están en `feature/piloto-verificable`. Antes de actualizar, revisa tus cambios locales con `git status`; consérvalos si los tienes. Desde la carpeta NOM:

```text
git fetch origin
git switch feature/piloto-verificable
git pull --ff-only origin feature/piloto-verificable
ACTUALIZAR_INTERFAZ.cmd
INICIAR_LOCAL.cmd
```

Si la rama local aún no existe, Git normalmente crea el seguimiento al hacer `git switch`. Si no lo hace, usa `git switch --track origin/feature/piloto-verificable`. Si Git informa conflictos o divergencia, no fuerces la actualización ni borres tus datos.

`ACTUALIZAR_INTERFAZ.cmd` requiere Node.js y reconstruye la interfaz. Cierra antes el servidor anterior con Ctrl+C; después inicia y recarga con Ctrl+F5. Para preparar un clon nuevo que aún no tiene dependencias de Python, usa `PREPARAR_LOCAL.cmd`.

### Cómo usarlo

1. **Consultar fuentes** revisa los últimos siete días de SIDOF y las páginas configuradas de las otras fuentes. La primera carga puede tardar varios minutos; el servidor sigue atendiendo la página.
2. **Novedades** reúne los documentos recuperados. La fecha oficial y la fecha de detección son distintas.
3. **Buscar publicaciones** busca títulos, identificadores y texto guardado. Los temas guardados son accesos rápidos a esa búsqueda.
4. Abre una publicación para ver su texto, versiones, copia descargable y vínculo oficial.
5. **Estado de las fuentes** muestra qué se consultó y qué falló. En el registro, **Ver revisión diaria** muestra las notas revisadas, los IDs seleccionados y las referencias pendientes de cada día. Un error de conexión no significa que no haya novedades.
6. **Cómo funciona** explica los estados, la cobertura y un ejemplo de uso.

La interfaz y la guía son bilingües. Los textos oficiales permanecen en español. El portal sigue páginas configuradas; todavía no acredita encontrar todas las NOM recientes, no determina automáticamente su aplicabilidad a cada producto y no envía correos.

Tus datos locales se conservan según `DATABASE_URL` y `STORAGE_PATH` de `.env`; no los borres para actualizar la interfaz. El ZIP no contiene tus datos anteriores. Para continuar con una base existente, conserva su ubicación y configuración.

## English

Version **0.4.1** has a large **norma.** heading, a paper-colored background and horizontal navigation. **Español** and **English** are at the top. It includes daily SIDOF discovery and native Windows certificate validation. Run PREPARAR_LOCAL.cmd after updating to install the Windows dependency. A green sidebar with Home, Alerts and Products belongs to an older interface.

1. Extract the entire ZIP into a new folder.
2. Run `PREPARAR_LOCAL.cmd` using an installed, approved Python interpreter. The ZIP includes the compiled interface, so Node is not needed for this first trial.
3. Run `INICIAR_LOCAL.cmd`. Keep the console open. Stop with Ctrl+C.
4. Open <http://127.0.0.1:8000/?lang=en> for English. The language is remembered.

If the launcher reports an old build, run `ACTUALIZAR_INTERFAZ.cmd` with Node.js installed, then start again. If port 8000 is occupied, stop the previous server first.

Select **Check sources**, then read **Latest publications**. SIDOF checks the last seven days; the first load can take several minutes while the portal remains available. Use **Search publications** to find a standard or keyword in the saved documents. Open a title to read it, inspect saved versions, download a copy or visit the official website. In **Source status**, **View daily check** shows each day's checked notes, selected IDs and unresolved references. **How it works** explains the workflow and coverage.

The controls and guide are bilingual. Official documents remain in Spanish. A failed connection does not establish that there are no updates. Daily discovery uses the official SIDOF API; image-only references without a usable title or text remain pending. Complete discovery of all recent standards, automatic product applicability and email notifications are not guaranteed.

Azure deployment uses the separate `startup.sh` entry point. See [AZURE.md](AZURE.md).
