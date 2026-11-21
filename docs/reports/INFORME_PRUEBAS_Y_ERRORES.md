# 🧪 Informe de Auditoría de Pruebas y Hallazgos — EarthLens
**Rama evaluada:** `results-charts` (unificada con `main`)  
**Suite automatizada ejecutada:** [test_full_audit.py](../../tests/statistics_fixtures/main_legacy/full_audit_reference.py), [test_statistics.py](../../tests/science/test_statistics.py) y [test_api.py](../../tests/api_contracts/test_api.py) (`30 tests ejecutados`)  
**Metodologías aplicadas:** Partición de Equivalencia, Caja Negra, Caja Blanca, Hilos (Concurrencia) y Orientación a Objetos.

---

## 1. Resumen de Pruebas por Página

| Página / Vista | Archivo Plantilla | Scripts Asociados | Estado HTTP / Render | Errores / Hallazgos Detectados |
| :--- | :--- | :--- | :---: | :--- |
| **01. Inicio** (`/`, `/index.html`) | `templates/pages/index.html` | `static/js/exploration/index.js` | `200 OK` | **H-05:** En modo `file://` o sin red, geocodificación inversa externa (`nominatim.openstreetmap.org`) falla sin caché local. |
| **02. Explorador** (`/explorer`, `/explorer.html`) | `templates/pages/explorer.html` | `static/js/shared/map.js`, `static/js/exploration/explorer.js` | `200 OK` | **H-02:** Desajuste en código de dirección (`no_clear_trend` en JS vs `stable` en Backend Python). |
| **03. Resultados** (`/results`, `/results.html`) | `templates/pages/results.html` | `static/js/shared/charts.js`, `static/js/exploration/results.js` | `200 OK` | **H-01:** `quickEndYear` permite hasta `2025`, lo que con `start_year=2023` en Comodoro Rivadavia lanza `ValueError` (HTTP 500). **H-06:** Cambiar ubicación en el `<select>` superior no actualiza la gráfica hasta pulsar el botón ni se sincroniza con la URL inicial. |
| **04. Comparador** (`/compare`, `/compare.html`) | `templates/pages/compare.html` | `static/js/shared/charts.js`, `static/js/exploration/compare.js` | `200 OK` | **H-01:** `cmpEndYear` permite `max="2025"`, desalineado del límite `2024` del dataset de muestra. |
| **05. Modo Detective** (`/missions`, `/missions.html`) | *(Faltante: `templates/pages/missions.html`)* | *(Faltante: `static/js/exploration/missions.js`)* | `200 OK` (Fallback) | **H-03:** El enlace del navbar existe en todas las páginas, pero al no existir `pages/missions.html` devuelve `explorer.html` sin activar el catálogo de `/api/missions`. |
| **06. Nosotros y Metodología** (`/about`, `/about.html`) | *(Faltante: `templates/pages/about.html`)* | — | `200 OK` (Fallback) | **H-03:** Al no existir `pages/about.html`, la ruta `/about` devuelve `index.html` (Inicio) en lugar de la sección de metodología e integrantes. |
| **07. Plantilla Base** (`/templates/base.html`) | `templates/layouts/base.html` | — | `200 OK` (Crudo) | **H-04:** Contiene etiquetas Jinja2 (`{{ url_for(...) }}` y `{% block %}`) que no son heredadas por las demás páginas y se sirven sin procesar en el servidor estático/fallback. |

---

## 2. Resultados por Metodología de Prueba

### 2.1. Pruebas de Partición de Equivalencia y Valores Límite
Se particionaron los dominios de entrada de `POST /api/analyze` y de los formularios de las 4 páginas:

