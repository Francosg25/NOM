# Puesta en marcha y aceptación del piloto

## Uso actual del portal · 3 de noviembre de 2026

El portal de lectura ahora abre sin cuenta, usa SQLite/archivos y tiene el monitor integrado. La navegación es boletín, archivo y fuentes, en español o inglés. Entra, Blob, PostgreSQL y el trabajador externo son opcionales. Para el arranque actual seguir README.md y docs/AZURE.md; los apartados posteriores describen la aceptación técnica histórica y los comandos avanzados. La evidencia de cobertura que sigue no cambia por el rediseño.

## Resultado comprobado el 2 de noviembre de 2026

La consulta ejecutada **desde el programa** descargó y guardó tres documentos reales:
la ficha PLATIICA NOM-014-ENER-2025, la página de normatividad NOM de SNICE y el
documento SIDOF 5758923. Los tres archivos se recuperaron del almacén y su SHA-256
coincidió con su clave. Una segunda consulta creó **cero versiones adicionales**.

El índice diario DOF no pudo consultarse: robots.txt devolvió HTTP 503 en ambos
intentos de aceptación. El trabajo quedó parcial y el periodo pendiente. Por ello
el resultado global es `passed=false`, `coverage_verified=false`.

- [Primera ejecución real](evidence/acceptance-first.json)
- [Segunda ejecución y deduplicación](evidence/acceptance-repeat.json)
- [Revalidación final con observaciones de cada trabajo](evidence/acceptance-final.json)
- [Muestra pública cargada y propuestas sin aprobación humana](evidence/catalog-proposals.json)
- [Procedencia, hashes originales y extractos de prueba](../backend/tests/fixtures/official/provenance.json)

Una muestra de tres URLs no demuestra que se detecten todas las publicaciones.
El repositorio público incluye extractos de texto reducidos en una estructura
HTML mínima, con hash propio y hash separado de la descarga original. No contiene
las respuestas HTML íntegras con sus metadatos y contactos. Los tests de estos
extractos no validan la estructura original del portal; los informes de aceptación
proceden de las consultas reales y de la recuperación de su evidencia completa.
SNICE se vigila como página informativa; en la captura sus menciones al capítulo
2.4 y al Anexo 2.4.1 no incluyen enlaces directos a esos documentos. No se presenta
esta página como el texto íntegro del Anexo ni como inventario de novedades.

## Preparar una instalación existente

Realizar respaldo de la base antes de migrar. Desde `backend/`, usar el ejecutable
del entorno del README en lugar de `python` si no está activado:

```text
python -m app.cli init-db
python -m app.cli configure-pilot
python -m app.cli pilot-catalog
python -m app.cli worker --poll
```

`configure-pilot` agrega fuentes ausentes y rellena URLs vacías; preserva URLs
personalizadas. No activa programación. `pilot-catalog` es idempotente y crea
11 registros: 3 familias, 4 subfamilias y 4 fichas de producto por completar,
basadas en las categorías públicas de Johnson Electric. Todas se identifican
como **MUESTRA PÚBLICA**. No se inventan PN, potencias, voltajes, fracciones,
NICO, responsables ni aplicabilidad. La descripción y `technical.provenance_url`
conservan su origen; no son inventario confirmado de ninguna planta.

En Windows, después de la preparación inicial, `INICIAR_LOCAL.cmd` inicia la web con el monitor integrado; aplica migraciones y activa las fuentes que todavía no tengan configuración de programación. No iniciar además el trabajador externo.

## Repetir la aceptación técnica

Use una base de validación separada, sin otros consumidores. Puede seleccionar
las fechas; 2025-06-02 sirve para el documento de referencia conocido, no para
demostrar la cobertura de todas las NOM vigentes.

```text
python -m app.cli validate-sources --start 2025-06-02 --end 2025-06-02 --output data/validacion.json
```

Para comprobar descubrimiento DOF, un responsable debe cotejar todas las ediciones
de un periodo conocido y guardar los IDs completos en un JSON de esta forma:

```json
{"dof": ["DOF:IDENTIFICADOR_REVISADO"]}
```

El valor anterior es un marcador de formato, no un identificador real. Después:

```text
python -m app.cli validate-sources --start AAAA-MM-DD --end AAAA-MM-DD --expected inventario_revisado.json --output data/validacion.json
```

