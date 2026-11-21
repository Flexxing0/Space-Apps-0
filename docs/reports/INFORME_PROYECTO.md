# 📄 Informe Técnico y Científico — Proyecto EarthLens
**NASA Space Apps Challenge 2026 · Be An Earth System Trend Detective!**  
**Equipo:** PatagoniaPrime  
**Fecha:** Noviembre 2026  

---

## 1. Resumen Ejecutivo
> *[COMPLETAR: Breve párrafo de 4–5 líneas describiendo el propósito general alcanzado por el equipo, las regiones analizadas principalmente y el hallazgo más relevante de la demostración.]*

* **Problema abordado:** Dificultad para que ciudadanos, estudiantes y tomadores de decisiones traduzcan datos satelitales climáticos crudos en evidencia estadística comprensible sobre tendencias ambientales.
* **Solución propuesta (EarthLens):** Aplicación web interactiva conectada a **NASA POWER (MERRA-2)** que automatiza la descarga, limpieza, agregación anual, cálculo de regresión lineal e interpretación estadística guiada.

---

## 2. Manual de Uso del Programa (Flujo de Investigación)

El sistema sigue el flujo de investigación en **4 etapas**: **1. Elegir → 2. Configurar → 3. Analizar → 4. Descubrir**.

### 2.1. Pantalla de Inicio (`/`)
* **Cómo se utiliza:**
  1. Al ingresar a la plataforma, el mapa superior muestra la ubicación actual (o permite hacer clic en cualquier coordenada del planeta).
  2. La sección inferior consulta automáticamente un resumen rápido (`/api/summary`) de las 6 variables climáticas principales para esa celda geográfica.
* **Registro de prueba del equipo:**
  * **Ubicación probada en Inicio:** `[COMPLETAR: ej. Comodoro Rivadavia / Buenos Aires]`
  * **Observación / Captura:** `[COMPLETAR: insertar captura o comentario del comportamiento inicial]`

### 2.2. Explorador Ambiental (`/explorer`)
* **Cómo se utiliza:**
  1. Seleccionar un punto en el mapa interactivo (Leaflet + OpenStreetMap / Vista Satelital), usar un botón de ubicación rápida (preset) o ingresar latitud y longitud manualmente.
  2. Elegir la **variable climática** del catálogo NASA POWER.
  3. Definir el **período de análisis** (`año_inicio` y `año_fin`, entre 1981 y 2024).
  4. Presionar **"Analizar tendencia"** para validar los parámetros y enviar la consulta a `POST /api/analyze`.
* **Registro de prueba del equipo:**
  * **Coordenadas ingresadas:** `Lat: [COMPLETAR] / Lon: [COMPLETAR]`
  * **Período seleccionado:** `[COMPLETAR: ej. 2000 – 2024]`

### 2.3. Dashboard de Resultados (`/results`)
* **Cómo se utiliza:**
  1. Visualizar el **bloque de conclusión estadística** y el *badge* de significancia ($p < 0.05$ vs $p \ge 0.05$).
  2. Revisar las **4 tarjetas de métricas**: Pendiente anual, Magnitud del cambio total, $p\text{-valor}$ y Dirección con Intervalo de Confianza al 95%.
  3. Analizar el **gráfico interactivo (`Chart.js`)** que superpone la serie histórica anual observada, la recta de regresión lineal y la banda de incertidumbre al 95%.
  4. Inspeccionar la tabla anual de valores observados, ajustados y anomalías respecto a la media, o exportar el estudio con el botón **"Descargar CSV"**.

### 2.4. Comparador de Dos Ubicaciones (`/compare`)
* **Cómo se utiliza:**
  1. Elegir **Ubicación A** y **Ubicación B**.
  2. Seleccionar una **variable común** y un **mismo período de años** para garantizar comparabilidad científica.
  3. Presionar **"Comparar"** para superponer ambas series y sus rectas de tendencia en una misma escala, evaluando qué región cambia a mayor velocidad ($\Delta\text{ tendencia/década}$ y $\Delta\text{ cambio total}$).

---

## 3. Variables Climáticas Utilizadas (Significado y Fundamento Físico)

Los datos provienen del proyecto **NASA POWER (Prediction Of Worldwide Energy Resources)** basados en el reanálisis satelital y atmosférico **MERRA-2** (resolución espacial aproximada de $0.5^\circ \times 0.625^\circ$, equivalente a celdas de ~50 km).

