# 🌍 EarthLens

> **Versión vigente:** [abrir EarthLens](https://earthlens-pp-224139449590.us-central1.run.app/).
> El despliegue automático de `main` utiliza el servicio `earthlens-pp`.
> [Restauración y verificaciones](docs/history/restore-main.md).

> **Understand the past. Anticipate the future.**

Environmental and geospatial intelligence platform developed by **Patagonia Prime** for the **NASA Space Apps Challenge 2026 — Be An Earth System Trend Detective!**

[![Open EarthLens](https://img.shields.io/badge/Live%20Demo-Open%20EarthLens-00897B?style=for-the-badge)](https://earthlens-pp-224139449590.us-central1.run.app/)

**[Live application](https://earthleans.earth/)** · [NASA Space Apps project](https://www.spaceappschallenge.org/2026/find-a-team/patagonia-prime/?tab=project) · [Challenge](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/)

---

## The problem

In Comodoro Rivadavia, Patagonia, strong winds, heavy rainfall and changing weather conditions can disrupt everyday life, tourism and outdoor activities. Scientific Earth observation data, meanwhile, are distributed across multiple platforms and can be difficult to interpret without technical expertise.

EarthLens bridges this gap by connecting historical environmental research, operational weather forecasts and personalized event planning in one interactive geospatial workspace.

## Our innovation

EarthLens brings the past, present and future together through an **interactive environmental time machine**. Instead of switching between separate research and planning applications, users can navigate through time on a single map, explore environmental variables and use scientific information to support decisions.

## Main features

- **Earth Time Machine:** explore historical records, select dates and time ranges, compare cities, investigate environmental trends and anomalies, and navigate forward to available weather forecasts.
- **City Profiles and Earth Fingerprint:** explore geographical context, climatology, environmental trends, normalized visual profiles and documented historical events.
- **Earth Radar:** identify candidate environmental trends with estimated slopes and statistical evidence.
- **Scientific Laboratory:** access Explorer, Comparator, Detective, and exploratory Earth Connections and Earth Twins analyses.
- **Smart Calendar:** create a personal account, save private events, define weather preferences and evaluate alternative dates and times.
- **Event Monitoring:** an independent monitoring service can update saved events, preserve forecast history and generate in-app notifications when relevant conditions change.
- **Reports and exports:** generate scientific and event-specific PDF reports, and export supported time series in CSV or JSON.

Historical records, reanalysis, operational forecasts and climatology are distinguished throughout the platform. Missing data are not fabricated, and long-range climatology is not represented as an exact daily forecast.

## Target audience and impact

| Audience | Value |
| --- | --- |
| Scientists and researchers | Investigate environmental changes and compare locations using reproducible statistical methods. |
| Geography and environmental science students | Explore historical environmental changes through accessible maps and charts. |
| Tourism companies and event organizers | Evaluate weather conditions, identify more favorable dates and monitor planned activities. |

Our goal is to create educational, social and economic impact by making scientific data accessible, supporting research and reducing uncertainty in activity planning. These are intended benefits rather than measured outcomes.

## Scientific data

| Coverage | Verified core dataset |
| --- | ---: |
| Argentine cities | 25 |
| Historical period | 2000–2024 |
| Complete monthly time series | 300 |
| Monthly values | 90,000 |

| NASA source | Environmental variables | Core records |
| --- | --- | ---: |
| [NASA POWER](https://power.larc.nasa.gov/) | Temperature, precipitation, atmospheric humidity and wind | 45,000 |
| [NASA GLDAS 2.1](https://ldas.gsfc.nasa.gov/gldas/dataset) | Soil moisture and evapotranspiration | 37,500 |
| [NASA GPM / IMERG V07](https://gpm.nasa.gov/data/imerg) | Satellite-based precipitation estimates | 7,500 |
| **Total** | | **90,000** |

Additional integrations, excluded from the core count:

- [NASA MODIS](https://modis.gsfc.nasa.gov/) — NDVI and EVI vegetation indices; historical retrieval for nine cities, with quality filtering. Partial coverage.
- [NASA SWOT](https://swot.jpl.nasa.gov/) and [Hydrocron](https://podaac.github.io/hydrocron/) — experimental water-height and width retrievals for the Chubut River; quality review pending and analysis disabled for these records.
- [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) — daily historical variables.
- [Copernicus ERA5](https://cds.climate.copernicus.eu/) via [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) — hourly historical reanalysis.
- [Open-Meteo Forecast API](https://open-meteo.com/en/docs) — operational hourly forecasts, up to 16 days depending on availability.
- [GeoRef Argentina](https://www.argentina.gob.ar/georef) — geographical references and city locations.
- [Copernicus DEM GLO-90](https://doi.org/10.5270/ESA-c5d3d65) — elevation context for city centroids.
- [Wikimedia Commons](https://commons.wikimedia.org/) — illustrative city photographs, with source and license attribution where available.

NASA data access and extraction resources include [Earthdata](https://www.earthdata.nasa.gov/), [GES DISC](https://disc.gsfc.nasa.gov/), [AppEEARS](https://appeears.earthdatacloud.nasa.gov/) and [ORNL DAAC](https://daac.ornl.gov/).

## Scientific methodology

EarthLens addresses the challenge's central questions: **what is changing, where, by how much, and with what statistical evidence?**

The statistical engine uses ordinary least squares (OLS) regression, slope estimates, p-values and confidence intervals to investigate historical trends. Sources, units, coverage, quality flags and limitations are preserved.

Earth Radar signals are provisional: its existing family of 150 tests has not been adjusted for multiple comparisons. Exploratory associations and city similarities do not establish causation. The current catalogue represents sampled city locations rather than continuous nationwide measurements.

Event recommendations compare available operational forecasts against user-defined weather preferences. They do not certify safety.

## Technology stack

| Layer | Technology |
| --- | --- |
| Backend and REST API | Python 3.12, Flask, Requests, Gunicorn |
| Frontend | HTML, CSS, JavaScript, Jinja |
| Maps | [Leaflet](https://leafletjs.com/) |
| Charts | [Chart.js](https://www.chartjs.org/) |
| Statistical analysis | [SciPy](https://scipy.org/) |
| Local persistence | [SQLite](https://www.sqlite.org/) |
| PDF reports | [ReportLab](https://www.reportlab.com/) |
| Infrastructure | Docker, Docker Compose, Google Cloud Run |
| Development and version control | Git, GitHub, Visual Studio Code, Google Antigravity |

ChatGPT, OpenAI Codex, Google Gemini and Anthropic Claude were used as development assistants under human supervision, not as substitutes for scientific validation.

## Validation and current limitations

The restoration of the integrated application to the main branch was documented with **254 automated tests executed: 253 passed and one optional live NASA test skipped**. The deployment report records browser checks of the map, timeline, operational forecast, mobile layout and JavaScript behavior.

Software tests demonstrate functionality under the tested conditions, not meteorological forecast accuracy.

EarthLens is a hackathon prototype. Current limitations and future work include:

- TimesFM 3.0 is not installed or validated; operational weather forecasts do not depend on it.
- Automated official SMN alerts and detailed urban vulnerability layers remain pending. The 2017 Comodoro Rivadavia storm provides historical context, not a validated street-level flood prediction.
- Complete MODIS coverage and SWOT quality review remain outstanding.
- Durable production user storage and continuous scheduled monitoring require appropriate infrastructure. A public web deployment alone does not establish those guarantees.
- Commercial use requires appropriate data-service permissions, including Open-Meteo commercial access terms.

## Run locally

Prerequisites: Git, Docker and Docker Compose (Docker Desktop on Windows/macOS).

```bash
git clone https://github.com/Arbitta/Space-Apps.git
cd Space-Apps
docker compose up -d --build --wait --wait-timeout 60
```

Open **http://127.0.0.1:5000/** to access Earth Time Machine.

Historical data availability depends on the scientific cache. Some providers require authorized NASA Earthdata access. Follow the documentation to obtain or recover scientific data. Never commit API tokens, credentials or private user databases.

### Tests and optional local event monitoring

```bash
docker compose exec -T backend python -m unittest discover -s tests
docker compose --profile monitoring up -d monitor
docker compose logs --tail 30 monitor
```

Earth Time Machine: **http://127.0.0.1:5000/time-machine**, incorporado de `main`
y conectado a las cachés POWER por ciudad. Conserva la interfaz del equipo y sus
análisis exploratorios; no utiliza muestras de respaldo, coordenadas libres ni
ajustes artificiales de cuadrantes. El Inicio y las herramientas anteriores se
conservan. Decisiones del merge: [integración de main](docs/history/merge-main.md).

- [Ejecución y pruebas en Docker](docs/operations/docker.md)
- [Estructura del proyecto e inventario de movimientos](docs/architecture/project-structure.md)
- [Contrato de la API](docs/architecture/api.md)
- [Radar y Fingerprint provisionales](docs/architecture/products.md)
- [Diagnóstico e integración entre ramas](docs/architecture/integration.md)
- [Estado y dependencias del backend](docs/project/BACKEND_TASKS.md)

Do not remove persistent volumes or scientific caches when updating the application. Avoid `docker compose down -v`.

## Documentation

- [Project roadmap, scientific inventory and implementation status](EARTHLENS_ROADMAP.md)
- [Time Machine interface and acceptance checks](docs/time-machine-correction.md)
- [Workspace, weather, accounts, events and monitoring](docs/workspace.md)
- [API contract](docs/api.md)
- [Docker setup and tests](docs/docker.md)
- [Radar and Fingerprint methodology](docs/products.md)
- [Backend implementation and dependencies](BACKEND_TASKS.md)
- [Integration history](docs/integration.md)
- [Main restoration and public deployment verification](docs/restore-main.md)
- [Cloud Run deployment](deployment/cloud-run/README.md)

## Scalability and vision

EarthLens started with a problem familiar to our community in Comodoro Rivadavia and expanded to a catalogue of cities across Argentina. Its modular, multi-provider architecture is designed to support new locations, variables and datasets.

Future international expansion would require regional data validation, appropriate geographical coverage, local alert sources and applicable licenses. Global coverage is a goal, not a feature already delivered.

---

**Patagonia Prime · Comodoro Rivadavia, Chubut, Argentina**

Developed for NASA Space Apps Challenge 2026.

*EarthLens — Understand the past. Anticipate the future.*
