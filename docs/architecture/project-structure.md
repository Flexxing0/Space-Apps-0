# Estructura del proyecto

`app.py` sigue siendo el punto de entrada WSGI y la fábrica Flask. Los
Blueprints de `api/` y `web/` enlazan HTTP con los servicios. `api/accounts.py`
mantiene las rutas de sesión y las protecciones de autenticación y CSRF.
Se registra en el Blueprint existente para conservar los endpoints Flask.
Los eventos y las notificaciones se atienden desde `api/events.py` con
persistencia SQLite compartida.

```text
.
├── app.py
├── api/
├── web/
├── services/
│   ├── events/
│   ├── geography/
│   ├── prediction/
│   ├── providers/
│   ├── science/
│   ├── storage/
│   ├── weather/
│   └── workspace/
├── templates/
│   ├── components/
│   ├── layouts/
│   └── pages/
├── static/
│   ├── css/  (components, global, pages)
│   └── js/   (exploration, products, shared, time-machine)
├── scripts/  (audit, data, maintenance)
├── tests/    (api_contracts, browser, geography, operations, prediction,
│              providers, science, workspace, data, statistics_fixtures)
├── docs/     (architecture, examples, history, operations, project, reports, science)
├── data/     (catálogos, caché y almacenamiento local)
└── deployment/cloud-run/
```

Los adaptadores NASA y sus auxiliares de adquisición quedan en
`services/providers/`. La meteorología operativa está en `services/weather/`
y los modelos predictivos y sus capacidades en `services/prediction/`.
Los módulos predictivos heredados conservan su comportamiento y TimesFM
sigue deshabilitado. El motor en `services/science/trend_analysis.py`
conserva su contenido y su hash SHA-256. Las rutas HTTP, los catálogos
y las ubicaciones de caché y SQLite conservan su contrato.

## Inventario de movimientos

Cada fila enumera los archivos movidos entre las carpetas indicadas.
Los paquetes Python nuevos tienen su propio `__init__.py`.

| Origen | Destino | Archivos |
| --- | --- | --- |
| `./` | `docs/operations/` | `GUIA_DESPLIEGUE_Y_CREDITOS_EARTHLENS.md`, `GUIA_DESPLIEGUE_Y_CREDITOS_EARTHLENS.pdf` |
| `./` | `docs/project/` | `BACKEND_TASKS.md`, `EARTHLENS_ROADMAP.md`, `PLANIFICACION_EARTH_TIME_MACHINE.docx`, `PLANIFICACION_EARTH_TIME_MACHINE.md`, `PLANIFICACION_EARTH_TIME_MACHINE.pdf`, `PatagioniaPrime_Plan_de_desarrollo.pdf` |
| `./` | `docs/reports/` | `INFORME_PROYECTO.docx`, `INFORME_PROYECTO.md`, `INFORME_PROYECTO.pdf`, `INFORME_PRUEBAS_Y_ERRORES.docx`, `INFORME_PRUEBAS_Y_ERRORES.md`, `INFORME_PRUEBAS_Y_ERRORES.pdf` |
| `docs/` | `docs/architecture/` | `api.md`, `integration.md`, `products.md`, `time-machine-correction.md`, `time-machine-integration.md`, `workspace.md` |
| `docs/` | `docs/history/` | `merge-forecast.md`, `merge-main.md`, `restore-main.md` |
| `docs/` | `docs/operations/` | `docker.md`, `runtime-local.md` |
| `docs/` | `docs/science/` | `bulk-power.md`, `fuentes.md`, `nasa-power.md`, `scientific-sources.md` |
| `scripts/` | `scripts/audit/` | `audit_science.py`, `audit_timesfm.py`, `backtest_weather.py`, `check_cached_integration.py`, `check_product_pages.py`, `check_scientific_cache.py`, `check_scientific_pages.py`, `check_time_machine.py`, `check_time_machine_acceptance.py`, `check_web.py`, `check_workspace.py` |
| `scripts/` | `scripts/data/` | `build_city_catalog.py`, `fetch_city_context.py`, `fetch_impact.py`, `fetch_power.py`, `fetch_science.py`, `order_modis.py`, `probe_giovanni.py`, `probe_weather.py` |
| `scripts/` | `scripts/maintenance/` | `generate_radar.py`, `initialize_data.py`, `monitor_events.py`, `prepare_cloud_release.py` |
| `services/` | `services/events/` | `events.py`, `monitoring.py`, `planning.py` |
| `services/` | `services/geography/` | `cities.py`, `geography.py` |
| `services/` | `services/prediction/` | `forecast.py`, `forecast_service.py`, `prediction.py` |
| `services/` | `services/providers/` | `bulk.py`, `cache.py`, `normalizer.py` |
| `services/` | `services/science/` | `analysis_results.py`, `analysis_service.py`, `datasets.py`, `fingerprint.py`, `guided_missions.py`, `hydrology.py`, `impact.py`, `mission_service.py`, `radar.py`, `scientific.py`, `scientific_compare.py`, `trend_analysis.py` |
| `services/` | `services/storage/` | `persistence.py` |
| `services/` | `services/weather/` | `weather.py` |
| `services/` | `services/workspace/` | `reports.py`, `time_machine.py`, `time_machine_service.py`, `time_navigation.py`, `workspace.py` |
| `static/css/` | `static/css/components/` | `scientific.css`, `time_machine_shell.css` |
| `static/css/` | `static/css/global/` | `styles.css` |
| `static/css/` | `static/css/pages/` | `explorer.css`, `index.css`, `products.css`, `results.css`, `time_machine.css`, `workspace.css` |
| `static/js/` | `static/js/exploration/` | `compare.js`, `explorer.js`, `index.js`, `missions.js`, `results.js` |
| `static/js/` | `static/js/products/` | `fingerprint.js`, `products.js`, `radar.js`, `scientific.js` |
| `static/js/` | `static/js/shared/` | `api.js`, `charts.js`, `map.js` |
| `static/js/` | `static/js/time-machine/` | `time_axis.js`, `time_machine.js`, `time_machine_charts.js`, `tm_forecast.js`, `workspace.js` |
| `templates/` | `templates/components/` | `_navigation.html`, `_provisional_notice.html`, `_scientific_panel.html`, `_workspace_header.html`, `_workspace_timeline.html` |
| `templates/` | `templates/layouts/` | `base.html` |
| `templates/` | `templates/pages/` | `about.html`, `compare.html`, `explorer.html`, `fingerprint.html`, `index.html`, `laboratory.html`, `missions.html`, `radar.html`, `results.html`, `scientific.html`, `time_machine.html`, `workspace.html` |
| `tests/` | `tests/api_contracts/` | `test_api.py` |
| `tests/` | `tests/browser/` | `test_product_pages.py`, `test_web_integration.py` |
| `tests/` | `tests/geography/` | `test_cities.py`, `test_city_catalog_builder.py`, `test_geography.py` |
| `tests/` | `tests/operations/` | `test_cloud_release.py`, `test_initialize_data.py` |
| `tests/` | `tests/prediction/` | `test_forecast.py` |
| `tests/` | `tests/providers/` | `test_bulk.py`, `test_cache.py`, `test_giovanni_probe.py`, `test_giovanni_provider.py`, `test_gldas_points.py`, `test_gldas_provider.py`, `test_modis_orders.py`, `test_power_provider.py`, `test_power_provider_live.py` |
| `tests/` | `tests/science/` | `test_datasets.py`, `test_hydrology.py`, `test_products.py`, `test_scientific.py`, `test_scientific_compare.py`, `test_statistics.py` |
| `tests/` | `tests/workspace/` | `test_time_machine.py`, `test_time_navigation.py`, `test_workspace_v2.py` |
| `test_nasa.py` | `scripts/audit/probe_nasa_power.py` | Ruta individual |
| `docker-entrypoint.sh` | `docs/history/legacy/docker-entrypoint.sh` | Ruta individual |
| `routes/__init__.py` | `docs/history/legacy/routes/__init__.py` | Ruta individual |
| `e config --services` | `docs/history/initial-git-status.txt` | Ruta individual |

