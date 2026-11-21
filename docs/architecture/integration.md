# Integración local de EarthLens

Historial de la integración inicial. La ampliación posterior de Radar y
Fingerprint está documentada en [products.md](products.md).

Verificación del 14 de noviembre de 2026 en `feature/backend-api`. Los cambios
permanecen locales, sin commits, push ni modificaciones de `main`.

## Causa del problema de arranque

La comparación se hizo después de `git fetch origin`:

| Referencia | Contenido relevante |
| --- | --- |
| `feature/backend-api`, `9066cdd` | API, proveedor, catálogo, caché y Docker; sólo plantillas de Resultados y Comparador. `app.py` tenía `static_folder=None` y ninguna ruta de páginas. |
| `origin/main`, `d56d8ae` | Portada, Explorador y recursos compartidos; otro `app.py`, con llamadas NASA propias y contratos incompatibles. No contenía el backend, sus pruebas ni sus archivos Docker. |
| `origin/datasets-missions`, `fbd7d0a` | Catálogos, misiones interactivas, hipótesis y recomendador. Tampoco se había integrado en `main`. |
| `origin/feature/statistics`, `04428a2` | Interfaz de Resultados y Comparador; todavía no contenía el motor Python. |
| `origin/results-charts`, `e33c76d` | Motor `services/science/trend_analysis.py`, pruebas, catálogos y otro arranque Docker en 8000. Su proveedor activaba por defecto un respaldo con muestras y ajustes generados, sin identificar su origen en la respuesta. |

No era un fallo del motor Docker: el contenedor de la API ya estaba saludable.
Abrir `/` daba 404 porque sólo se habían registrado rutas `/api`.

## Todos los archivos Docker encontrados

| Referencia | Archivos |
| --- | --- |
| Rama de trabajo | `Dockerfile`, `compose.yaml`, `.dockerignore` |
| `origin/main` | Ningún Dockerfile ni Compose |
| `origin/results-charts` | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `docs/history/legacy/docker-entrypoint.sh` |

Se conserva una sola configuración activa: `Dockerfile` + `compose.yaml`.
El frontend usa HTML/Jinja, JavaScript, Bootstrap, Leaflet y Chart.js; no requiere
Node, npm, Vite ni otro proceso. Flask sirve páginas, estáticos y API en el mismo
origen. No se agregó un segundo Compose, un contenedor de frontend ni CORS.

El Docker alternativo copiaba toda la carpeta a `/app` y `/app_baked`, montaba el
host en `/workspace` y ejecutaba otro servidor en 8000; no compartía la caché
científica del backend. No se adoptaron ese arranque ni su proveedor alternativo.

## Qué se integró

- Se incorporaron los nueve archivos faltantes de portada/Explorador de `origin/main`.
  Se conservaron los paneles, mapas, gráficos y exportación CSV del equipo.
- El motor `services/science/trend_analysis.py` y `services/science/datasets.py` se copiaron de
  `origin/results-charts`. El código del motor se conserva idéntico a `e33c76d`.
- `services/science/analysis_service.py` adapta las series mensuales reales al contrato
  existente del motor. No duplica regresiones ni sustituye su implementación.
- La interfaz usa `/api/cities`, `/api/variables`, `/api/summary`, `/api/analyze`
  y `/api/compare` mediante `static/js/shared/api.js`. Los errores se muestran sin
  reemplazarlos por datos simulados. Los gráficos y CSV usan la respuesta real.
- Los seis endpoints anteriores conservan su contrato. Las rutas nuevas también
  usan `status`, `data`, `meta` y errores públicos controlados.
- Se conservó la interfaz original de misiones de `origin/datasets-missions`,
  con hipótesis, pistas y recomendador, conectada al catálogo y método vigentes.
  Se agregó una página de metodología. Las hipótesis son preguntas, no resultados.
- Las ubicaciones se eligen por ID del catálogo argentino y usan sus coordenadas
  oficiales. No se habilitan coordenadas libres ni presets internacionales.
- Los recursos sintéticos heredados del motor quedaron exclusivamente en `tests/`.
  No se importan desde la aplicación ni se usan como respaldo científico.