* **Latitud (`latitude`):**
  * *Partición inválida inferior ($< -90^\circ$):* `-150.0`, `-90.0001` $\rightarrow$ Rechazado correctamente (`400 Bad Request`).
  * *Partición válida ($[-90^\circ, 90^\circ]$):* `-90.0`, `-45.86`, `0.0`, `90.0` $\rightarrow$ Aceptado (`200 OK`).
  * *Partición inválida superior ($> 90^\circ$) y tipos no numéricos:* `90.0001`, `180.0`, `None`, `"sur"` $\rightarrow$ Rechazado correctamente (`400 Bad Request`).
* **Longitud (`longitude`):**
  * *Partición inválida ($< -180^\circ$ o $> 180^\circ$):* `-180.01`, `180.01`, `None` $\rightarrow$ Rechazado (`400 Bad Request`).
  * *Partición válida ($[-180^\circ, 180^\circ]$):* `-180.0`, `-67.50`, `0.0`, `180.0` $\rightarrow$ Aceptado (`200 OK`).
* **Variables (`variable`):**
  * *Partición válida MVP:* `T2M`, `PRECTOTCORR`, `RH2M`, `WS2M`, `T2M_MAX`, `T2M_MIN` (insensible a mayúsculas/minúsculas) $\rightarrow$ Aceptado (`200 OK`).
  * *Partición inválida:* `NDVI`, `CO2`, `""`, `12345` $\rightarrow$ Rechazado (`400 Bad Request`).
