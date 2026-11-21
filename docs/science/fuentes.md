# Fuentes científicas y Modo detective (Persona 5)

| Archivo | Qué contiene |
|---|---|
| `data/variables.json` | Variables del MVP (campos del explorador + metadatos de Persona 5), fenómenos y catálogo de fuentes |
| `data/missions.json` | Los 3 casos guiados y las hipótesis posibles |
| `tests/data/samples/power_comodoro_2000_2024.json` | Respuesta **real** de NASA POWER (mensual, 6 variables) para Comodoro Rivadavia |
| `services/science/datasets.py` | Catálogo, recomendador, misiones, veredicto y agregación anual de referencia |
| `routes/missions_routes.py` | Endpoints del recomendador y de fuentes (Flask y servidor de respaldo) |
| `templates/pages/missions.html`, `static/js/exploration/missions.js` | Página del Modo detective (HTML independiente, sin Jinja) |
| `tests/science/test_datasets.py` | Pruebas (`python -m pytest tests`) |

## Endpoints

| Ruta | Función | Dónde |
|---|---|---|
| `GET /missions` | Página del Modo detective | `app.py` |
| `GET /api/missions` | Resumen de los casos | `routes/api_routes.py` → `datasets.get_missions_list()` |
| `GET /api/missions/<id>` | Detalle del caso (acepta id o número, ej. `01`), con `explorer_url` e hipótesis | `routes/api_routes.py` → `datasets.get_mission_by_id()` |
| `GET /api/variables` | Catálogo de variables | `routes/api_routes.py` → `datasets.get_variables_catalog()` |
| `GET /api/phenomena` | Fenómenos para el recomendador | `routes/missions_routes.py` |
| `GET /api/variables/recommend?phenomenon=sequia` | Variables sugeridas | `routes/missions_routes.py` |
| `GET /api/sources` | Catálogo de fuentes de datos | `routes/missions_routes.py` |

En `data/variables.json`, los campos que usa el explorador (`shortName`, `displayUnit`, `unit`, `description`…)
tienen prioridad; Persona 5 solo agrega campos nuevos (`annual_aggregation`, `valid_range`, `notes`, `phenomena`…).

## Cómo funciona una misión

1. En `/missions` el usuario elige un caso y una hipótesis (`increasing`, `decreasing`, `no_clear_trend`).
2. `missions.js` guarda la misión activa en `sessionStorage` (`earthlens.activeMission`) y redirige:
   - Modo `analyze` → `/explorer?lat=..&lon=..&label=..&variable=..&start_year=..&end_year=..&mission=..`
   - Modo `compare` → `/compare?latA=..&lonA=..&nameA=..&latB=..&lonB=..&nameB=..&variable=..&start_year=..&end_year=..&mission=..`
3. En `/results` y `/compare`, `EarthLensMissions.renderVerdict(...)` muestra el veredicto en `#mission-verdict`
   **solo si** la variable y la ubicación coinciden con la misión activa y los datos no son de prueba (`is_mock`).
   En el comparador la hipótesis se evalúa sobre la Ubicación A.

| Resultado | Hipótesis = dirección | Hipótesis opuesta | Hipótesis "sin cambio claro" |
|---|---|---|---|
| Significativo (p < 0,05) y con pendiente | Apoyada | Contradicha | Contradicha |
| No significativo | Evidencia insuficiente | Evidencia insuficiente | Apoyada (con aviso: no prueba ausencia de cambio) |

## NASA POWER: lo que verificamos (14/11/2026)

- Endpoint mensual: claves `AAAAMM`; **el mes `13` es el valor anual** que calcula POWER. Faltante: `-999`.
- Unidades: `C`, `mm/day`, `%`, `m/s`. Resolución: 0,5° × 0,625° (~50 km). Cobertura: desde 1981.

### Avisos para backend (P4) y estadística (P6)

1. **Datos reales solo con `EARTHLENS_LIVE_NASA=1`.** Sin esa variable, `services/power.py` no consulta NASA:
   devuelve `tests/data/samples/comodoro_rivadavia_2000_2024.json` (T2M 2000 = 12,35 °C, cuando el valor real de POWER
   es 10,68 °C; ver `power_comodoro_2000_2024.json`) y para otras coordenadas genera valores sintéticos,
   etiquetados igual como "NASA POWER / MERRA-2". Los veredictos de las misiones solo son válidos con datos reales.
   Con `EARTHLENS_LIVE_NASA=1`, Comodoro T2M 2000–2024 da +0,25 °C/década, p ≈ 0,035.
2. **`T2M_MAX` / `T2M_MIN` mensuales y anuales son extremos absolutos**, no promedios (T2M_MAX 2012 = 34,1 °C).
   Para "promedio de máximas" hay que usar el endpoint diario.
3. **Precipitación**: POWER da mm/día y el mes 13 también es un promedio en mm/día. Para **mm/año** hay que sumar
   `valor mensual × días del mes` (`datasets.annual_series_from_power_monthly()` lo hace y está probado).

## Catálogo de fuentes

| Fuente | Uso | Acceso | Resolución / cobertura | Estado |
|---|---|---|---|---|
| NASA POWER (MERRA-2) | Base del MVP | API pública, JSON | ~50 km · 1981–hoy | **Probado** |
| Giovanni | Contraste de series por área | Web, cuenta Earthdata | según producto | Pendiente (descarga manual) |
| GPM IMERG | Precipitación satelital | GES DISC, Earthdata | 0,1° · jun 2000–hoy | Opcional, no probado |
| GLDAS-2.1 | Humedad del suelo | GES DISC / Data Rods, Earthdata | 0,25° · 2000–hoy | Opcional, no probado |
| AppEEARS / MODIS | NDVI, nieve, temp. superficial | API con token Earthdata | 250 m–1 km · 2000–hoy | Si hay tiempo |

## Misiones

| Id | Pregunta | Variable | Lugar | Modo |
|---|---|---|---|---|
| `patagonia-cambiante` | ¿Aumenta la temperatura? | T2M (+T2M_MIN, T2M_MAX) | Comodoro Rivadavia | analyze |
| `en-busca-del-agua` | ¿Disminuyen las lluvias? | PRECTOTCORR (+T2M, RH2M) | Mendoza | analyze |
| `misterio-del-viento` | ¿Cambia el viento? | WS2M | Comodoro vs. Buenos Aires | compare |

Los presets del explorador (`explorer.js`, `PRESET_LOCATIONS`) tienen su propia versión del caso 03
(Río Gallegos, sin comparación). Conviene unificarlos con `data/missions.json`.
