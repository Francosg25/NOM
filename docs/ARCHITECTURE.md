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

Los roles son consulta, revisor y administrador. El backend verifica permisos en cada operación protegida. El modo local requiere activación explícita y no debe utilizarse en producción. Entra ID usa tokens de acceso firmados para la audiencia de la API, emisor y tenant configurados. La interfaz integra MSAL con redirección, tokens de acceso y renovación silenciosa. Usa sessionStorage para la sesión MSAL. El modo normal no solicita pegar tokens. El código se carga solo cuando existe configuración Entra; falta validar el tenant real.

No se confía en cabeceras de identidad añadidas por un cliente. La autenticación de App Service puede añadirse como capa adicional, pero no sustituye la configuración de validación de la API. No se han creado registros de aplicaciones, roles ni recursos de Azure.

## Extensibilidad

Los conectores se separan del trabajo, la API, el almacenamiento y las reglas. La interfaz opcional de análisis permite incorporar IA posteriormente con evidencia e incertidumbre, sin que sea necesaria para arrancar.

## Estado inicial

La implementación inicial partió de un repositorio vacío. En esta ampliación se revisó NOM_Monitor_Piloto.zip, se incorporaron sus URLs y se verificó la evidencia de tres descargas reales. El repositorio público conserva informes, hashes y extractos reducidos; excluye las páginas HTML completas con metadatos y contactos. La cobertura diaria DOF sigue pendiente; ver PILOT_ACCEPTANCE.md.

## Colas, programación y lecturas

Los cambios de catálogo incrementan una revisión pendiente por registro y descendientes. El trabajador procesa publicaciones por cursor en lotes; propuestas y cursor se confirman en la misma transacción. Los bloqueos PostgreSQL y la actualización condicional evitan que un guardado requiera recorrer el archivo. Las decisiones previas se conservan.

La programación reside en el trabajador supervisado, con activación global y por fuente. Los intervalos incompletos se reintentan antes de avanzar. Ningún timer depende del proceso HTTP o del navegador. Las consultas y versiones se deduplican; el siguiente periodo conserva un solapamiento reciente.

Las listas cargan nombres y evidencia de vigencia en consultas agrupadas, con índices de apoyo. El frontend carga el catálogo de opciones al abrir un selector, no en cada pantalla ni cada 2.5 s. El seguimiento de trabajos usa sondeo de 5 s sin descargas de catálogo y se pausa en pestañas no visibles.

El hash de versión incluye enlaces oficiales extraídos, para detectar sustituciones de documentos aunque el texto visible sea igual. En la primera consulta posterior a esta migración puede crearse una versión adicional por el nuevo formato de comparación, aun si no cambió el contenido normativo. No se presenta esa versión técnica como cambio legal.

Cada documento observado deja un registro de auditoría ligado al trabajo y a su
versión, también cuando no cambió. La aceptación usa esas observaciones actuales,
no el inventario histórico de la base. El archivo asociado a una ejecución puede
recuperarse aunque después se publique otra versión.
