# ⏳ Planificación Técnica y Científica — Módulo Earth Time Machine
**Proyecto:** EarthLens — *Be An Earth System Trend Detective!* (NASA Space Apps Challenge 2026)  
**Equipo:** PatagoniaPrime  
**Responsable de Integración (Rol 03):** Resultados, Visualización Temporal y Comparación (`results-charts`)  
**Rama Padre:** `results-charts`  
**Rama Hija (Implementación Completa):** `feature/earth-time-machine`  
**Fecha:** 14 de noviembre de 2026  

---

## 1. Propósito y Alineación con el Desafío

Según el documento de diseño del equipo (**Problemática**) y el **Plan de Desarrollo de PatagoniaPrime (`docs/project/PatagioniaPrime_Plan_de_desarrollo.pdf`)**, **Earth Time Machine** es la herramienta de exploración espacio-temporal de EarthLens diseñada para cumplir tres objetivos centrales:

1. **Recorrido temporal interactivo (2000–2024 y serie extendida 1981–2024):** Permitir al usuario desplazarse año por año (mediante un control deslizante *slide-zoom* y reproducción automática *Play/Pause*) observando cómo evoluciona una variable climática de **NASA POWER / MERRA-2** sobre una zona geográfica específica y sobre las 25 ciudades del catálogo argentino.
2. **Visualización cromática en mapa (Zona MERRA-2 y Red Regional):** Representar con escalas de color científicas tanto el valor absoluto anual como la anomalía climática ($\Delta_t = y_t - \bar{y}$ y $z\text{-score}$) sobre la grilla satelital MERRA-2 ($0.5^\circ \times 0.625^\circ$) de la zona seleccionada y las 5 regiones argentinas.
3. **Comparación de períodos (Época A vs. Época B) y Detección de Anomalías:** Contrastar estadísticamente dos sub-períodos históricos (por ejemplo, `2000–2011` vs. `2012–2024`) y detectar automáticamente años con anomalías moderadas ($|z| \ge 1.5$) o severas ($|z| \ge 2.0$), así como los récords históricos del período.

---

## 2. Diagnóstico de Ramas y Estrategia de No-Interferencia (Git)

Antes de diseñar la arquitectura, se inspeccionaron en modo lectura todas las ramas remotas del repositorio para garantizar **cero conflictos** con el trabajo de los demás integrantes:

| Rama | Rol / Integrante | Estado inspeccionado | Estrategia de convivencia |
| :--- | :--- | :--- | :--- |
| `results-charts` *(Rama actual / Padre)* | **Rol 03 (Resultados y Comparador)** + Motor Estadístico (`trend_analysis.py`) | Contiene `results.html`, `compare.html`, `charts.js`, `results.js`, `compare.js`, `results.css`, `services/science/trend_analysis.py` y la suite de 31 pruebas de auditoría (`tests/`). | Se añaden únicamente **funciones puras aditivas** en `services/science/trend_analysis.py` y `static/js/shared/charts.js`, más los botones de enlace hacia `/time-machine` en `results.html` y `compare.html`. No se altera ninguna firma existente ni las 31 pruebas actuales. |
| `feature/earth-time-machine` *(Rama hija nueva)* | **Rol 03 — Módulo Earth Time Machine completo** | Creada a partir de `results-charts`. | Contiene la vista completa `templates/pages/time_machine.html`, lógica `static/js/time-machine/time_machine.js`, estilos `static/css/pages/time_machine.css`, servicio `services/workspace/time_machine.py`, catálogo `data/cities_argentina.json`, endpoints `/api/time-machine` y pruebas `tests/workspace/test_time_machine.py`. |
| `origin/feature/backend-api` | **Rol 04 (Backend, Caché, Radar y Fingerprint)** | Implementa el catálogo de 25 ciudades argentinas (`data/cities.json`), `Earth Radar` (`/radar`) y `Earth Fingerprint` (`/fingerprint`), reutilizando `services/science/trend_analysis.py` de `results-charts`. | **No se modifica esa rama.** En `feature/earth-time-machine` se utilizan los mismos IDs, nombres, provincias, regiones y coordenadas GeoRef de las 25 ciudades argentinas y los datos verificados de Comodoro Rivadavia, Mendoza, Posadas, San Juan y San Luis para asegurar compatibilidad total al integrar. |
| `origin/datasets-missions` y `origin/main` | **Rol 01, 02 y 05 (Inicio, Explorador y Modo Detective)** | Contienen `index.html`, `explorer.html` y `pages/missions.html`. | **No se modifican archivos de los Roles 01, 02 ni 05** en `results-charts`. En la rama hija `feature/earth-time-machine` el módulo se integra mediante rutas propias (`/time-machine` y `/api/time-machine`). |

