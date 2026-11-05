# Operación verificable · 0.6.0

La rama conserva el portal sencillo: SIDOF, SQLite y evidencia local. Los mecanismos de recuperación no hacen que una instancia única tenga alta disponibilidad. Esta guía distingue comprobaciones automatizadas de aceptación en Azure, todavía pendiente.

## Señales de funcionamiento

| Ruta | Qué verifica | Resultado |
| --- | --- | --- |
| `/api/health` | Proceso web y versión compilada | 200; no acredita consultas ni persistencia |
| `/api/ready` | Consulta a BD, escritura temporal de evidencia y pulso reciente del monitor si está habilitado | 200 o 503 con códigos; no recicla el portal por un fallo de SIDOF |
| `/api/operations` | Pulso durable, programación vencida, fuente parcial y primera revisión pendiente | `ok`/`degraded`; sin URLs, tokens ni errores originales |

El pulso se renueva antes/después de cada ciclo y queda en la base. Una ingesta larga prueba actividad mediante su arrendamiento renovado. La comprobación vence a los dos minutos; un trabajo programado con más de quince minutos de retraso produce `SCHEDULE_OVERDUE`. SIDOF sin novedades puede estar sano: no se exige recibir una NOM nueva cada día. Una fecha con HTTP 404 continúa sin verificar.

En App Service, configurar Health check a `/api/ready`, Always On y una instancia/proceso. Crear las alertas operativas en Azure después de desplegar: endpoint 503 persistente → fallo local; `/api/operations` degradado → revisar cola/fuente. La configuración de Health check puede reiniciar la aplicación; hacerlo dentro de la aceptación. No se han creado reglas, destinatarios ni alertas reales desde esta rama.

La sonda usa únicamente GET y retorna código 2 ante fallos; `--strict-source` también trata avisos de monitor/fuente como señal de alerta. Un sistema de supervisión autorizado puede ejecutar esa sonda y notificar al responsable. No se mandan mensajes desde la aplicación ni se añade un servicio obligatorio.

## Aceptación en Azure, sin afirmar resultados aún

Desde `backend`, con Python y dependencias instaladas, reemplazar el origen:

```bash
python -m app.deployment_check --url https://TU-PORTAL.azurewebsites.net --version 0.6.0 --output data/antes.json
```

El informe comprueba versión, readiness, SIDOF único y recupera una muestra de evidencia. Si no hay documentos, indica `NO_SAVED_EVIDENCE_TO_VERIFY`: primero dejar que el programador descargue una muestra real. No dar por validada la persistencia con una base vacía.

1. Registrar baseline con muestra real y hashes. Cerrar el navegador; esperar al siguiente ciclo horario.
2. Volver a ejecutar, sin pulsar Consultar SIDOF:

```bash
python -m app.deployment_check --url https://TU-PORTAL.azurewebsites.net --version 0.6.0 --baseline data/antes.json --require-automatic-run --output data/despues.json
```

3. Verificar que el resultado identifique una ejecución **nueva**, iniciada por `scheduler`, posterior al baseline y terminada. Una ejecución parcial sigue mostrando sus avisos; no acredita cobertura.
4. Reiniciar App Service, esperar readiness y repetir la sonda con el baseline. Compara conteo y hash de la versión original incluso si llegó una versión posterior.
5. Volver a desplegar el ZIP y repetir. Conservar `/home/nom-monitor` y sus datos.
6. Registrar el resultado, fechas, versión, responsable y evidencia de una restauración en ubicación separada. Acordar RPO/RTO medidos antes de aceptar operación crítica.

## Respaldo y restauración

Desde `backend`, usando la configuración de la instalación que se quiere respaldar:

```bash
python -m app.cli backup --destination /RUTA/SEGURA/backup-2026-11-05
python -m app.cli restore --source /RUTA/SEGURA/backup-2026-11-05 --destination /RUTA/NUEVA/recuperada
```

Para Windows se pueden usar rutas entre comillas. Cada destino debe ser nuevo. El respaldo usa la API online de SQLite, incluye la base y todos los originales referenciados por sus versiones, y verifica integridad SQL, referencias y SHA-256. No copia `.env` ni credenciales. El manifiesto detecta corrupción; no autentica al autor de un respaldo externo. Mantener los respaldos en una ubicación de confianza y con permisos corporativos.

La restauración verifica la copia antes de publicarla; no sustituye los datos activos. Para un cambio real, parar monitor/web, conservar la instalación anterior, apuntar `DATABASE_URL` a `recuperada/nom.db` y `STORAGE_PATH` a `recuperada/evidence`, arrancar, aplicar migraciones y ejecutar la sonda. Los trabajos en curso pueden esperar a que venza su arrendamiento antes de recuperarse. No ejecutar a la vez dos monitores contra SQLite.

Definir con el operador una frecuencia de respaldo y retención (propuesta inicial: diario y antes de cada actualización), guardar una copia fuera del volumen de la aplicación y ensayar recuperación periódicamente. Esta rama agrega herramientas y pruebas; no configura un respaldo diario real ni almacenamiento adicional. Conservar sólo copias en `/home` no protege frente a la pérdida de ese volumen.

## Escalado sin alterar el piloto actual

No se activan PostgreSQL, Blob ni trabajadores externos. El worker existente `python -m app.cli worker --poll --schedule` puede utilizarse más adelante con `MONITOR_ENABLED=false` en la web; el despliegue debe garantizar un único programador. Su pulso se registra también para la supervisión.

Antes de varias instancias: probar PostgreSQL gestionado, almacenamiento de evidencia compartido y duradero, único programador supervisado y consumidores con arrendamiento. La CI comprueba el adaptador PostgreSQL; eso no acredita conmutación, capacidad ni disponibilidad de una infraestructura concreta. Medir carga, tiempos de cola, restauración y fallos de red antes de migrar. Mantener SQLite en una instancia hasta que haya una necesidad medida.

Referencias oficiales: [Health check](https://learn.microsoft.com/azure/app-service/monitor-instances-health-check), [Python en App Service](https://learn.microsoft.com/azure/app-service/configure-language-python), [Always On](https://learn.microsoft.com/azure/app-service/configure-common).
