# Preparación de despliegue en Azure App Service

Este documento prepara el despliegue; no publica ni crea recursos. Antes de desplegar, confirmar con TI:

1. Sistema operativo de App Service, plan, runtime Python soportado, arquitectura y mecanismo de despliegue. No se presupone Linux ni compatibilidad con WebJobs.
2. Tenant Entra ID, registro de la API y cliente, audiencia, asignación de roles `consulta`, `revisor`, `administrador`, usuarios/grupos autorizados y redirecciones. Rechazar acceso anónimo.
3. Base PostgreSQL administrada aprobada, TLS, DNS, firewall/red privada, credencial de ejecución y de migraciones. No existe una base corporativa asumida.
4. Cuenta y contenedor privado de Blob Storage, identidad administrada con Storage Blob Data Contributor, retención y copias de seguridad. No usar el disco temporal para evidencia o base.
5. Salida HTTPS a las fuentes, robots.txt y condiciones de acceso; DNS, proxy corporativo y CA de confianza. Nunca desactivar TLS ni sortear CAPTCHA.
6. Dónde correr el trabajador, reinicios, supervisión y frecuencia. No activar programación hasta validar una consulta manual y un periodo retrospectivo.

Para Entra, configurar tokens de acceso **v2** para la API (`api.requestedAccessTokenVersion=2` en su registro), audiencia exactamente igual a `ENTRA_AUDIENCE` y tenant GUID en `ENTRA_TENANT_ID`. Definir y asignar los tres roles de aplicación indicados. Los tokens de identidad de otro cliente no sustituyen el token de acceso para la API. Si se usa el token store de App Service, confirmar scopes y que `/.auth/me` entregue ese token de acceso; el backend seguirá comprobando firma, emisor, audiencia, tenant, expiración y roles. Si ese flujo no se configura, la interfaz admite pegar un token en memoria para una prueba controlada; no implementa adquisición interactiva MSAL por sí sola.

## Compilación y paquete

En un agente de compilación con Node y Python compatibles:

```bash
cd frontend
npm ci
npm run build
cd ../backend
python -m pip install -r requirements.txt
python -m pytest -q
```

Empaquetar `backend/` y `frontend/dist/` manteniendo su disposición relativa. El runtime no necesita Node si recibe el frontend ya compilado. Conservar `requirements.txt`, `alembic.ini`, migraciones y módulos de `app`. No incluir `.env`, `.venv`, datos de pruebas, bases SQLite ni credenciales.

Configurar mediante ajustes de aplicación las variables de `.env.example` adaptadas a producción. `ENVIRONMENT=production`, autenticación local deshabilitada, conexión PostgreSQL con TLS, almacenamiento Blob y tenant/audiencia reales. Los secretos se suministran mediante configuración segura o referencias Key Vault aprobadas, nunca en el repositorio.

Antes de dar tráfico: ejecutar `python -m alembic upgrade head` desde `backend/`, con una sola instancia de migración y respaldo previo. Después inicializar las fuentes según README. Las migraciones son explícitas y no se ejecutan automáticamente al iniciar cada servidor.

Si se confirma App Service Linux con Python, un comando de inicio posible desde `backend/` es:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Configurar el directorio de trabajo/puerto según el mecanismo de despliegue real. Si App Service es Windows y no ofrece el runtime Python requerido, confirmar un alojamiento compatible aprobado o cambiar el SO con autorización; no se afirma que el mismo comando resuelva esa incompatibilidad.

## Trabajador y programación: decisión pendiente

El trabajador usa el mismo PostgreSQL y Blob que la API. Primero levantar el consumidor de cola en un proceso supervisado y solicitar el trabajo manual desde la aplicación. Comprobar el identificador, progreso persistente, evidencia y resultados.

Alternativas a evaluar según el plan y SO: WebJob continuo/programado si es compatible, Azure Functions con temporizador que encole/ejecute el comando, o un agente corporativo/Windows Task Scheduler aprobado. No ejecutar simultáneamente varios programadores. Un temporizador debe encolar el intervalo explícito y usar la deduplicación del trabajo. La frecuencia deseada de una fuente es metadato: por sí sola no activa programación.

Una ejecución parcial conserva continuación; una fallida no equivale a un periodo cubierto. Revisar interrupciones, completar retrospectivas y verificar todas las ediciones antes de marcar cobertura. Mantener alertas operativas por fallos reiterados o ausencia de consultas exitosas.

## Comprobación después del despliegue

- `/api/health` responde; una ruta API protegida rechaza al anónimo.
- Un usuario consulta no puede cambiar catálogo ni decisiones; revisor y administrador tienen sus permisos esperados.
- La UI compilada carga desde FastAPI y las llamadas usan la misma aplicación.
- Una consulta manual deja trabajo y evidencia recuperables después de reiniciar web y trabajador.
- PostgreSQL y Blob permanecen disponibles después de reiniciar/escalar App Service.
- Revisar logs sin tokens ni contenidos sensibles; definir retención y responsables operativos.

La compilación local no valida el runtime, SSO ni conectividad de Azure. Esas pruebas requieren la configuración real y autorización de despliegue.
