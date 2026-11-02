# Validación y limitaciones

Validación realizada el 2 de noviembre de 2026 en Linux con Python 3.12.14 y Node 24.19.0. Se usó un entorno virtual del proyecto y el lockfile de npm. No se desplegó Azure.

## Comprobaciones ejecutadas

| Comprobación | Resultado |
| --- | --- |
| Instalación `bash scripts/setup.sh` | Pasó: dependencias, `npm ci`, compilación y migraciones. Repetición idempotente con `.env` existente. |
| Backend `python -m pytest -q` | 78 pruebas aprobadas; ninguna fallida, omitida ni esperada como fallo. |
| Alembic `upgrade head` y `check` | Dos revisiones aplicadas, sin diferencias de esquema. |
| Frontend `npm run build` | TypeScript y Vite aprobados; 29 módulos. |
| Dependencias Python `pip check` | Sin incompatibilidades detectadas. |
| Navegador Chromium | Cinco vistas, pantalla vacía, tabla de demo, detalle, descarga de evidencia, confirmación con autor/fecha, comentario y modo consulta comprobados. Sin errores JavaScript en ese recorrido. Vista móvil comprobada. |
| Reinicio real de procesos web | La decisión, autor, comentario, archivo de evidencia y trabajo parcial siguieron disponibles con la misma base. |
| Consulta manual real DOF por API + CLI | Registró trabajo, último intento, error y continuación. No creó publicaciones ni marcó última consulta exitosa. `worker --once` devolvió 2 (parcial), no un éxito falso. |

La suite incluye deduplicación entre ejecuciones, versiones A→B→A, reapertura auditada de revisiones tras un cambio, recuperación de errores, edición/paginación de índices DOF con muestras controladas, cola y periodos parciales, reanudación después de interrupción, cambio de configuración de fuente, exclusión mutua y propuestas de relevancia al editar reglas. Cubre fechas desconocidas/verificadas, confirmación/descarte, permisos, JWT firmados, auditoría, SSRF, robots, tamaños y demostración separada.

El recorrido principal automatizado es `tests/test_jobs.py::test_main_flow_query_propose_review_and_evidence`: solicitud HTTP de consulta → procesamiento con conector inyectado → publicación persistida → propuesta basada en palabra clave → confirmación humana → comentario → descarga autenticada de evidencia. La respuesta de la fuente en esa prueba es una muestra sintética controlada, **no una consulta oficial validada**.

Los tests de autenticación usan firma RSA y claves controladas para verificar firma, audiencia, emisor, tenant, expiración y permisos. No validan un registro Entra real. Las pruebas de base se ejecutan sobre SQLite temporal y no prueban un PostgreSQL remoto.

El aislamiento de red del ejecutor bloqueó el IPC interno de TestClient; se resolvió usando la excepción de ejecución soportada, conservando los tests. Hay una advertencia de depreciación de `anyio.abc.BlockingPortal` en Starlette; no impide las comprobaciones. La primera compilación señaló un import no utilizado, ya corregido. No quedan fallos de validación local sin diagnosticar.

## Pendiente de validar

- Acceso y parsers con respuestas oficiales actuales de DOF, PLATIICA y SNICE. Una comprobación de robots DOF fue negada por el proxy con CONNECT 403; la consulta manual posterior tampoco pudo verificar DNS oficial desde este ejecutor. No hubo contenido oficial para validar. El borrador de red guardado no aplica permisos a la instancia actual.
- Todas las ediciones y fechas de un periodo conocido, incluidos días sin publicación, con contraste manual. Las muestras sintéticas no prueban cobertura oficial.
- URLs reales de fichas PLATIICA y publicaciones SNICE; no estuvieron disponibles las tres URLs del piloto ni su ZIP.
- Ejecución nativa en Windows corporativo. Hay comandos sin activación de venv ni Docker y dependencia `tzdata`, pero no se probó un equipo Windows en esta sesión.
- PostgreSQL administrado, Blob Storage, identidad administrada, Entra SSO y App Service reales. Deben probarse después de confirmar SO/runtime/plan, red y configuración, con autorización de despliegue.
- Programación automática y supervisión del trabajador. No se activó ningún temporizador ni servicio de pago.

## Limitaciones concretas de la primera versión

1. DOF usa un índice HTML diario candidato y enlaces visibles. No se garantiza descubrir ediciones no enlazadas, enlaces generados por JavaScript, anexos no enlazados ni correcciones fuera del periodo solicitado. SIDOF no se implementa como API supuesta.
2. PLATIICA y SNICE siguen documentos configurados; no descubren todas sus novedades. La consulta de una ficha actual no reconstruye automáticamente su historia anterior.
3. PDF directo se descarga y extrae hasta 150 páginas. No hay OCR. Un archivo escaneado o ilegible deja un pendiente. Descargas mayores a 12 MiB quedan como URL pendiente en la continuación del trabajo y requieren intervención; no se almacena un archivo incompleto como evidencia íntegra.
4. La extracción HTML general puede incluir ruido y dejar avisos de revisión. Una misma NOM publicada en dos agencias se conserva como dos documentos de fuente; no se fusiona automáticamente su identidad jurídica.
5. Los criterios son transparentes y orientativos. No analizan por sí solos excepciones, transitorios, fechas relativas, alcance técnico ni aplicabilidad legal. No hay IA contratada ni decisiones automáticas de importación.
6. La cola necesita un trabajador externo al proceso web. La frecuencia de una fuente es metadato hasta configurar un programador. La recuperación de un proceso muerto se detecta por arrendamiento vencido al volver a atender la cola/solicitar trabajo.
7. El acceso corporativo está preparado mediante validación de tokens. La interfaz permite un token en memoria y puede aprovechar el token de App Service si TI configura ese flujo; no incluye un registro Entra ni una experiencia MSAL aprovisionada.
8. La reevaluación del catálogo es síncrona y adecuada al primer volumen de uso. Para un catálogo/archivo grande conviene trasladarla a trabajos paginados. No se implementaron notificaciones por correo ni exportación, fuera del alcance solicitado.
9. No se realizaron pruebas de carga ni una auditoría formal de seguridad. Antes de producción deben definirse monitoreo, copias, retención, asignaciones corporativas y recuperación operativa.

## Configuración reutilizable del entorno cloud

Se guardaron `install_script`, `start_skill` y seis destinos oficiales en el borrador de configuración del entorno. Los presets de paquetes existentes se conservaron. No se solicitaron secretos ni se inventaron credenciales de Azure. El guardado no ejecuta instrucciones, aplica red ni publica una imagen.

Para reutilizar la configuración, revise y guarde los cambios en los ajustes del entorno y publique el entorno cloud. Esa publicación es independiente de un despliegue en Azure. No se ha validado una restauración en una tarea nueva.