## Compatibilidad y archivos históricos

- El Dockerfile raíz, la receta empaquetada para Cloud Run y los montajes de
  desarrollo siguen copiando árboles completos. Los servicios de monitoreo de
  ambos Compose ejecutan `python -m scripts.maintenance.monitor_events`.
  El empaquetador y el verificador de Cloud Run apuntan a la nueva plantilla
  y al recurso JavaScript de Time Machine. La interfaz WSGI sigue en `app:app`.
- Jinja resuelve los layouts y componentes desde sus carpetas y genera las
  URLs de recursos con `url_for('static', filename=...)`. El verificador
  histórico del frontend abre `/time-machine/legacy`.
- El antiguo entrypoint y el paquete `routes/` conservan una copia en
  `docs/history/legacy/`. Ningún Dockerfile ni Compose activo los usa y
  ningún módulo activo importa el paquete. La captura de estado de Git se
  conserva en `docs/history/initial-git-status.txt`.
- La plantilla de Inicio anterior y sus recursos quedan preservados en
  `templates/pages/index.html`, `static/css/pages/index.css` y
  `static/js/exploration/index.js`. La ruta `/index.html` sirve Time Machine.
- Los PDF y DOCX acompañan a sus informes editables. Los archivos de
  referencia estadística y las muestras de prueba se conservan. Los dos JSON
  de Comodoro bajo `tests/data/samples/` tienen copias byte a byte en
  `tests/statistics_fixtures/main_legacy/`, que conserva el material histórico.

## Ejecutores desde la raíz

```powershell
python -m unittest discover -s tests -v
python -m scripts.data.fetch_power --city comodoro-rivadavia --dry-run
python -m scripts.audit.audit_timesfm
python -m scripts.audit.check_time_machine_acceptance
flask --app app:create_app run
```

Los verificadores de navegador usan Playwright y Chrome. La sonda manual
`python -m scripts.audit.probe_nasa_power` consulta al proveedor. Consultá las
[condiciones de aceptación de Time Machine](time-machine-correction.md)
y la [guía de ejecución con Docker](../operations/docker.md).
