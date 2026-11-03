# Validación del portal

## Cambio de alcance · 3 de noviembre de 2026

El boletín abre sin cuenta con SQLite y archivos locales; el monitor está integrado y la interfaz es un boletín en español/inglés. Entra, Blob y PostgreSQL dejaron de ser requisitos. La interfaz anterior de catálogo y decisiones sigue disponible solo por API/CLI.

| Comprobación actual | Resultado |
| --- | --- |
| Backend | 112 pruebas aprobadas; incluye acceso abierto sin permisos de edición, orden por fecha oficial, cambios, cola y monitor integrado |
| Frontend | TypeScript/Vite aprobados, 31 módulos; se retiró MSAL |
| Interacciones ES/EN | Verificadas sobre el JS compilado con JSDOM y una respuesta API controlada: idioma persistente, búsqueda, temas, lectura/cierre y fuentes de solo lectura |
| Paquete Linux | Arranque real de startup.sh con ENVIRONMENT=production y sin Entra/Blob/PostgreSQL; la web/API responden y SQLite/evidencia sobreviven un reinicio |
| Runtime de esta comprobación | Python 3.12; destino configurado para App Service Python 3.13, todavía sin prueba en Azure |
| Revisión visual | Pendiente: Chromium local no estuvo disponible y el navegador remoto rechazó el acceso al archivo local por política |

La prueba de interacciones es de DOM, no una comprobación visual ni de diseño móvil en un navegador. La aceptación de cobertura DOF que sigue continúa pendiente.

## Resultados del piloto anterior · 2 de noviembre de 2026

### Capturas reales

El programa descarga y conserva tres documentos oficiales configurados. La
aceptación de descubrimiento DOF sigue **sin aprobar**: su `robots.txt` responde
HTTP 503 desde este ejecutor. No se omitió esa comprobación.

| Comprobación ejecutada | Resultado |
| --- | --- |
| Backend `python -m pytest -q` | **113 aprobadas**, sin fallos ni omisiones; una advertencia de depreciación de Starlette/AnyIO |
| Frontend `npm run build` | TypeScript y Vite aprobados, 187 módulos; MSAL en un módulo separado |
| Dependencias `python -m pip check` | Sin incompatibilidades |
| Base nueva: `init-db` y `alembic check` | Tres revisiones aplicadas; sin diferencias de esquema |
| Consulta real del recopilador | PLATIICA, SNICE y SIDOF conocido completados; DOF diario parcial con error visible |
| Evidencia recuperada | SHA-256 correcto para los tres documentos |
| Repetición real | Tres documentos observados otra vez; cero versiones adicionales |
| Muestra pública JE y reevaluación | 11 registros, incluidos cuatro borradores de producto; propuestas pendientes de un responsable |

Evidencias reproducibles: [aceptación final por ejecución](evidence/acceptance-final.json),
[primera descarga](evidence/acceptance-first.json),
[repetición inicial](evidence/acceptance-repeat.json),
[catálogo y propuestas](evidence/catalog-proposals.json) y
[procedencia y hashes de los extractos](../backend/tests/fixtures/official/provenance.json).

`technical_passed` exige completar las fuentes activas y recuperar su evidencia.
`coverage_verified` exige además que el inventario DOF **observado en los trabajos
de esa validación**, con fechas explícitas, coincida con el inventario revisado
manualmente del periodo. `passed` requiere ambos. Ninguno certifica aplicabilidad
legal ni cobertura de documentos que las fuentes configuradas no descubren.

## Regresiones cubiertas

- Descubrimiento con índices, paginación, ediciones adicionales, límites y
  continuación; error de una URL, índice desconocido y día explícitamente vacío.
- Un enlace del índice a sí mismo no acredita cobertura; una nota fechada fuera
  del periodo no se incorpora silenciosamente.
- Inventarios históricos no satisfacen la aceptación de una consulta nueva.
  También se comprueban evidencia corrupta, fechas desconocidas e inventarios
  mal formados. La repetición conserva observación aunque no cree una versión.
- Versiones A→B→A, enlaces modificados, recuperación de evidencia, reapertura
  auditada, arrendamientos de trabajos y decisiones humanas conservadas.
- Cola durable y por lotes al editar catálogo; herencia de reglas y programación
  voluntaria con recuperación de intervalos y espera tras fallos.
- Búsquedas por modelo/contenido; consultas SQL agrupadas para que las listas
  no hagan una consulta adicional por fila.
- Firma RSA, tenant, emisor, audiencia, expiración y roles para la opción Entra;
  el portal de lectura no requiere esa opción.
- Destinos HTTPS permitidos, redirecciones, robots, límites y compresión HTTP;
  rechazo de portadas e índices incompatibles desde el formulario de fuentes.

Los tests de conectores inyectados siguen siendo muestras controladas. Los de
`test_official_snapshots.py` usan extractos públicos reducidos de las capturas,
en una estructura HTML mínima preparada para pruebas. Se conserva un hash de
extracto separado del hash original; no validan el DOM íntegro del portal, una
nueva consulta de red ni cobertura integral. Las páginas completas se excluyen
del repositorio público para no publicar metadatos o contactos del HTML.

## CI y comprobaciones pendientes

Se incluye CI con suite y compilación en Linux/Windows y una comprobación
independiente sobre PostgreSQL 16: migraciones, persistencia, versiones,
herencia, cola y programación. Su resultado se consulta en GitHub; la ejecución
local anterior usa SQLite y no se presenta como validación de PostgreSQL.

La [ejecución de CI del PR](https://github.com/Francosg25/NOM/actions/runs/41540706173)
terminó antes de asignar un ejecutor y no ejecutó ningún paso. Por tanto,
Linux/Windows en Actions y PostgreSQL siguen **sin validar en CI**; los resultados
aprobados de esta página corresponden a la ejecución local. El impedimento de
la cuenta de GitHub debe resolverse antes de repetir esas comprobaciones.

La comprobación visual de esta ampliación no se completó. El navegador remoto
no alcanzó la aplicación local; el ejecutor no tiene un Chromium utilizable.
La compilación aprobada no sustituye una prueba visual, móvil o de SSO.

Para verificar el boletín faltan: descubrimiento y contraste manual del periodo DOF,
revisión visual, prueba en el equipo Windows corporativo y en el App Service real.
Las fichas JE y decisiones solo son necesarias si se utiliza la función adicional de aplicabilidad.
Entra, PostgreSQL y Blob son opciones y no condiciones para abrir el boletín.
No se desplegó Azure ni se instalaron
servicios permanentes. El [procedimiento de aceptación](PILOT_ACCEPTANCE.md)
explica cómo repetir cada comprobación y qué evidencia debe aportar JE.
