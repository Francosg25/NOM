# Validación del portal

## Estados y ciclo automático · 0.5.1

158 pruebas backend aprobadas en Linux/Python 3.12. Se distinguen la última descarga de publicaciones, el último periodo completado y las fechas pendientes a partir del cursor persistido. El estado no afirma conectividad actual a partir de una descarga histórica.

Una prueba con reloj controlado ejecuta tres ciclos del programador sin intervención del portal: primera descarga, repetición horaria sin versiones duplicadas y día siguiente con una publicación nueva pese a un HTTP 404 histórico. Es una simulación del ciclo; no equivale a observar un servidor real durante 24 horas. Los reinicios y persistencia se comprueban en el ZIP Linux. Windows y Azure real siguen pendientes de comprobación en sus entornos.

## SIDOF único e interfaz simplificada · 0.5.0

156 pruebas backend aprobadas. Se comprueba que la actualización conserva documentos y evidencia, retira las fuentes anteriores y cancela sus trabajos en cola, de manera idempotente. El filtro del boletín selecciona SIDOF sin eliminar el archivo histórico. Compilación TypeScript/Vite y recorrido ES/EN del JS compilado comprobados. La revisión visual de escritorio utiliza muestras controladas, sin presentarlas como publicaciones reales. No se probó esta entrega en Windows ni se desplegó Azure.

## Compatibilidad Windows · 0.4.1 · 3 de noviembre de 2026

Las capturas del equipo corporativo confirman la interfaz 0.4.0 y el idioma
inglés, pero muestran TLS_CERTIFICATE en las cuatro fuentes, sin consultas
exitosas. El navegador también rechaza DOF; SIDOF responde al navegador y su
base sin operación devuelve un mensaje 404. [Análisis y procedimiento](CONNECTION.md).

La versión 0.4.1 usa el cliente de certificados nativo de Windows, añade el
backend elegido y códigos de verificación al diagnóstico, enlaza al portal
SIDOF y agrupa los botones de cada ejecución para evitar una fila separada
para Retomar. No se aceptan certificados desconocidos automáticamente.

154 pruebas backend aprobadas, incluidas selección de CryptoAPI mediante una
dependencia controlada, prioridad de CA explícita, dependencia ausente y
diagnóstico sin datos privados. Las pruebas se ejecutaron en Linux/Python 3.12;
la rama Windows se verificó con inyección de dependencias, no con un Windows
real. La conectividad corporativa debe volver a comprobarse con el diagnóstico
de esta versión. Las pruebas anteriores no acreditan acceso en ese equipo.

## SIDOF diario · 0.4.0 · 3 de noviembre de 2026

| Comprobación | Resultado |
| --- | --- |
| Backend | 150 pruebas aprobadas: incluye contrato JSON, tres ediciones, selección, notas sin título, fechas/identidades contradictorias, evidencia, repetición, continuaciones y errores independientes por día |
| Frontend | TypeScript/Vite aprobados; 32 módulos y marca de compilación 0.4.0 |
| ES/EN | Interacciones del JS compilado con JSDOM: lector diario, conteos, referencias pendientes y enlaces oficiales, además del recorrido y pruebas de idioma anteriores |
| Paquete Linux 0.4.0 | ZIP extraído y startup.sh ejecutado en modo producción; lectura pública, edición restringida y SQLite/evidencia conservados después de reiniciar; sin Entra/Blob/PostgreSQL |
| Prueba real SIDOF | Cinco publicaciones en cinco fechas; 523 notas examinadas; JSON conservado y recuperable. La NOM del 2 de noviembre se repitió con cero versiones adicionales |
| Límites observados | 51 referencias sin clasificación; dos fechas con HTTP 404. No se aprueba cobertura integral de NOM |

El [detalle de la integración](SIDOF_DAILY.md) y el [informe reducido de evidencia](evidence/sidof-daily-2026-11-03.json)
separan consulta técnica, preservación y cobertura. La base de prueba y las
respuestas completas no se incluyen en el repositorio ni en el ZIP. La prueba
usa Python 3.12/Linux; Windows corporativo, Python 3.13 y Azure real siguen
pendientes de comprobación en esos entornos.

## Antecedente 0.3.1 · 3 de noviembre de 2026

La versión **0.3.1** abre sin cuenta con SQLite y archivos locales; el monitor está integrado y la interfaz es un boletín en español/inglés. Incorpora guía de uso, aviso de cobertura incompleta y selector de idioma con nombres completos. El cliente HTTPS carga autoridades del sistema y públicas, respeta almacenes explícitos y clasifica errores de red sin registrar credenciales. Entra, Blob y PostgreSQL son opcionales. La interfaz anterior de catálogo y decisiones sigue disponible solo por API/CLI.

| Comprobación actual | Resultado |
| --- | --- |
| Backend | 130 pruebas aprobadas; incluye contexto TLS verificado, clasificación de errores, informe seguro y reintento de fuentes fallidas, además de la identidad de la compilación, monitor, acceso abierto y cola |
| Frontend | TypeScript/Vite aprobados, 32 módulos; compilación con versión y huella de sus fuentes |
| Interacciones ES/EN | Verificadas sobre el JS compilado con JSDOM y una respuesta API controlada: idioma persistente, URL `?lang=en`, búsqueda, temas, lectura/cierre, guía, fallo de todas las fuentes y descripción de error TLS en ambos idiomas |
| Paquete Linux | Arranque real de startup.sh con ENVIRONMENT=production y sin Entra/Blob/PostgreSQL; la web/API responden y SQLite/evidencia sobreviven un reinicio |
| Runtime de esta comprobación | Python 3.12; destino configurado para App Service Python 3.13, todavía sin prueba en Azure |
| Revisión visual de escritorio | Portada, navegación horizontal y guía ES/EN verificadas en la entrega 0.3.0 con respuestas controladas; el cambio de conexión 0.3.1 se verificó con pruebas backend y DOM, sin nuevas consultas en vivo |
| Windows | Los `.cmd` requieren comprobación en un equipo Windows; el entorno de validación es Linux |

La prueba de DOM comprueba interacciones; la vista de navegador comprueba el escritorio. La comprobación visual móvil y la aceptación de cobertura DOF que sigue continúan pendientes. El ZIP incorpora los comandos y archivos para probar en Windows, además de su entrada `startup.sh` para Azure. El arranque local impide servir una interfaz compilada con fuentes anteriores y avisa si ya existe otro servidor en el puerto.

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