---

## 3. Solución al Problema de Sobrecarga por Rango de Años

En el documento **Problemática** se planteó la siguiente inquietud técnica:
> *"El tema del rango de los años: si mientras más años más sobrecarga a la página le damos, ver qué podría ser mejor."*

### Arquitectura adoptada para evitar sobrecarga:
1. **Descarga única por serie y reproducción 100% en memoria del cliente (Client-Side Scrubbing):**
   * En lugar de disparar una petición HTTP a la API cada vez que el usuario mueve el deslizador de año (`2000 → 2001 → 2002...`), el endpoint `POST /api/time-machine` devuelve en **un único paquete JSON compacto (~15–35 KB)** la matriz precalculada de todos los años del período solicitado (`2000–2024` por defecto, o hasta `1981–2024`).
   * De este modo, al mover el slider o reproducir la animación (*Play*), la actualización del mapa Leaflet, la grilla zonal de colores y los 3 gráficos de `Chart.js` ocurre en **menos de 5 milisegundos en el navegador**, con **0 peticiones adicionales al servidor**.
2. **Sub-zoom temporal instantáneo (Slide-Zoom):**
   * Cuando el usuario ajusta los selectores de **Época A / Época B** o hace zoom en un sub-intervalo dentro de los años ya cargados, el cliente recalcula instantáneamente las métricas de sub-período y actualiza el mapa sin recargar la página.
3. **Caché en memoria en el backend:**
   * Las series anuales consultadas a NASA POWER se mantienen cacheadas en memoria y respaldadas con las muestras verificadas del proyecto, evitando bloqueos o límites de tasa (*rate-limiting*).

---

## 4. Metodología Científica y Estadística de Earth Time Machine

Earth Time Machine extiende el motor estadístico `services/science/trend_analysis.py` con tres bloques matemáticos rigurosos:

### 4.1. Anomalías Anuales, Estandarización ($z\text{-score}$) y Percentiles
Sea $Y = \{y_{t_1}, y_{t_2}, \dots, y_{t_n}\}$ la serie anual limpia de una variable climática en el período $[t_{\text{inicio}}, t_{\text{fin}}]$, con media climatológica del período $\bar{y}$ y desviación estándar muestral $s_y$:

$$\bar{y} = \frac{1}{n}\sum_{i=1}^{n} y_{t_i}, \qquad s_y = \sqrt{\frac{1}{n-1}\sum_{i=1}^{n} (y_{t_i} - \bar{y})^2}$$

Para cada año $t_i$ se calculan:
* **Valor ajustado por tendencia lineal OLS:** $\hat{y}_{t_i} = m \cdot t_i + b$
* **Anomalía absoluta respecto al promedio del período:**
  $$\Delta_{t_i} = y_{t_i} - \bar{y}$$
* **Anomalía estandarizada ($z\text{-score}$ adimensional):**
  $$z_{t_i} = \frac{y_{t_i} - \bar{y}}{s_y}$$
* **Clasificación objetiva de anomalías:**
  * $|z_{t_i}| < 1.0$: Comportamiento dentro del rango normal histórico.
  * $1.0 \le |z_{t_i}| < 1.5$: Desviación moderada-leve.
  * $1.5 \le |z_{t_i}| < 2.0$: **Anomalía moderada** (evento destacable).
  * $|z_{t_i}| \ge 2.0$: **Anomalía severa / extrema** (evento crítico superior al ~95% de la distribución).

### 4.2. Comparación Estadística entre Dos Períodos (Época A vs. Época B)
Para evaluar cómo cambió el régimen climático de una misma ubicación a lo largo del tiempo, la serie se particiona en dos sub-períodos disjuntos definidos por un año de corte $t_{\text{corte}}$ (por defecto, primera mitad `2000–2011` vs. segunda mitad `2012–2024`):

