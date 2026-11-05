# Revisión humana de cobertura

El monitor guarda publicaciones seleccionadas por las reglas de SIDOF. No acredita que haya recuperado toda la normativa ni determina aplicabilidad a un producto. La interfaz no cambia esa distinción.

Para cada periodo aceptado, una persona designada por JE contrasta el inventario oficial de SIDOF (fechas y ediciones) con el informe de revisión diaria. Incluir NOM definitivas y de emergencia, proyectos, modificaciones, cancelaciones, aclaraciones y acuerdos de comercio exterior dentro del alcance acordado. Revisar especialmente títulos sin texto, referencias sin clasificar, fechas fallidas y ediciones extraordinarias. Conservar enlaces, IDs y justificación de exclusiones.

1. Definir periodo, criterios de inclusión/exclusión y responsable. No limitarlo a motores si se pretende cubrir otras familias JE.
2. Construir el inventario manual independiente de IDs esperados. No usar la propia salida del recolector como patrón de verdad.
3. Comparar lo esperado con lo recuperado mediante la herramienta existente:

```bash
python -m app.cli validate-sources --start AAAA-MM-DD --end AAAA-MM-DD --expected inventario.json --output data/revision.json
```

Formato de `inventario.json`: `{"sidof": ["DOF:ID_OFICIAL_1", "DOF:ID_OFICIAL_2"]}`. Los IDs del ejemplo son marcadores, no publicaciones reales. La herramienta consulta el sitio y guarda evidencia: ejecutarla cuando se autorice la validación en el entorno correspondiente.

4. Clasificar cada diferencia: omitido por el recolector, excluido por regla documentada, referencia pendiente o indisponibilidad oficial. Un HTTP 404 no demuestra que el día no tenga publicación.
5. Resolver omisiones, repetir sin duplicados y registrar aceptación o rechazo. El responsable normativo evalúa por separado producto, fracción, vigencia y transición con su evidencia oficial.

Registro mínimo por revisión:

| Campo | Contenido requerido |
| --- | --- |
| Periodo y alcance | Fechas, ediciones y tipos incluidos |
| Responsable y fecha | Persona que contrastó las fuentes |
| Inventario esperado | IDs y enlaces obtenidos independientemente |
| Recuperados / omitidos | Conteos e IDs; conservar informe |
| Pendientes | Fechas fallidas y referencias sin clasificación |
| Decisión | Aceptado para el periodo/alcance indicado o rechazado, con motivo |
| Aplicabilidad | Evaluación separada por responsable normativo; nunca automática |

No hay responsable ni aceptación ficticia en esta rama. La prueba técnica y la aceptación normativa son evidencias distintas.