### 3.1. `T2M` — Temperatura Media a 2 Metros (`°C`)
* **¿Qué significa?** Es la temperatura promedio del aire medida a 2 metros sobre la superficie terrestre (altura estándar meteorológica internacional para evitar el contacto directo con el suelo).
* **¿En qué consiste?** Representa el estado térmico general de la atmósfera baja a lo largo del año. Una tendencia positiva sostenida indica calentamiento regional.
* **Limitación a considerar:** Al promediar todo el año, un aumento fuerte en verano puede compensarse parcialmente con un invierno frío; por ello se complementa con `T2M_MAX` y `T2M_MIN`.

### 3.2. `T2M_MAX` y `T2M_MIN` — Temperatura Máxima y Mínima a 2 Metros (`°C`)
* **¿Qué significan?** Promedio anual de las temperaturas máximas diurnas (`T2M_MAX`) y mínimas nocturnas (`T2M_MIN`) a 2 metros de altura.
* **¿En qué consisten?** Permiten evaluar el comportamiento de los extremos térmicos:
  * Si `T2M_MAX` sube rápidamente, aumenta el estrés térmico diurno y la demanda evaporativa.
  * Si `T2M_MIN` sube, disminuyen las noches frías/heladas y el enfriamiento nocturno.

### 3.3. `PRECTOTCORR` — Precipitación Total Corregida (`mm/día`)
* **¿Qué significa?** Tasa media diaria de agua precipitada (lluvia y nieve derretida equivalente) expresada en milímetros por día ($\text{1 mm} = \text{1 litro de agua por m}^2$).
* **¿En qué consiste?** Combina estimaciones satelitales y modelos atmosféricos MERRA-2 corregidos con redes pluviométricas superficiales para reducir el sesgo instrumental.
* **Limitación a considerar:** La precipitación tiene una variabilidad interanual muy alta (años secos seguidos de un año con lluvias extraordinarias), lo que suele ensanchar los intervalos de confianza.

### 3.4. `RH2M` — Humedad Relativa a 2 Metros (`%`)
* **¿Qué significa?** Proporción porcentual de vapor de agua presente en el aire respecto al máximo que ese aire podría contener a su temperatura actual.
* **¿En qué consiste?** Indica qué tan seco o saturado está el aire cerca de la superficie. Cuando la temperatura (`T2M`) sube y el contenido de vapor no aumenta al mismo ritmo, la humedad relativa baja, incrementando la aridez atmosférica.
* **Aclaración científica obligatoria:** **La humedad relativa atmosférica (`RH2M`) NO equivale a la humedad del suelo**. El suelo puede estar seco mientras el aire costero es húmedo, o viceversa.

### 3.5. `WS2M` — Velocidad del Viento a 2 Metros (`m/s`)
* **¿Qué significa?** Velocidad horizontal media del viento a 2 metros sobre la superficie, medida en metros por segundo ($\text{1 m/s} = 3.6\text{ km/h}$).
* **¿En qué consiste?** Cuantifica el régimen eólico superficial, factor determinante en la Patagonia por su impacto directo sobre la erosión del suelo, la desecación de pastizales y el potencial energético.
* **Limitación a considerar:** Representa el viento medio de toda la celda geográfica (~50 km), suavizando ráfagas puntuales en cañadones o acantilados.

---

## 4. Métodos Estadísticos de Evaluación (Significado y Funcionamiento)

Para evitar conclusiones subjetivas a partir de simples gráficos, EarthLens evalúa cada serie temporal mediante **6 etapas estadísticas** implementadas en `services/science/trend_analysis.py` (`SciPy`):

### 4.1. Limpieza de Datos y Agregación Anual con Criterio de Completitud
* **¿En qué consiste?**
  1. **Filtrado de centinelas:** NASA POWER codifica las observaciones faltantes como `-999.0`. El sistema descarta todo valor $\le -900$, `NaN` o nulo antes de cualquier cálculo.
  2. **Criterio de completitud intra-anual:** Para calcular el valor de un año a partir de registros mensuales, se exige contar con al menos **9 meses válidos de los 12** ($\ge 75\%$). Si un año tiene menos datos, se excluye para no sesgar el promedio anual con una sola estación del año.
  3. **Criterio de completitud del período:** Se verifica que el período cuente con al menos 3 años válidos y una cobertura $\ge 70\%$ del rango solicitado.

### 4.2. Gráfico de Serie Temporal y Anomalía Respecto a la Media
* **¿Qué significa?** Muestra la secuencia cronológica de valores anuales observados $(x_i = \text{año}, \, y_i = \text{valor})$ y su desviación frente al promedio histórico del período ($\text{Anomalía}_i = y_i - \bar{y}$).
* **¿Para qué sirve?** Permite distinguir visualmente entre **oscilaciones interanuales** de corto plazo (ej. eventos El Niño / La Niña de 1–2 años) y **cambios estructurales de largo plazo**.

