# Consulta por fracción y copias guardadas · 0.7.1

## Etiquetas de versiones

El listado muestra «Tiene versiones anteriores» y el filtro se llama «Con
versiones anteriores». Tener dos copias no establece una modificación oficial.
El nuevo campo API `has_previous_versions` expresa ese significado; `has_changes`
y el parámetro `changes_only` se conservan para compatibilidad con clientes anteriores.

La comparación solicitada dentro del lector distingue «Texto sin cambios»,
«Diferencias de espacios o caracteres equivalentes» y «Diferencias de texto
detectadas». No se calculan diferencias para todas las NOM al navegar. La vista
explica que sus números de versión identifican copias guardadas por NOM Monitor,
no ediciones oficiales. No se elimina ni modifica el historial existente.

## Relación entre una fracción y una NOM

La consulta anterior sólo buscaba el número en el texto guardado. Ahora también
consulta un índice documental del Anexo 2.4.1 que SNICE enlaza desde su Biblioteca
Jurídica. Sus resultados se presentan aparte de las coincidencias textuales.
Una norma puede aparecer en esa relación aunque no mencione el número en su texto.

La referencia incluida contiene **2,529 fracciones** y procede del documento
referencial con modificaciones hasta el **2 de abril de 2026**. Esa fecha se
extrae de la cabecera del documento, no del día en que se descargó. SNICE puede
publicar compilaciones que no incluyan reformas posteriores: esta referencia
no se presenta como una tabla de obligaciones vigentes ni como una decisión
de aplicabilidad. Se muestran fecha documental, fuente y acotaciones.

- Página: https://www.snice.gob.mx/cs/avi/snice/biblioteca.juridica.html
- Documento: https://www.snice.gob.mx/~oracle/SNICE_DOCS/ACUERDO-REGLAS-SE-02ABRIL2026-BIBLIOTECA_20260520-20260520.docx
- SHA-256 del documento descargado:
  `d947d0a8121a1fc542da3d68dd53811335e7f273cbce1fb8c645f07eb06ad905`

Se indexan las tablas de importación de los numerales 1, 2, 3 y 5. Se excluye el
numeral 4, de exportación, y se conservan las descripciones, acotaciones, sección
y filas NICO de cada fracción. En el numeral 3, la NOM se obtiene del encabezado
específico de su tabla, sin incluir su antecedente cancelado. No se asignan NOM
por cercanía numérica, capítulo arancelario ni similitud de productos.

Con una entrada de diez dígitos se muestran las relaciones de la fracción base
de ocho dígitos y todos sus NICO como referencia. No se decide aplicabilidad por
coincidencia de NICO. Una fila sólo abre una NOM guardada si coincide exactamente
su clave y año con un registro PLATIICA que la fuente identifica como vigente.
No se sustituye silenciosamente por una norma de otro año.

Ejemplos verificables en esta copia:

- `8501.52.04`: referencia a `NOM-016-ENER-2016`, con la acotación de la tabla.
- `8501.31.03`: referencia de información comercial `NOM-024-SCFI-2013`.
- `8501.10.01`: no aparece en esta referencia. La aplicación lo indica sin
  afirmar una exención, validez del código o inexistencia de otras obligaciones.

La búsqueda textual conserva su propósito distinto: encuentra códigos completos
o fracciones base en texto, incluso con separadores, NICO o saltos dentro de los
dígitos. El filtro SQL admite esas divisiones y acentos; la verificación final
rechaza dígitos dispersos en palabras. Las búsquedas por descripción incluyen
el campo producto/servicio y no descartan coincidencias por acentos en SQL.

## Actualización y funcionamiento

El índice comprimido se incluye en `backend/app/resources/tariff_reference.json.gz`.
No se descarga un documento externo por cada búsqueda, no se carga el índice
completo en el navegador y no se añade trabajo a la navegación del catálogo.

Con el monitor y la programación habilitados, un hilo independiente comprueba
diariamente el Word enlazado en la Biblioteca Jurídica de SNICE. Usa el cliente
existente con validación HTTPS, lista de hosts permitidos, robots y tamaños
acotados. Si los bytes no cambiaron, no vuelve a analizar el Word. Una estructura
desconocida, documento anterior, respuesta incompleta o problema de conexión
conserva el último índice válido y expone su estado en la consulta por producto.

El resultado actualizado y su estado se conservan bajo `STORAGE_PATH/_references`;
los respaldos de evidencia incluyen esa carpeta. No hay migraciones nuevas ni
cambios en la base del usuario. Una actualización manual opcional se ejecuta
desde `backend` con `python -m app.cli refresh-tariff-reference`.

En la comprobación de red de este entorno fue necesario usar el proxy ya
configurado (`SOURCE_DNS_MODE=proxy`); la descarga y comprobación SHA funcionaron.
Esto no establece la conectividad de la instancia Azure del usuario.

## Verificación

Verificación: 41 pruebas de interfaz y 263 pruebas backend, además de Ruff, Bandit
y comprobación de Alembic sin cambios de esquema. Las pruebas cubren la estructura Word, acotaciones y NICO, exclusión de exportación
y antecedentes cancelados, integridad del índice, conexión fallida, persistencia,
actualizaciones incompletas y archivos sin cambios. API e interfaz comprueban
que una relación arancelaria se muestre aunque no haya coincidencias textuales,
sin asociar una NOM de otro año. La prueba del ZIP comprueba esa consulta después
del arranque, reinicio y restauración junto con lectura y comparación de versiones.

Playwright incluye el recorrido con API real en escritorio y móvil. Su ejecución
visual sigue pendiente: este entorno bloquea el arranque de Chromium. No se
presenta esa cobertura como una prueba visual ni una medición de Azure.