* **Cambio neto de media entre épocas:**
  $$\Delta_{\text{épocas}} = \bar{y}_B - \bar{y}_A$$
* **Variación relativa porcentual:**
  $$\Delta_{\%} = \left(\frac{\bar{y}_B - \bar{y}_A}{|\bar{y}_A|}\right) \times 100$$
* **Prueba $t$ de Welch para diferencia de medias (varianzas desiguales):**
  $$t_{\text{Welch}} = \frac{\bar{y}_B - \bar{y}_A}{\sqrt{\frac{s_A^2}{n_A} + \frac{s_B^2}{n_B}}}$$
  con grados de libertad de Welch-Satterthwaite $\nu$ y $p\text{-valor}$ bilateral. Si $p < 0.05$, existe evidencia estadística de un desplazamiento del promedio climático entre la Época A y la Época B.

### 4.3. Modelado Espacial Slide-Zoom (Grilla MERRA-2 $3 \times 3$ y Red de 25 Ciudades)
Cada observación de **NASA POWER / MERRA-2** representa una celda satelital de $0.5^\circ \text{ lat} \times 0.625^\circ \text{ lon}$ (~50 km $\times$ 55 km). Earth Time Machine ofrece dos modos espaciales en el mapa:
1. **Modo Zona Específica (Slide-Zoom Grilla $3 \times 3$):** Dibuja la celda central seleccionada rodeada por su vecindario inmediato de $3 \times 3$ celdas MERRA-2 ($1.5^\circ \times 1.875^\circ$) y un halo de interpolación zonal que cambia de color año a año según la escala cromática de la variable.
2. **Modo Red Nacional Argentina (25 Ciudades en 5 Regiones):** Muestra simultáneamente las 25 ciudades argentinas (*Patagonia, Cuyo, Centro y región pampeana, NOA y NEA*), coloreando cada marcador según su valor o anomalía en el año activo $t$.

---

## 5. Escalas Cromáticas Científicas por Variable

Para que el usuario interprete intuitivamente los colores en el mapa y en las barras de anomalías (*Warming/Climate Stripes*), cada variable utiliza una paleta semántica específica:

| Variable | Código | Paleta de Valor / Anomalía Negativa ($z < 0$) | Centro ($z \approx 0$) | Paleta de Valor / Anomalía Positiva ($z > 0$) |
| :--- | :---: | :--- | :--- | :--- |
| **Temperatura media / máx / mín** | `T2M`, `T2M_MAX`, `T2M_MIN` | Azul profundo → Celeste (`#1d4ed8` → `#93c5fd`) | Blanco cálido (`#f8fafc`) | Ámbar → Rojo intenso (`#f59e0b` → `#dc2626`) |
| **Precipitaciones corregidas** | `PRECTOTCORR` | Ámbar seco / Ocre (`#b45309` → `#fcd34d`) | Gris neutro (`#f8fafc`) | Turquesa → Azul hídrico (`#0ea5e9` → `#0369a1`) |
| **Humedad relativa a 2m** | `RH2M` | Arena / Seco (`#d97706` → `#fde68a`) | Blanco neutro (`#f8fafc`) | Esmeralda → Verde húmedo (`#10b981` → `#047857`) |
| **Velocidad del viento a 2m** | `WS2M` | Celeste calmo (`#38bdf8` → `#bae6fd`) | Blanco neutro (`#f8fafc`) | Índigo → Violeta intenso (`#6366f1` → `#7e22ce`) |

---

## 6. Contrato de la API para Earth Time Machine

### 6.1. `POST /api/time-machine` (y `GET /api/time-machine`)

**Solicitud (`POST /api/time-machine`):**
```json
{
  "latitude": -45.86,
  "longitude": -67.50,
  "location_name": "Comodoro Rivadavia, Chubut",
  "variable": "T2M",
  "start_year": 2000,
  "end_year": 2024,
  "split_year": 2012,
  "include_regional": true
}
```