### 4.3. Regresión Lineal por Mínimos Cuadrados Ordinarios (OLS)
* **¿Qué significa?** Es un modelo matemático que ajusta una línea recta de la forma:
  $$y = m \cdot x + b$$
  donde $x$ es el año, $y$ es el valor estimado de la variable, $m$ es la **pendiente** y $b$ es la ordenada al origen.
* **¿En qué consiste?** Busca la única recta que minimiza la suma de las distancias verticales al cuadrado entre los datos reales de la NASA y la línea ($\sum (y_i - \hat{y}_i)^2$).

### 4.4. Métricas de Magnitud: Pendiente ($m$), Cambio por Década y Cambio Total
* **Pendiente anual ($m$):** Indica cuántas unidades sube ($m > 0$) o baja ($m < 0$) la variable **por cada año transcurrido**:
  $$m = \frac{\sum (x_i - \bar{x})(y_i - \bar{y})}{\sum (x_i - \bar{x})^2}$$
* **Cambio por década ($m \times 10$):** Multiplica la pendiente anual por 10 años. Es la métrica estándar utilizada por la OMM y el IPCC porque permite leer cambios climáticos en escalas humanas comprensibles (ej. $+0.35\text{ °C/década}$).
* **Cambio total estimado en el período:** Cuantifica cuánto cambió en total la variable desde el año inicial hasta el año final según la recta de tendencia:
  $$\Delta_{\text{total}} = m \times (\text{año}_{\text{fin}} - \text{año}_{\text{inicio}})$$

### 4.5. Prueba de Hipótesis y $p\text{-valor}$ (Significancia Estadística)
* **¿Qué significa?** Evalúa si la pendiente observada refleja una tendencia real o si podría ser producto del azar y del ruido natural entre años.
* **¿En qué consiste?**
  * Se plantea la **hipótesis nula ($H_0: m = 0$)**, que asume que *no hay tendencia* (recta horizontal).
  * Se calcula el estadístico $t = \frac{m}{SE(m)}$ bajo una distribución $t$ de Student con $n - 2$ grados de libertad, obteniendo el **$p\text{-valor}$ bilateral**.
  * **Regla de decisión ($\alpha = 0.05$):**
    * **Si $p < 0.05$ (Significativo):** Hay menos de un 5% de probabilidad de observar esa pendiente por simple azar. Se rechaza $H_0$ y se concluye que **existe evidencia estadística de una tendencia**.
    * **Si $p \ge 0.05$ (No significativo):** No hay evidencia suficiente para confirmar una tendencia lineal. **Importante:** *un $p \ge 0.05$ no demuestra ausencia de cambio*, sino que la variabilidad entre años es alta respecto al tamaño de la muestra.

### 4.6. Intervalo de Confianza al 95% (IC 95%)
* **¿Qué significa?** Es el rango numérico dentro del cual se encuentra la verdadera pendiente de cambio con un 95% de confianza estadística.
* **¿En qué consiste?** Se calcula a partir del error estándar de la pendiente $SE(m)$ y el valor crítico $t_{0.975, \, n-2}$:
  $$\text{IC}_{95\%} = m \pm t_{0.975, \, n-2} \cdot SE(m)$$
  * Si ambos extremos del intervalo tienen el mismo signo (por ejemplo $[+0.025, +0.049]$, sin incluir el $0$), confirma visual y numéricamente que la tendencia es estadísticamente significativa.

---

## 5. Registro de Resultados y Conclusiones (Plantilla para Completar)

> *Instrucciones para el equipo: Ejecutar cada consulta en EarthLens (`http://localhost:8000`) y completar las tablas e interpretaciones a continuación.*

### 5.1. Caso Base de Validación: Comodoro Rivadavia (2000–2024)
* **Coordenadas:** `Lat: -45.86° | Lon: -67.50°`
* **Período:** `2000 – 2024 (25 años)`

| Variable | Promedio del Período | Pendiente Anual ($m$) | Cambio por Década ($m \times 10$) | Cambio Total (2000–2024) | $p\text{-valor}$ | ¿Significativo ($p < 0.05$)? | IC 95% Pendiente |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`T2M` (°C)** | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[Sí / No]` | `[mín, máx]` |
| **`T2M_MAX` (°C)** | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[Sí / No]` | `[mín, máx]` |
| **`T2M_MIN` (°C)** | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[Sí / No]` | `[mín, máx]` |
| **`PRECTOTCORR` (mm/d)** | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[Sí / No]` | `[mín, máx]` |
| **`RH2M` (%)** | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[Sí / No]` | `[mín, máx]` |
| **`WS2M` (m/s)** | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` | `[Sí / No]` | `[mín, máx]` |