* **Rango de años (`start_year`, `end_year`) — ❌ ERROR ENCONTRADO (H-01):**
  * En [api_routes.py](../../tests/statistics_fixtures/main_legacy/api_routes_reference.py), la validación acepta `end_year <= 2026` y `end_year - start_year >= 2` (mínimo 3 años).
  * En [results.html](../../templates/pages/results.html#L86) y [compare.html](../../templates/pages/compare.html#L153), el input permite hasta `2025` (mientras que en [explorer.html](../../templates/pages/explorer.html#L263) el máximo es `2024`).
  * **Fallo:** Cuando se solicita `start_year=2023, end_year=2025` para Comodoro Rivadavia (`-45.86, -67.50`), el validador de la API aprueba la petición, pero [comodoro_rivadavia_2000_2024.json](../../tests/statistics_fixtures/main_legacy/comodoro_rivadavia_2000_2024.json) solo contiene datos hasta `2024`. Como resultado, la serie filtrada queda con solo **2 puntos** (`2023` y `2024`) y [compute_linear_trend](../../services/science/trend_analysis.py) lanza una excepción no capturada `ValueError: Se requieren al menos 3 años válidos para calcular la regresión lineal (recibidos: 2)`.

---

### 2.2. Pruebas de Caja Negra (Entradas / Salidas sin ver el código interno)
Se probaron todas las rutas HTTP de páginas y endpoints verificando códigos de estado, cabeceras `Content-Type` y contratos JSON:

* `GET /`, `/explorer`, `/results`, `/compare` y sus variantes `.html`: responden `200 OK` con `text/html` y contienen los contenedores DOM requeridos (`#home-location-map`, `#explorer-map`, `#resultsTrendChart`, `#comparisonChart`).
* `GET /api/variables`, `GET /api/summary`, `GET /api/missions`, `POST /api/analyze`, `POST /api/compare`: cumplen el esquema JSON de la página 6 del PDF.
* **❌ ERRORES DE CAJA NEGRA ENCONTRADOS:**
  1. **Rutas `/missions` y `/about` incompletas (H-03):** Desde la perspectiva del usuario final (Caja Negra), hacer clic en *"Modo detective"* (`/missions`) o *"Nosotros y metodología"* (`/about`) en la barra de navegación no lleva a esas pantallas, sino que recarga el Explorador o el Inicio sin aviso.
  2. **Desincronización del selector rápido en `/results` (H-06):** Si el usuario llega a `/results?lat=-54.80&lon=-68.30&location=Ushuaia`, el título principal muestra *"Ushuaia"*, pero el desplegable superior `#quickLocationSelect` sigue mostrando seleccionado *"Comodoro Rivadavia"*.

---

### 2.3. Pruebas de Caja Blanca (Inspección de Ramas Internas y Flujo de Datos)
Se analizaron todas las ramas condicionales internas de Python y JavaScript:

* **Agregación y limpieza (`aggregate_to_annual_series`):**
  * Se probaron las ramas para entradas `None`, listas anuales con duplicados, diccionarios mensuales de NASA POWER con clave `YYYY13` (mes 13 de resumen anual) y diccionarios diarios (`YYYYMMDD`) con menos y más de 270 días válidos. Todas las ramas internas funcionaron correctamente.
* **❌ ERRORES DE CAJA BLANCA ENCONTRADOS:**
  1. **Incompatibilidad de enumeración `direction` entre Backend y `explorer.js` (H-02):**
     * En [trend_analysis.py](../../services/science/trend_analysis.py), cuando la pendiente es cercana a cero ($|m| \le 10^{-5}$), el backend devuelve `"direction": "stable"`.
     * En [explorer.js](../../static/js/exploration/explorer.js), el objeto `directionLabelMap` define `increasing`, `decreasing` y `no_clear_trend`, pero **no incluye la clave `stable`**. Por ello, en series estables el badge preliminar del Explorador imprime literalmente `"stable"` en lugar de `"Sin tendencia clara ↔"`.
  2. **Plantilla `layouts/base.html` con etiquetas Jinja2 sin procesar (H-04):**
     * En [layouts/base.html](../../templates/layouts/base.html#L15), se utiliza `{{ url_for('static', filename='css/global/styles.css') }}`. Sin embargo, en [app.py](../../app.py#L57-L95) las rutas usan `send_file()` (y en el servidor HTTP de respaldo `_send_file()`) en lugar de `render_template()`, por lo que cualquier acceso a `/templates/base.html` entrega texto Jinja2 crudo al navegador.

---

### 2.4. Pruebas de Hilos y Concurrencia (Multithreading)
Se ejecutó una prueba de estrés concurrente con `ThreadPoolExecutor` (`max_workers=8`, 24 tareas simultáneas) sobre los servicios de análisis y el servidor HTTP:

* **Cálculo estadístico concurrente:** Las funciones matemáticas de [trend_analysis.py](../../services/science/trend_analysis.py) no comparten variables globales mutables, por lo que los 24 hilos produjeron resultados matemáticos exactos sin interferencia.
* **❌ ERRORES DE HILOS / CONCURRENCIA ENCONTRADOS (H-07 y H-08):**
  1. **Servidor HTTP de respaldo monohilo bloqueante (H-07):**
     * En [app.py](../../app.py#L196), el servidor de respaldo instancia `HTTPServer((host, port), EarthLensUnifiedHandler)` en lugar de `ThreadingHTTPServer`. `HTTPServer` atiende una sola petición a la vez de forma secuencial: si un hilo demora 4 segundos esperando a la API externa de la NASA (o mantiene un socket abierto), todas las demás pestañas o peticiones concurrentes de `index.js` / `compare.js` quedan bloqueadas en fila.
  2. **Diccionario `_MEMORY_CACHE` sin cerrojo (`threading.Lock`) (H-08):**
     * En [power.py](../../tests/statistics_fixtures/main_legacy/power_reference.py), el diccionario global `_MEMORY_CACHE` es leído y escrito por múltiples hilos sin sincronización (`threading.Lock`), exponiendo condiciones de carrera (*race conditions*) al actualizar o limpiar la caché bajo carga concurrente.

---

### 2.5. Pruebas Orientadas a Objetos (Encapsulamiento, Herencia y Estado)
Se evaluó el diseño orientado a objetos de `EarthLensUnifiedHandler` y el encapsulamiento de estado en los módulos de servicio:

* **Herencia y Polimorfismo:** `EarthLensUnifiedHandler` hereda correctamente de `BaseHTTPRequestHandler` y sobrescribe polimórficamente `do_GET` y `do_POST`.
* **❌ ERROR ORIENTADO A OBJETOS ENCONTRADO (Ruptura de Encapsulamiento por Referencia Mutable — H-09):**
  * En [power.py](../../tests/statistics_fixtures/main_legacy/power_reference.py), `fetch_nasa_power_series` guarda `(annual_series, source)` en `_MEMORY_CACHE[cache_key]` y retorna **directamente la misma referencia de la lista interna** sin copia defensiva (`copy.deepcopy` o comprensión de lista).
  * **Demostración en [test_full_audit.py](../../tests/statistics_fixtures/main_legacy/full_audit_reference.py):** Si cualquier objeto o función consumidora modifica un elemento de la lista recibida (ej. `series[0]["value"] = -12345.67`), **el estado interno privado de `_MEMORY_CACHE` queda corrompido permanentemente** para todas las consultas posteriores del servidor.

---

## 3. Matriz Priorizada de Errores Encontrados

| ID | Severidad | Tipo de Prueba | Ubicación | Descripción del Error | Solución Recomendada |
| :---: | :---: | :--- | :--- | :--- | :--- |
| **H-01** | **Alta** | Equivalencia / Valores Límite | `routes/api_routes.py`, `results.html`, `compare.html` | `end_year=2025` o `2026` con `start_year=2023` pasa la validación pero deja $<3$ años en la muestra `2000–2024`, causando `ValueError` (HTTP 500). | Unificar el límite superior en `2024` en HTML y API, y capturar `ValueError` en `handle_analyze_request` devolviendo HTTP 400/422. |
| **H-09** | **Alta** | Orientada a Objetos | `services/power.py` (`_MEMORY_CACHE`) | Fuga de encapsulamiento: `fetch_nasa_power_series` retorna la referencia mutable directa de la lista en caché. | Retornar una copia profunda (`[{"year": d["year"], "value": d["value"]} for d in series]`). |
| **H-07** | **Media** | Hilos / Concurrencia | `app.py` (`HTTPServer`) | El servidor HTTP nativo usa `HTTPServer` (secuencial/monohilo) en lugar de `ThreadingHTTPServer`. | Cambiar `from http.server import HTTPServer` por `ThreadingHTTPServer`. |
| **H-08** | **Media** | Hilos / Concurrencia | `services/power.py` | Acceso y escritura concurrente a `_MEMORY_CACHE` sin `threading.Lock()`. | Proteger lecturas y escrituras de `_MEMORY_CACHE` con `with _CACHE_LOCK:`. |
| **H-02** | **Media** | Caja Blanca (`explorer.js`) | `static/js/exploration/explorer.js` vs `services/science/trend_analysis.py` | El backend envía `direction: "stable"`, pero `explorer.js` solo traduce `no_clear_trend`, mostrando `"stable"` sin traducir. | Añadir `stable: 'Sin tendencia clara ↔'` en `directionLabelMap` de `explorer.js`. |
| **H-03** | **Media** | Caja Negra (Páginas) | `templates/` (`/missions`, `/about`) | Faltan las plantillas `pages/missions.html` y `pages/about.html` referenciadas en el menú de navegación de todas las páginas. | Crear `pages/missions.html` y `pages/about.html` o redirigir `/missions` a `/explorer?mission=comodoro`. |
| **H-06** | **Baja** | Caja Negra (`results.html`) | `static/js/exploration/results.js` | El selector `#quickLocationSelect` no se sincroniza con las coordenadas de la URL ni dispara el análisis automáticamente al cambiar de opción. | Disparar `btnApply.click()` en el evento `change` de `#quickLocationSelect` y sincronizar su valor inicial. |
| **H-04** | **Baja** | Caja Blanca (`layouts/base.html`) | `templates/layouts/base.html` | Contiene bloques Jinja2 (`{{ url_for(...) }}`) que no se procesan cuando se sirve con `send_file`. | Reemplazar por rutas estáticas o usar `render_template` en Flask. |