**Respuesta (`200 OK`):**
```json
{
  "is_mock": false,
  "variable": "T2M",
  "variable_name": "Temperatura media a 2m",
  "unit": "deg C",
  "display_unit": "°C",
  "source": "NASA POWER / MERRA-2",
  "location": {
    "name": "Comodoro Rivadavia, Chubut",
    "latitude": -45.86,
    "longitude": -67.50,
    "region": "Patagonia"
  },
  "period": {
    "start_year": 2000,
    "end_year": 2024,
    "split_year": 2012
  },
  "statistics": {
    "slope": 0.0365,
    "change_per_decade": 0.365,
    "total_change": 0.876,
    "p_value": 0.0001,
    "significant": true,
    "direction": "increasing",
    "confidence_interval_95": [0.025, 0.048],
    "mean": 13.06,
    "std_dev": 0.34
  },
  "timeline": [
    {
      "year": 2000,
      "value": 12.42,
      "trend_value": 12.62,
      "ci_low": 12.48,
      "ci_high": 12.76,
      "anomaly": -0.64,
      "z_score": -1.88,
      "percentile": 4.0,
      "anomaly_level": "moderate_low",
      "is_anomaly": true,
      "color": "#3b82f6"
    }
  ],
  "anomalies": {
    "threshold_z": 1.5,
    "count": 4,
    "max_record": {"year": 2024, "value": 13.68, "anomaly": 0.62, "z_score": 1.82},
    "min_record": {"year": 2000, "value": 12.42, "anomaly": -0.64, "z_score": -1.88},
    "events": []
  },
  "period_comparison": {
    "period_a": {"label": "2000–2011", "start_year": 2000, "end_year": 2011, "mean": 12.84, "std_dev": 0.22, "slope_decade": 0.31},
    "period_b": {"label": "2012–2024", "start_year": 2012, "end_year": 2024, "mean": 13.26, "std_dev": 0.29, "slope_decade": 0.39},
    "delta_mean": 0.42,
    "delta_percent": 3.27,
    "p_value": 0.0006,
    "significant_shift": true,
    "summary": "El período 2012–2024 presenta un incremento promedio de +0.42 °C respecto a 2000–2011 (p = 0.0006 < 0.05)."
  },
  "spatial_zone": {
    "cell_resolution_deg": {"lat": 0.5, "lon": 0.625},
    "cells": []
  },
  "regional_cities": [],
  "conclusion": "..."
}
```

---

## 7. Estructura de Archivos por Rama

### 7.1. Cambios mínimos en `results-charts` (Rama Padre)
* `services/science/trend_analysis.py`: Adición de `compute_annual_anomalies()`, `compare_time_periods()` y `analyze_time_machine()` sin tocar funciones previas.
* `static/js/shared/charts.js`: Adición de utilidades `computeAnomalySeries()`, `computePeriodComparison()`, `getVariableColor()`, `renderAnomalyBarChart()` y `renderPeriodComparisonChart()`.
* `templates/pages/results.html`, `static/js/exploration/results.js`, `templates/pages/compare.html`, `static/js/exploration/compare.js`: Botón de acceso rápido `⏳ Earth Time Machine` sincronizado con las coordenadas, variable y años activos.
* `docs/project/PLANIFICACION_EARTH_TIME_MACHINE.md` y `docs/project/PLANIFICACION_EARTH_TIME_MACHINE.pdf`: Documentación formal de planificación.

### 7.2. Implementación completa en `feature/earth-time-machine` (Rama Hija)
* `data/cities_argentina.json`: Catálogo oficial de las 25 ciudades argentinas organizadas en 5 regiones (*Patagonia, Centro y región pampeana, Cuyo, NOA, NEA*) con coordenadas GeoRef compatibles con `feature/backend-api`.
* `services/workspace/time_machine.py`: Motor completo de la Máquina del Tiempo (serie temporal enriquecida, grilla espacial $3 \times 3$ MERRA-2, instantáneas de las 25 ciudades, detección de anomalías y prueba de cambio de época).
* `routes/api_routes.py` y `app.py`: Rutas `/time-machine`, `/api/time-machine` y `/api/cities`.
* `templates/pages/time_machine.html`: Interfaz interactiva con mapa Leaflet Slide-Zoom, barra de reproducción temporal `2000–2024`, selector de épocas, 3 gráficos sincronizados y detector de anomalías.
* `static/css/pages/time_machine.css` y `static/js/time-machine/time_machine.js`: Estilos y controlador reactivo sin sobrecarga de red.
* `tests/workspace/test_time_machine.py`: Suite de pruebas unitarias, de integración HTTP y de concurrencia para validar el nuevo módulo junto con los 31 tests existentes.

