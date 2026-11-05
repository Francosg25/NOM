# Comprobaciones reproducibles

Desde `backend`:

```bash
python -m pip install --require-hashes -r requirements-dev.txt
python -m ruff check app
python -m ruff format --check app
python -m bandit -r app -ll -q
python -m pytest --cov=app --cov-report=xml:data/coverage.xml
```

La cobertura incluye ramas y falla por debajo de 80%; el informe señala módulos menos cubiertos. No se interpreta ese porcentaje como ausencia de defectos. Ruff verifica todo `app`, no sólo los archivos nuevos; Bandit bloquea hallazgos de severidad media/alta. TypeScript verifica el frontend. Las pruebas no descargan publicaciones reales.

Desde `frontend`:

```bash
npm ci
npm test
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```

Playwright arranca una API FastAPI real con una base temporal y muestras controladas. Comprueba búsqueda, ES/EN persistente, lectura con teclado, descarga, estado parcial y ausencia de desbordamiento horizontal. Ejecuta escritorio y móvil y axe WCAG A/AA. El análisis automatizado no sustituye evaluación manual de accesibilidad ni pruebas con lectores de pantalla. Se puede indicar `NOM_TEST_PYTHON` para elegir el Python autorizado; el usuario común del portal no necesita Node ni Chromium.

## Dependencias

`requirements.in` declara dependencias directas; `requirements.txt` es la resolución universal transitiva con hashes para Python >=3.12 (entornos admitidos/probados: 3.12/3.13, Linux/Windows). `requirements-dev.in/txt` separa herramientas de desarrollo del despliegue. El ZIP y Oryx usan exactamente el lock de producción. La ruta opcional Azure Blob utiliza `requirements-azure.lock`; no se instala por defecto.

Los locks se generaron con uv 0.13.5. Para regenerar desde la raíz, con esa versión en una estación de mantenimiento:

```bash
uv pip compile backend/requirements.in --universal --python-version 3.12 --generate-hashes --no-emit-index-url --no-emit-find-links -o backend/requirements.txt
uv pip compile backend/requirements-dev.in --universal --python-version 3.12 --generate-hashes --no-emit-index-url --no-emit-find-links -o backend/requirements-dev.txt
uv pip compile backend/requirements-azure.txt --universal --python-version 3.12 --generate-hashes --no-emit-index-url --no-emit-find-links -o backend/requirements-azure.lock
```

Los usuarios corporativos siguen instalando con pip; no necesitan ejecutar uv. No editar hashes manualmente ni desactivar TLS para instalar. Dependabot propone cambios mensuales de npm, pip y Actions cuando la configuración esté en la rama predeterminada. Al actualizar un input, regenerar los tres locks, revisar diferencias y ejecutar CI; no basta con cambiar sólo una versión de un lock. No hay actualización ni merge automáticos.

CI mantiene matriz backend Linux/Windows Python 3.12/3.13, adaptador PostgreSQL, calidad y recorridos de navegador. Los resultados locales deben distinguirse de la ejecución real de Actions y del App Service.