El catálogo original de misiones se conserva como `services/science/guided_missions.py`
con archivos separados `data/guided_missions.json` y `data/mission_variables.json`.
`services/science/mission_service.py` construye enlaces por ID, proyecta las unidades y el
método activos y mantiene el recomendador. Su agregador alternativo de medias
ponderadas, acumulados y extremos anuales permanece como código del compañero y
pruebas; no se utiliza en el flujo OLS actual. No se mezclan esos criterios.

## Contrato del adaptador estadístico

Entrada del motor: diccionario mensual `YYYYMM -> número | None`, derivado de
`series` sin interpolación y sin `YYYY13`, variable, unidad NASA, período y nombre.
Se llama a `aggregate_to_annual_series`, `evaluate_completeness`, `analyze_series`
y `compare_two_locations` con sus interfaces existentes.

Se usan los criterios ya presentes en ese motor: media aritmética no ponderada
de al menos 9 meses válidos por año, al menos 3 años y 70% de cobertura anual;
OLS con SciPy, p-valor bilateral, alfa 0,05 e IC del 95% de la pendiente. El
adaptador rechaza cobertura insuficiente antes de presentar estadísticas.
La comparación exige igual variable, período, unidad y conjunto de años válidos.
Es descriptiva: no prueba significancia de la diferencia entre ciudades.

Las respuestas conservan unidades originales, metadatos NASA, calidad mensual,
fecha de obtención, origen, cobertura anual y método. `dataset=MERRA-2` conserva
el contrato histórico; consultar `metadata.header.sources` para las fuentes reales.
La precipitación sigue en `mm/day`, sin transformarse en acumulados. Los extremos
de temperatura son los del producto mensual. El adaptador añade el crítico t
calculado con SciPy para dibujar la banda de confianza con los grados de libertad
correctos; no se mantiene la constante gráfica de 25 años del frontend anterior.

Limitaciones pendientes de revisión metodológica con el responsable del motor:
independencia, estacionalidad, autocorrelación, comparaciones múltiples, sensibilidad
a cobertura y centinelas adicionales del motor (`-99`, `-999`, `-9999`, `<= -900`).
La significancia no establece causalidad. No se implementaron Earth Radar,
Earth Fingerprint ni descubrimientos automáticos. El adaptador territorial real
y el despliegue productivo también siguen pendientes.

## Validación realizada

- Docker Linux/amd64, Python 3.12.16, Flask 3.1.3, Requests 2.34.2 y SciPy 1.18.1;
  `pip check` satisfactorio. NumPy se instala como dependencia de SciPy.
- 104 pruebas descubiertas dentro de Docker: **103 aprobadas y una omitida**
  (la integración NASA de red optativa). Incluyen las **71 originales intactas**,
  7 del motor, 15 del catálogo/misiones y 10 de integración. No se confunde la omisión con una prueba de red.
- Chrome real con Playwright: Inicio, selección de ciudad, Explorador, análisis,
  Resultados, gráfico, CSV, Comparador, cambio de ciudad, error 503 simulado y
  recuperación, misiones, metodología y vista móvil. Cero errores JavaScript.
- Auditoría con la red NASA bloqueada: 25 ciudades, 150 series, 45.000 valores
  mensuales y 150 análisis anuales derivados de esas series. Cero consultas NASA.
  No se aplicó `force` ni se hizo una nueva descarga científica.
- Se verificaron hashes SHA-256 y fechas de obtención antes/después. Los 25 JSON
  originales de `data/cache/power` permanecen intactos. No se eliminaron volúmenes
  ni se intervino en contenedores ajenos a este Compose.

Evidencias locales ignoradas por Git:
`data/cache/reports/integrated-cache-audit.json`,
`data/cache/reports/web/browser.json` y capturas PNG en esa misma carpeta `web`.

Para repetir las comprobaciones, ver [docker.md](../operations/docker.md). Los estilos, fuentes,
mapas y librerías del frontend conservan sus CDN externos: el navegador necesita
Internet para descargarlos; los datos científicos del período cacheado son locales.
