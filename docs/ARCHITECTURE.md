# Decisiones de arquitectura

JE NOM Monitor es un monolito modular: React/TypeScript/Vite, API FastAPI, SQLAlchemy y Alembic. El backend sirve el frontend compilado; el recopilador se ejecuta como proceso independiente. No requiere Docker ni un servicio de IA.

## Límites funcionales

La recopilación produce evidencia y propuestas de relevancia. Una coincidencia no decide aplicabilidad legal ni permite/prohíbe importar. Los revisores deben contrastar el documento oficial y justificar sus decisiones. Un documento sin coincidencias permanece en revisión general. Las familias y reglas son datos editables; no hay una lista de tipos de producto codificada.

Las fechas de publicación, detección y vigencia son distintas. Una detección reciente puede corresponder a una publicación antigua. No se infiere una fecha de vigencia desde frases ambiguas. Las consultas se registran en UTC y la interfaz las presenta en America/Mexico_City.

## Persistencia y procesos

- SQLite se reserva al desarrollo. Producción requiere PostgreSQL administrado persistente, por ejemplo Azure Database for PostgreSQL Flexible Server, sujeto a aprobación y disponibilidad corporativa.
- Las migraciones se ejecutan explícitamente antes de arrancar; no deben ejecutarlas simultáneamente todas las instancias.
- Los trabajos se solicitan por API y se conservan en la base. El servidor web no ejecuta la recopilación en una tarea efímera de memoria. Se necesita un trabajador independiente para consumir la cola.
- Se conserva cada cambio respecto de la versión anterior, incluidas reversiones. El hash de contenido no elimina la historia A → B → A.
- Evidencia mediante almacenamiento local en desarrollo o Azure Blob Storage en producción. Un archivo en el disco temporal de App Service no es almacenamiento de producción.
- Mantener la base y Blob bajo políticas de copia de seguridad, retención y acceso corporativas. Las referencias de evidencia no deben ser URLs públicas de contenedores.

## Autenticación

Los roles son consulta, revisor y administrador. El backend verifica permisos en cada operación protegida. El modo local requiere activación explícita y no debe utilizarse en producción. Entra ID usa tokens de acceso firmados para la audiencia de la API, emisor y tenant configurados. La interfaz permite suministrar un token sin persistirlo; una experiencia SSO corporativa con MSAL puede integrarse posteriormente.

No se confía en cabeceras de identidad añadidas por un cliente. La autenticación de App Service puede añadirse como capa adicional, pero no sustituye la configuración de validación de la API. No se han creado registros de aplicaciones, roles ni recursos de Azure.

## Extensibilidad

Los conectores se separan del trabajo, la API, el almacenamiento y las reglas. La interfaz opcional de análisis permite incorporar IA posteriormente con evidencia e incertidumbre, sin que sea necesaria para arrancar.

## Estado inicial

El repositorio recibido no tenía archivos ni commits. No se encontró AGENTS.md ni NOM_Monitor_Piloto.zip en los archivos disponibles. No se afirma haber revisado o reutilizado ese piloto. Los parsers y su cobertura deben contrastarse con respuestas oficiales actuales antes de confiar en la vigilancia operativa.
