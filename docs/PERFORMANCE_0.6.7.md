# Rendimiento del portal y del lector · 0.6.7

La actualización reduce el trabajo del navegador al abrir una NOM y el volumen
de las consultas que actualizan el boletín. Conserva la ventana centrada, la
animación de apertura, el ajuste de letra, los párrafos, las tablas y las figuras.
Las NOM largas se leen por partes con Anterior, Siguiente y un selector.

## Cambios

- El portal pide metadatos de las versiones con `include_content=false`; abrir
  una NOM ya no descarga el texto completo de todas sus versiones anteriores ni
  obliga a formatear el documento antes de recibir esos metadatos.
- Solo se monta en el DOM la parte seleccionada. Las tablas y las listas son
  indivisibles y todos los bloques mantienen su orden. Se retiraron los tamaños
  estimados de `content-visibility`, que podían alterar la altura al desplazarse.
- Se eliminaron los filtros de desenfoque de las tarjetas, la navegación, el
  fondo y el propio lector, incluidas las reglas heredadas con prefijo WebKit.
- Las lecturas se memorizan por versión, hasta cuatro por sesión. Cerrar la
  ventana cancela las solicitudes pendientes; las respuestas antiguas no pueden
  volver a abrirla. Un fallo real permite reintentar la carga.
- La actualización general pide `/api/jobs?summary=true`, sin descargar las
  colas completas de importación. Estas siguen disponibles en el detalle.
- El panel de cobertura consulta solo la fecha y la declaración de ausencia de
  cada revisión, sin construir cientos de documentos de auditoría en Python.
- Las solicitudes generales anteriores se cancelan al cambiar de búsqueda y
  las actualizaciones automáticas no se superponen. Durante la lectura se pausa
  el sondeo del boletín en el navegador; el monitor del servidor sigue activo.
- La lectura se serializa en el trabajador de la ruta y las respuestas grandes
  se comprimen con gzip. Los fragmentos adyacentes con el mismo estilo se unen
  conservando letras, espacios, unidades y superíndices.
- Se reutilizan los formatos de fecha en cada idioma, en vez de construir un
  formateador para cada fecha de cada tarjeta.

## Mediciones locales

Comparación con 0.6.6 (`7fbf1ef`). La prueba del API utiliza una base temporal
con 12 versiones, 12 procesos con 823 registros en sus colas y 300 revisiones
grandes. Es una historia sintética para reproducir el crecimiento del portal;
no representa una copia de la base del usuario.

| Consulta | 0.6.6 | 0.6.7 |
| --- | ---: | ---: |
| Metadatos y versiones, bytes descomprimidos | 900,722 | 4,663 |
| Lista de procesos, bytes descomprimidos | 912,012 | 4,416 |
| Lista de procesos, mediana local con cachés calientes | 75.62 ms | 5.30 ms |
| Panel general, mediana local con cachés calientes | 100.14 ms | 24.45 ms |
| Lectura estructurada, bytes enviados con la configuración probada | 159,527 | 23,454 |

La muestra documental es NOM-EM-023-SE-2026, DOF 5802721. Se conservaron los 441
bloques y sus 49,360 caracteres distintos de espacios. La lectura de 0.6.7 tiene
18 partes; todas son accesibles y las tablas mantienen sus celdas y combinaciones.

| Trabajo del componente React en jsdom | 0.6.6 | 0.6.7 |
| --- | ---: | ---: |
| Elementos montados al abrir | 1,440 | 63 |
| Máximo de elementos en una parte | 1,440 (documento completo) | 168 |
| Mediana del montaje inicial | 56.03 ms | 8.48 ms |

Estas cifras miden solicitudes locales y construcción del DOM. jsdom no mide
el pintado, la composición gráfica ni el desplazamiento de Chrome/Edge. No se
dispuso de una sesión Azure autenticada ni de la URL completa del portal para
medir el despliegue del usuario. Las restricciones del navegador local tampoco
permitieron esa verificación interactiva. Los resultados y las condiciones de
la comparación se conservan en
[`evidence/reader-performance-2026-11-11.json`](evidence/reader-performance-2026-11-11.json).

Para reproducir las mediciones con una copia oficial descargada previamente:

```bash
.venv/bin/python scripts/profile-api.py ruta/nom.json data/api-profile.json
node scripts/profile-reader.mjs ruta/reading.json data/reader-profile.json
```

El segundo archivo es el árbol devuelto por `/api/versions/ID/reading`. El script
del API crea y elimina su propia base; no consulta fuentes ni modifica datos del
portal. El script del lector requiere las dependencias de desarrollo del frontend.

## Despliegue y aceptación

Subir `NOM_AppService_0.6.7.zip` a Cloud Shell y ejecutar:

```bash
az webapp deploy \
  --subscription ab029082-550e-447e-bec6-b0b363b1a8c7 \
  --resource-group rg-jess01-np-eus-np-scs-02-Mexico \
  --name rg-jess01-np-eus-np-scs-02-mexico-webapp \
  --src-path NOM_AppService_0.6.7.zip \
  --type zip

az webapp restart \
  --subscription ab029082-550e-447e-bec6-b0b363b1a8c7 \
  --resource-group rg-jess01-np-eus-np-scs-02-Mexico \
  --name rg-jess01-np-eus-np-scs-02-mexico-webapp
```

Después del arranque, recargar con Ctrl+F5 y comprobar en `/api/health` que
`frontend.version` y `backend.version` sean `0.6.7`. Verificar navegación y
desplazamiento del boletín, catálogo y estado de fuentes; abrir la NOM larga,
cambiar de parte, ajustar la letra, cerrar y volver a abrir. El historial, los
documentos y la programación se conservan.

El paquete se prueba con su `startup.sh`, consulta del lector, reinicio y
respaldo/restauración en almacenamiento aislado antes de entregarlo. La
verificación visual y de tiempos en Azure se realiza después del despliegue.
