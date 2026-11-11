# Recuperación SIDOF 0.6.3

## Resultado comprobado el 11 de noviembre de 2026

Se consultó realmente SIDOF para el periodo del 2 al 11 de noviembre de 2026 con HTTPS verificado. No se sustituyeron las respuestas de la fuente por datos de demostración. El archivo [de evidencia](evidence/sidof-recovery-2026-11-11.json) conserva cada comprobación, las direcciones oficiales y los hashes obtenidos.

| Comprobación | Resultado |
| --- | --- |
| Fechas procesadas | 10 |
| Registros de los índices diarios | 787; incluyen referencias de página y notas, no 787 NOM |
| Referencias recuperadas desde PDF | 65 |
| Referencias todavía sin contenido verificable | 0 |
| Errores de consulta en esta prueba | 0 |
| Fechas sin publicación según el calendario visual oficial | 7 y 8 de noviembre de 2026 |
| Publicación NOM seleccionada, después de resolver la duplicación de la imagen | DOF:5802721; NOM-EM-023-SE-2026, publicada el 2 de noviembre |

El primer recorrido detectó también DOF:5802720, que SIDOF presenta como referencia de imagen de la misma página de la NOM. La comprobación final del 2 de noviembre utilizó el mecanismo de deduplicación: dejó una sola publicación, DOF:5802721, y conservó la evidencia de la imagen con `represented_by`. Ambos recorridos reales se conservan por separado en el archivo de evidencia.

Estos resultados corresponden al periodo y las respuestas observadas. La selección es técnica y no determina aplicabilidad a un producto ni acredita cobertura normativa integral.

## Causas y correcciones

1. **Notas API vacías.** Algunas referencias no contienen título ni texto en JSON. Ahora se descarga el PDF original del diario, se verifica la fecha y el número de la página declarada por SIDOF, y se extrae su texto. Se analiza la página completa para evitar perder otra NOM en una página compartida. Una imagen y una nota con texto solo se vinculan cuando coinciden diario, sección, página y encabezado completo, sin identificadores NOM adicionales sin representar.
2. **Calendario API incompleto.** `FechasSinPublicacion` llega vacío. Se permite comprobar el calendario visual de SIDOF cuando está enlazado por el propio portal, contiene una regla explícita que deshabilita esa fecha y el portal muestra una edición anterior. El manifiesto y el listado de notas no deben contradecirlo. Un 404 o un fin de semana por sí solos no cierran la fecha.
3. **Descargas de diarios grandes.** Los originales comprobados superan el límite de 12 MiB que se usaba para todas las respuestas. Solo el endpoint oficial de PDF tiene ahora un límite de 64 MiB. El lector procesa la página solicitada y conserva un solo diario en memoria por lote. Se mantienen TLS, restricciones de destinos, reglas de robots, límites y reintentos.
4. **Estados de cobertura.** Los días comprobados mediante calendario se presentan separados de los días con índice revisado. Una referencia realmente ilegible mantiene la fecha reintentable y el estado parcial; reanudar un cursor vacío no puede convertirla en una consulta correcta.
5. **Conservación de una versión legible.** Una respuesta posterior vacía e incompleta se registra como evidencia de un intento; conserva la versión legible anterior en lugar de reemplazarla por contenido vacío.
6. **Interfaz.** La evidencia recuperada se puede desplegar dentro de la revisión diaria. Los mensajes HTTP originales quedan dentro de los detalles técnicos cuando existe un fallo real. Se distingue una norma de emergencia y se elimina la repetición del título al inicio del extracto.

## Instalación y comprobación en Azure

Publicar `NOM_AppService_0.6.3.zip` en la misma App Service. No se requieren librerías nuevas del sistema, OCR, cambios de base ni eliminación de datos. Se utiliza `pypdf`, que ya formaba parte de las dependencias fijadas.

Al arrancar, SIDOF se vuelve a programar una sola vez si el monitor y su programación ya estaban habilitados. El monitor procesa los lotes en segundo plano. Revisar el registro más reciente después de terminar los lotes y comprobar `/api/health` con versión `0.6.3`. Las ejecuciones históricas parciales anteriores permanecen visibles como historial de sus resultados originales.

La prueba del paquete ejecuta `startup.sh` en modo de producción, comprueba la API y la compilación, reinicia el proceso conservando la base y las copias, y prueba respaldo/restauración en una carpeta aislada. Esta comprobación local del ZIP no sustituye confirmar el resultado en la instancia Azure del usuario.

## Pruebas de producto

Las pruebas automatizadas cubren calendarios contradictorios, ediciones extraordinarias, redirecciones, PDF de otra fecha o página, cuerpos inválidos, valores literales `null`, páginas con varias NOM, deduplicación, reintentos y conservación de una versión legible. También se prueban los estados ES/EN del portal.

El intento de ejecutar Playwright con Chromium en este entorno fue bloqueado por su aislamiento de procesos (`socket() failed: Operation not permitted`). El navegador compartido tampoco puede acceder al servidor de pruebas por localhost. Por tanto, no se declara superada la batería de navegador ni de accesibilidad con axe; se conservan sus pruebas para ejecutarlas en un agente con navegador habilitado. Los componentes y la compilación sí se validan aquí.

## Referencias oficiales utilizadas

- [Documentos PDF del diario, documentación SIDOF](https://sidof.segob.gob.mx/datos_abiertos/getPDF/43)
- [Consulta de diarios y calendario API, documentación SIDOF](https://sidof.segob.gob.mx/datos_abiertos/getPDF/65)
- [Calendario visual de 2026](https://sidof.segob.gob.mx/assets/css/calendarCss/2026.css)
- [Portal SIDOF consultando el 7 de noviembre](https://sidof.segob.gob.mx/welcome/07-11-2026)
- [Portal SIDOF consultando el 8 de noviembre](https://sidof.segob.gob.mx/welcome/08-11-2026)
