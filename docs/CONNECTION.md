# Fuentes sin conexión / Source connection failures

El diagnóstico de red comprueba únicamente la API SIDOF; no prueba acceso ni cobertura de PLATIICA. El monitor de producción usa SIDOF y el Catálogo Mexicano de Normas de PLATIICA. Los errores de otras fuentes descritos más abajo corresponden al historial de diagnóstico anterior.

La versión 0.4.1 usa **CryptoAPI de Windows mediante truststore** para construir y validar la cadena de certificados, incluidos los intermedios que Windows pueda recuperar. Linux/App Service conserva OpenSSL con autoridades del sistema y certifi. Se mantiene la validación de certificado y nombre de servidor. No se instalan certificados ni se modifica la configuración de red. Desde 0.4.0, la prueba SIDOF consulta la API de notas del día, el mismo canal usado por el descubrimiento diario.

`SSL_CERT_FILE` o `SSL_CERT_DIR`, si ya están configurados, siguen siendo la selección explícita de certificados. Una ruta inválida produce un error visible; no se sustituye silenciosamente. Los proxies de entorno y el proxy estático del sistema se siguen leyendo mediante HTTPX. No se ejecutan archivos PAC ni se copian credenciales del navegador.

Las capturas con el mensaje anterior «Tiempo de espera o conexión fallida» no permiten distinguir certificado, DNS, proxy y tiempo de espera. Se corrige esa pérdida de información con categorías específicas; no se supone cuál es la causa en la computadora del usuario.

## Evidencias recibidas · 3 de noviembre de 2026

- La pantalla muestra v0.4.0 y controles en inglés: la interfaz actual sí está cargada.
- Las cuatro fuentes muestran `TLS_CERTIFICATE`, sin consulta exitosa: esa instalación no acredita descarga ni ausencia de novedades.
- El navegador rechaza el certificado de `www.dof.gob.mx` con `NET::ERR_CERT_AUTHORITY_INVALID`. La captura no permite atribuirlo al sitio, al proxy o a una autoridad ausente del equipo.
- El navegador sí recibe JSON de SIDOF, pero abrir únicamente `/dof/sidof` devuelve un mensaje 404. Esa base configura el conector; no es una operación de consulta. La interfaz 0.4.1 enlaza al portal oficial en lugar de dirigir al lector a esa base.
- La operación real `https://sidof.segob.gob.mx/dof/sidof/notas/02-11-2026` y su manifiesto `diarios/porFecha/02-11-2026` respondieron `messageCode: 200`, `response: OK` desde el ejecutor. Esto no prueba el acceso del proceso Python corporativo.

El cambio de Windows es una corrección de compatibilidad, no una confirmación de que el equipo ya descargue las fuentes. Si DOF continúa rechazado también en el navegador, usar el diagnóstico para identificar la cadena de confianza; no aceptar ese certificado automáticamente. Los siete errores SIDOF mostrados corresponden a intentos por fecha, no a siete NOM identificadas.

## Comprobar en Windows

1. Detén el servidor anterior con Ctrl+C y usa el paquete actualizado en una carpeta nueva.
2. Ejecuta `PREPARAR_LOCAL.cmd` y después `DIAGNOSTICAR_CONEXION.cmd`.
3. El informe se guarda en `data/diagnostico_conexion.json`. Prueba las cuatro URLs públicas del piloto con el mismo cliente HTTPS y las mismas reglas de robots que el monitor. No cambia la base de datos ni añade publicaciones.
4. Abre `INICIAR_LOCAL.cmd` y vuelve a consultar las fuentes. Después de una consulta fallida o parcial se permite reintentar tras un minuto desde su finalización. Las consultas correctas conservan una espera de 15 minutos.

El informe incluye indicadores de configuración, `tls_backend_selected` y errores clasificados. Para un rechazo de certificado incluye el código numérico de verificación y una categoría conocida si están disponibles. No incluye valores de proxy, credenciales, rutas de certificados, texto interno de excepciones ni variables de entorno completas. Si una variable de red se cambia, es necesario reiniciar el portal para que el proceso nuevo la reciba.