Se comparan faltantes y sobrantes por fecha de publicación explícita. Cualquier
fallo, extracción pendiente o diferencia mantiene el resultado sin aprobar.
No se confunde una fecha desconocida con la fecha de detección. El comando limita
lotes y no ejecuta trabajos ajenos al suyo. Repetirlo permite comprobar deduplicación.
Los documentos que ya estaban en la base no sustituyen una observación de la
ejecución actual. El detalle de cada trabajo incluye los documentos observados,
su versión y descarga de evidencia, incluso si no hubo cambios. Las ejecuciones
anteriores a esta función no tienen ese inventario retroactivo.

`technical_passed` comprueba descargas e integridad de las fuentes activas;
`coverage_verified` exige el inventario DOF manual coincidente; `passed` requiere
ambos. Sin inventario revisado se devuelve código 2, aunque las descargas sean
correctas. `{"dof": []}` solo debe usarse para un periodo revisado sin publicaciones.

## Revisión necesaria de Johnson Electric

| Comprobación | Estado | Evidencia que falta |
| --- | --- | --- |
| Documento de referencia descargado y recuperable | Comprobado | Hash y captura conservados |
| Tres URLs sin duplicar al repetir consulta | Comprobado | Informes enlazados arriba |
| Descubrimiento diario y ediciones DOF | Pendiente | Consulta permitida y comparación con inventario manual |
| Productos representativos de la planta | Pendiente JE | PN, modelo, ficha técnica, uso, fracción/NICO y responsable reales |
| Propuestas revisadas por responsable | Pendiente JE | Decisión, justificación, usuario y fecha registrados en Alertas |
| Acceso al boletín | Lectura abierta implementada | Entra es opcional y no condiciona el portal |
| Operación programada alojada | Pendiente probar en Azure | Monitor integrado, SQLite y archivos persistentes bajo /home |

Para el uso opcional del catálogo por API/CLI, sustituir/completar los borradores o crear las fichas reales.
Las reglas de familias y subfamilias se heredan con el origen indicado en el
motivo. La API de alertas permite asignar, comentar, confirmar y descartar con historial.
La mera mención de motores puede proponer una relación para un motor CC: eso no
significa que la NOM-014-ENER-2025 le aplique. Contrastar alimentación, fases,
tecnología, potencia, servicio y exclusiones contra el documento oficial.

Se cargó la muestra y se procesó su cola sobre las tres publicaciones reales;
el informe de propuestas conserva sus motivos y la ausencia de decisiones.
No se contactó a un responsable ni se simuló su aprobación. No se puede cerrar
esta aceptación con categorías públicas o con decisiones del usuario local de prueba.

## Programación implementada

1. Validar manualmente cada fuente y su acceso en el equipo de ejecución.
2. En **Las fuentes**, indicar fecha inicial, frecuencia y habilitar
   consultas automáticas por fuente.
3. El portal con `MONITOR_ENABLED=true` y `SCHEDULER_ENABLED=true` ya incluye el consumidor. Como alternativa, desactivar el monitor integrado e iniciar **un** trabajador externo:

```text
python -m app.cli worker --poll --schedule
```

En Windows `INICIAR_AUTOMATICO.cmd` abre ahora el portal con su monitor integrado. Detener el servidor detiene las consultas. App Service debe mantenerse cargado con Always On. El ejemplo systemd corresponde al trabajador externo opcional. El navegador del usuario puede cerrarse sin detener las consultas del servidor.

Los lotes parciales por límite se retoman sin esperar la frecuencia completa;
los fallos esperan la frecuencia configurada. Se reintenta el intervalo pendiente
antes de avanzar, se cubre el atraso en bloques de hasta 366 días y se vuelve a
consultar el día anterior tras completar el periodo actual. No se garantiza detectar
cambios históricos fuera de esos intervalos. Evitar dos programadores simultáneos.

## Proxy con resolución remota

Por defecto se valida DNS local. Cuando el proxy aprobado resuelve los dominios,
configurar `SOURCE_DNS_MODE=proxy` con `HTTPS_PROXY` o `ALL_PROXY` ya configurado.
Se mantienen TLS verificado, dominios oficiales exactos, validación de cada
redirección y robots.txt. El proxy debe restringir salida y destinos privados.
Nunca habilitar esta opción como sustituto de la configuración de red corporativa.
La solicitud usa `Accept-Encoding: identity` para interoperar con proxies que
transforman respuestas comprimidas; no se ignoran errores de TLS o de robots.