---

### 5.2. Evaluación por Misiones Científicas (Modo Detective)

#### Misión 01 · Patagonia Cambiante (Temperatura)
* **Pregunta de investigación:** *¿Está aumentando la temperatura en la región analizada?*
* **Ubicación y período evaluados:** `[COMPLETAR]`
* **Resultados obtenidos (`T2M`, `T2M_MAX`, `T2M_MIN`):**
  * `[COMPLETAR: pegar los valores arrojados por el dashboard]`
* **Conclusión respectiva del equipo:**
  * **Dirección y magnitud:** `[COMPLETAR: ej. Se observa un calentamiento de +X °C/década...]`
  * **Evidencia estadística:** `[COMPLETAR: explicar el p-valor y si el IC 95% cruza o no el cero]`
  * **Implicancia ambiental:** `[COMPLETAR: ej. impacto sobre evaporación, amplitud térmica diurna/nocturna]`

---

#### Misión 02 · En Busca del Agua (Precipitaciones y Humedad)
* **Pregunta de investigación:** *¿Están disminuyendo las precipitaciones y la humedad atmosférica?*
* **Ubicación y período evaluados:** `[COMPLETAR]`
* **Resultados obtenidos (`PRECTOTCORR`, `RH2M`, `T2M`):**
  * `[COMPLETAR: pegar valores del dashboard]`
* **Conclusión respectiva del equipo:**
  * **Dirección y magnitud:** `[COMPLETAR]`
  * **Evidencia estadística:** `[COMPLETAR]`
  * **Distinción clave (Humedad del aire vs. suelo):** `[COMPLETAR: explicar cómo se relaciona la baja de RH2M con el aumento de T2M y por qué RH2M no mide directamente el agua almacenada en el suelo]`

---

#### Misión 03 · El Misterio del Viento y Comparación Regional (`/compare`)
* **Pregunta de investigación:** *¿Cómo difiere la tendencia climática entre dos ubicaciones patagónicas bajo la misma variable y período?*
* **Variable y período común:** `Variable: [COMPLETAR, ej. WS2M o T2M] | Período: [COMPLETAR, ej. 2000–2024]`

| Métrica Comparativa | Ubicación A: `[COMPLETAR Nombre]` | Ubicación B: `[COMPLETAR Nombre]` | Diferencia ($\text{A} - \text{B}$) |
| :--- | :---: | :---: | :---: |
| **Coordenadas (Lat, Lon)** | `[COMPLETAR]` | `[COMPLETAR]` | — |
| **Promedio del período** | `[COMPLETAR]` | `[COMPLETAR]` | `[Δ Media]` |
| **Pendiente anual ($m$)** | `[COMPLETAR]` | `[COMPLETAR]` | — |
| **Cambio por década** | `[COMPLETAR]` | `[COMPLETAR]` | `[Δ Tendencia/déc]` |
| **Cambio total acumulado** | `[COMPLETAR]` | `[COMPLETAR]` | `[Δ Cambio total]` |
| **$p\text{-valor}$ y Significancia** | `[COMPLETAR]` | `[COMPLETAR]` | — |

* **Conclusión comparativa del equipo:**
  * **¿Qué ubicación cambia más rápido?:** `[COMPLETAR]`
  * **Contraste de significancia estadística:** `[COMPLETAR: ¿en ambas es significativa la tendencia o solo en una?]`
  * **Interpretación geográfica/física:** `[COMPLETAR: ej. diferencia latitudinal, cercanía al mar o cordillera]`

---

## 6. Limitaciones Metodológicas y Trabajo Futuro

1. **Resolución espacial de grilla (MERRA-2):** Los valores corresponden a celdas geográficas satelitales (~50 km) y no a estaciones meteorológicas puntuales; microclimas urbanos o de valles estrechos pueden diferir del promedio de la celda.
2. **Linealidad y autocorrelación:** La regresión lineal OLS captura la tendencia monótona media del período, pero los sistemas climáticos también presentan ciclos multidecadales y no linealidades.
3. **Correlación vs. Causalidad:** Detectar una tendencia estadísticamente significativa ($p < 0.05$) demuestra que existe un cambio sistemático en el período observado, pero atribuir sus causas físicas requiere modelos de atribución climática adicionales.
4. **Próximos pasos (Post-MVP):** `[COMPLETAR: ej. integración con GLDAS para humedad real del suelo, GPM/IMERG para lluvias de alta resolución y test no paramétrico de Mann-Kendall].`