| Código | Qué establece | Qué revisar |
| --- | --- | --- |
| ACCESS_OK | Se recuperó la URL con TLS verificado y reglas de robots respetadas | Continuar con la consulta del portal; no acredita cobertura de todas las NOM |
| TLS_CERTIFICATE | La cadena o validez del certificado no pudo verificarse | Certificados de confianza del proceso y la configuración explícita de CA; no desactivar verificación |
| TLS_CONFIGURATION | No se pudo cargar el cliente/almacén configurado | Ejecutar PREPARAR_LOCAL.cmd; revisar SSL_CERT_FILE / SSL_CERT_DIR si existen |
| TLS_HANDSHAKE | Falló la negociación TLS | Compatibilidad del sitio o proxy con la conexión segura |
| PROXY_AUTH | El proxy exige una autenticación no disponible al proceso | Método de acceso autorizado para aplicaciones; no copiar sesiones del navegador |
| PROXY_CONFIGURATION | Proxy ausente para el modo DNS proxy o formato inválido | Configuración HTTPS_PROXY/ALL_PROXY o proxy estático del sistema |
| PROXY_CONNECT | La conexión a través del proxy falló | Acceso del proceso al proxy y salida hacia las fuentes |
| DNS_ERROR | No se resolvió el nombre del sitio | DNS del equipo/servidor; modo proxy solo si ya hay un proxy configurado que resuelve nombres |
| CONNECT_TIMEOUT / READ_TIMEOUT | No conectó o no recibió respuesta a tiempo | Disponibilidad del sitio y acceso desde la red del proceso |
| ROBOTS_PENDING / SOURCE_PENDING | No se pudo completar una consulta permitida o recuperar la fuente | El mensaje identifica reglas de acceso, HTTP o formato; un fallo no significa ausencia de novedades |

No se configura ni descubre un proxy nuevo automáticamente. Si el navegador corporativo usa un PAC, su éxito no prueba que Python tenga la misma ruta de salida. Azure tiene su propia red y sus propios certificados: el resultado local no acredita conectividad desde App Service.

## English

Version 0.4.1 uses native Windows CryptoAPI through truststore to validate certificate chains. Linux/App Service retains OpenSSL with system roots and certifi. Certificate and hostname validation remain enabled. Existing explicit `SSL_CERT_FILE` / `SSL_CERT_DIR` settings remain authoritative. It does not install certificates, change network settings, run PAC scripts or reuse browser credentials. Run PREPARAR_LOCAL.cmd after updating. Since 0.4.0, the SIDOF check uses today's notes API, the same channel used for daily discovery.

Run `DIAGNOSTICAR_CONEXION.cmd` after preparation. The access report is saved to `data/diagnostico_conexion.json`. It checks the four public pilot URLs with the same verified HTTPS client and robots rules as collection, without changing the database or importing publications. An `ACCESS_OK` result confirms access to that URL, not complete NOM discovery or product applicability.

The report distinguishes certificate, TLS, proxy, DNS and timeout errors. It does not include proxy values, credentials or certificate paths. Restart the portal after changing approved network configuration. Failed or partial checks can be retried after one minute; successful checks retain their 15-minute cooldown.

Opening the SIDOF API base alone returns an unknown-service response. Collection uses dated operations such as `/notas/02-11-2026`. The visible source link now opens the official SIDOF portal. The supplied screenshots show certificate failures on the user's computer; they do not validate successful collection there. A successful test from another environment cannot replace that check.

References: [HTTPX SSL](https://www.python-httpx.org/advanced/ssl/), [Truststore](https://truststore.readthedocs.io/en/stable/index.html), [Python system certificates](https://docs.python.org/3.13/library/ssl.html#ssl.SSLContext.load_default_certs), [HTTPX environment configuration](https://www.python-httpx.org/environment_variables/).
