> **Versi?n vigente:** [abrir EarthLens](https://earthlens-pp-224139449590.us-central1.run.app/).
> El despliegue autom?tico de `main` utiliza el servicio `earthlens-pp`.
> [Restauraci?n y verificaciones](docs/history/restore-main.md).

# EarthLens — Patagonia Prime

NASA Space Apps Challenge 2026 · Earth System Trend Detective.
Explorador de datos ambientales históricos de Argentina, con API NASA POWER,
caché local y motor estadístico del equipo.

Desde la raíz del repositorio, con Docker Desktop iniciado:

```powershell
docker compose up -d --build --wait --wait-timeout 60
```

Abrir **http://127.0.0.1:5000/**.

Earth Radar: **http://127.0.0.1:5000/radar**. Earth Fingerprint:
**http://127.0.0.1:5000/fingerprint**. Usan los datos reales de 2000–2024;
las señales son provisionales y no tienen ajuste por comparaciones múltiples.

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

La caché existente de `data/cache` se conserva mediante un bind mount. No hace
falta Node ni un segundo Compose. Los recursos visuales externos requieren Internet.
