# Archivo e historial de publicaciones · 0.7.4

## Uso

**Catálogo NOM** conserva las fichas PLATIICA. **Buscar publicaciones** organiza las publicaciones SIDOF guardadas por fecha oficial: proyectos, normas definitivas y de emergencia, modificaciones, acuerdos, avisos y cancelaciones seleccionados por el colector existente.

- Elige año y mes o escribe un rango Desde/Hasta. Puedes ordenar de más reciente a más antigua o al revés. Los límites de fecha son inclusivos. Un rango excluye documentos sin fecha oficial confirmada.
- Los filtros de texto y tipo siguen disponibles. El archivo muestra 25 registros por página; Novedades y Catálogo NOM conservan su paginación de 15.
- **Cobertura del archivo guardado** distingue las fechas de los documentos y los días con índice efectivamente consultado. Un intervalo de fechas con documentos no demuestra cobertura continua, ni que se haya descargado todo el DOF.
- **Ver historial relacionado** está en las fichas con una clave NOM completa y en su lector. Abre una cronología de publicaciones SIDOF que citan esa clave. El fragmento y su ubicación (título, identificador o texto) permiten revisar la referencia. Puedes abrir cada documento.

Las relaciones usan número, dependencia y año completos. Se acepta el prefijo PROY y guiones tipográficos, pero se conservan el marcador EM y los años. No se vinculan automáticamente claves de años distintos, sustituciones ni cancelaciones. Una cita en una bibliografía es una mención documental, no una declaración de modificación o vigencia.

## Ampliar el archivo

La interfaz solo muestra lo ya recuperado. Esta versión no incluye una base histórica precargada ni descarga todos los años al iniciar.

En una sesión con rol administrador, abre **Buscar publicaciones → Cargar un periodo anterior**, indica fechas de hasta 366 días y solicita la carga. Se usa la cola existente. El trabajo conserva sus límites, evita duplicar publicaciones y registra las respuestas incompletas. Consulta su resultado en **Estado de fuentes** y utiliza **Retomar** cuando corresponda. Si hay otra consulta activa para esa fuente, espera a que termine.

El portal público de Azure conserva su rol de consulta. Sin acceso administrativo en la interfaz, se puede solicitar la carga desde SSH, en la carpeta backend de la aplicación y usando la misma base de producción:

```bash
DATABASE_URL=sqlite:////home/nom-monitor/nom.db python -m app.cli backfill-sidof --start 2026-01-01 --end 2026-01-31
```

El monitor procesa la cola cuando `MONITOR_ENABLED=true`. Cada lote tiene límites y puede terminar parcial, conservando el punto de continuación. No repitas un periodo mientras su consulta sigue activa. Las respuestas de las fuentes determinan la disponibilidad real del histórico.

## Actualización y rendimiento

La migración `b17d6408a075`, posterior a `fa91c2d6e842`, añade dos tablas de referencias e índices de metadatos. Conserva las publicaciones, las versiones, la evidencia y los cursores de notificación existentes. La migración no procesa los textos.

El monitor prepara hasta diez publicaciones SIDOF existentes por ciclo, una copia a la vez. Las nuevas versiones se indexan dentro de la misma transacción de ingesta. Una marca persistente evita volver a procesar textos sin referencias y las versiones anteriores dejan de aportar referencias al cambiar la copia actual.

La consulta del historial usa un índice por clave NOM y no selecciona cuerpos de documentos. El lector y la comparación se cargan al solicitarlos. Las llamadas de cobertura e historial no consultan sitios externos. Los paneles cancelan solicitudes obsoletas y muestran errores recuperables.

Si ejecutas con monitor desactivado, después de aplicar las migraciones puedes preparar las referencias de forma explícita:

```bash
python -m app.cli index-publication-history
```

Para actualizar tu carpeta NOM habitual, conserva tus datos locales, actualiza la rama PilotoAzure y ejecuta `PREPARAR_LOCAL.cmd` e `INICIAR_LOCAL.cmd`. El arranque aplica las migraciones y comprueba la compilación.

## Verification scope

Automated checks cover inclusive dates, leap years, deterministic pagination, exact identifiers, demo separation, verbatim reference context, replacement of stale references, absence of document-body queries on history requests, bounded indexing, coverage claims, existing import permissions, navigation, and late-response cancellation. Synthetic records used in tests are never imported into the user's database.

The archive is limited to saved SIDOF records selected by the existing collector. It is not a complete DOF mirror or a legal relationship graph. Deploying this package does not populate earlier periods automatically. Browser visual acceptance and live Azure historical imports must be assessed after deployment.
