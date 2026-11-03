# Portal en Azure App Service Linux

La instalación sencilla utiliza el App Service existente: **Linux, Python 3.13, Basic B1, una instancia**. Sirve la web y ejecuta el monitor desde un solo proceso. No necesita crear PostgreSQL, Blob, Entra ni un WebJob.

## Preparar y publicar

1. En un equipo o agente con Node.js, ejecutar `cd frontend && npm ci && cd ..` y `bash scripts/package-appservice.sh`.
2. El archivo `data/nom-appservice.zip` contiene `backend/`, `frontend/dist/`, `startup.sh` y `requirements.txt` en la raíz. También incorpora el código de la interfaz y los comandos de prueba en Windows. No contiene datos locales, secretos ni entornos virtuales. No hace falta Node en App Service: la interfaz ya está compilada.
3. En App Service, configurar **SCM_DO_BUILD_DURING_DEPLOYMENT=true** y el comando de inicio **bash startup.sh**. Mantener Python 3.13 y habilitar **Always On**.
4. Publicar el ZIP mediante un método corporativo permitido o Azure CLI autenticada:

```bash
az webapp deploy --resource-group '<GRUPO_DE_RECURSOS>' --name '<NOMBRE_DE_WEB_APP>' --src-path data/nom-appservice.zip
```

No registrar nombres internos de recursos ni credenciales en el repositorio.

## Valores de arranque

El script establece estos valores solo si no se proporcionaron otros:

| Variable | Valor |
| --- | --- |
| ENVIRONMENT | production |
| AUTH_MODE | portal |
| DEV_AUTH_ENABLED | false |
| MONITOR_ENABLED | true |
| SCHEDULER_ENABLED | true |
| DATABASE_URL | sqlite:////home/nom-monitor/nom.db |
| STORAGE_BACKEND | local |
| STORAGE_PATH | /home/nom-monitor/evidence |

Si existen ajustes anteriores de Entra/Blob/PostgreSQL, revisar las variables efectivas para elegir estos valores. No copiar el modo local de administrador al despliegue público.

El modo portal permite consultar publicaciones y solicitar una revisión sin iniciar sesión. Cambiar URLs, catálogos o decisiones conserva permisos de edición; el visitante es lector. El inicio aplica migraciones e inicializa fuentes sin publicaciones inventadas. En la primera preparación habilita programación de las fuentes configuradas; respeta las que ya tengan fecha/frecuencia configuradas.

## Persistencia y consultas

El código de Python puede ejecutarse desde una carpeta temporal de Oryx. Por eso **base y documentos se guardan bajo /home/nom-monitor**, fuera del contenido desplegado. En el App Service Linux integrado, comprobar que el almacenamiento persistente de /home esté habilitado; si corresponde a la configuración, usar `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`.

Usar una instancia, `--workers 1` y el monitor integrado para este piloto con SQLite. El modo de diario de SQLite en producción es DELETE para no usar WAL sobre el volumen compartido. No se ha validado escalado a varias instancias. El monitor se detiene si se apaga o descarga el App Service; Always On mantiene cargada la app. La cola y las consultas pendientes permanecen en SQLite. Los intervalos fallidos se reintentan sin interpretar un error como ausencia de cambios.

No hace falta instalar el trabajador externo. Si se elige hacerlo más adelante, desactivar `MONITOR_ENABLED` en la web.

## Comprobar en la instancia real

- `/api/health` responde y la portada carga sin pantalla de acceso.
- Español / English cambia interfaz, fechas y la guía Cómo funciona / How it works.
- `/api/health` identifica la compilación en `frontend.version` y `frontend.source_sha256`; debe corresponder a la marca v0.4.0 de la pantalla.
- “Consultar fuentes” deja una ejecución y después resultados o un error visible.
- Una copia del documento se puede recuperar después de reiniciar la aplicación.
- Se conserva la base al volver a publicar el ZIP.
- La API diaria `https://sidof.segob.gob.mx/dof/sidof` es accesible desde Azure con TLS verificado y las reglas de robots. La primera revisión cubre siete días y después se programa cada hora.
- “Ver revisión diaria” muestra conteos y referencias pendientes. Buscar `NOM-EM-023-SE-2026` después de consultar el 2 de noviembre de 2026 permite repetir la comprobación conocida; la ventana automática puede requerir ampliar fechas si se prueba más adelante.
- DOF HTML, PLATIICA y SNICE son accesibles desde la red de Azure. Un fallo de DOF no impide procesar SIDOF, aunque seguirá mostrándose como fuente incompleta.

El paquete preparado y las pruebas locales no equivalen a un despliegue real. No se crearon ni modificaron recursos Azure durante esta preparación.

Documentación: [Python y archivos persistentes bajo /home](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python), [Always On](https://learn.microsoft.com/en-us/azure/app-service/configure-common), [publicar ZIP con compilación](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip).
