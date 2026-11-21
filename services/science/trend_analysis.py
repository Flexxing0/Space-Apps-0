"""
EarthLens — Rol 06: Motor Estadístico, Agregación Anual y Reglas de Conclusión
Archivo: services/trend_analysis.py
Tecnologías: Python 3, SciPy (scipy.stats.linregress, scipy.stats.t), Pandas/NumPy (opcional)

Supuestos metodológicos documentados (Página 7 del Plan de Desarrollo):
1. Regresión lineal por Mínimos Cuadrados Ordinarios (OLS) sobre series anuales:
   - Pendiente (m): cambio estimado por año en la unidad de la variable.
   - Cambio por década: pendiente × 10.
   - Cambio total en el período: pendiente × (año_fin - año_inicio).
2. Inferencia e incertidumbre:
   - p-valor bilateral bajo distribución t de Student con (n - 2) grados de libertad.
   - Umbral de significancia α = 0.05: p < 0.05 sugiere evidencia estadística de tendencia
     bajo los supuestos del modelo (linealidad, independencia aproximada e homocedasticidad);
     un p ≥ 0.05 NO demuestra ausencia de cambio.
   - Intervalo de confianza al 95% de la pendiente: m ± t_{0.975, n-2} × SE(m).
3. Limitaciones físicas y espaciales:
   - NASA POWER (MERRA-2) representa promedios en celdas geográficas (~0.5° × 0.625°),
     no estaciones meteorológicas puntuales.
   - En RH2M, la humedad relativa atmosférica no equivale a la humedad del suelo.
   - Correlación temporal no implica causalidad directa sin análisis de forzantes físicos.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

# Intentar importar SciPy (tecnología oficial del Rol 06 en el PDF).
# Si se ejecuta fuera de Docker en un entorno sin SciPy instalado, se provee
# un respaldo matemático exacto para garantizar portabilidad total.
try:
    from scipy import stats as scipy_stats  # type: ignore

    HAS_SCIPY = True
except ImportError:
    scipy_stats = None
    HAS_SCIPY = False


MISSING_SENTINELS = {-999, -999.0, -99, -99.0, -9999, -9999.0}

VARIABLES_CATALOG: Dict[str, Dict[str, str]] = {
    "T2M": {
        "name": "Temperatura media a 2m",
        "unit": "deg C",
        "display_unit": "°C",
        "aggregation": "mean",
    },
    "PRECTOTCORR": {
        "name": "Precipitaciones corregidas",
        "unit": "mm/day",
        "display_unit": "mm/día",
        "aggregation": "mean",
    },
    "RH2M": {
        "name": "Humedad relativa a 2m",
        "unit": "%",
        "display_unit": "%",
        "aggregation": "mean",
    },
    "WS2M": {
        "name": "Velocidad del viento a 2m",
        "unit": "m/s",
        "display_unit": "m/s",
        "aggregation": "mean",
    },
    "T2M_MAX": {
        "name": "Temperatura máxima a 2m",
        "unit": "deg C",
        "display_unit": "°C",
        "aggregation": "mean",
    },
    "T2M_MIN": {
        "name": "Temperatura mínima a 2m",
        "unit": "deg C",
        "display_unit": "°C",
        "aggregation": "mean",
    },
}


def is_valid_observation(value: Any) -> bool:
    """Verifica que un valor numérico sea válido y no sea un código faltante (-999) ni NaN."""
    if value is None or isinstance(value, bool):
        return False
    try:
        num = float(value)
    except (ValueError, TypeError):
        return False
    if math.isnan(num) or math.isinf(num):
        return False
    if num in MISSING_SENTINELS or num <= -900.0:
        return False
    return True


def aggregate_to_annual_series(
    raw_data: Union[List[Dict[str, Any]], Dict[str, Any]],
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    min_months_per_year: int = 9,
    min_days_per_year: int = 270,
) -> List[Dict[str, float]]:
    """
    Convierte datos crudos (lista anual [{'year', 'value'}], diccionario mensual YYYYMM de NASA POWER
    o diccionario diario YYYYMMDD) en una serie anual limpia y ordenada [{'year': int, 'value': float}].
    Aplica criterios de completitud intra-anual descartando años con demasiados datos faltantes.
    """
    annual_series: List[Dict[str, float]] = []

    # Caso 1: Lista ya agregada por año [{'year': 2000, 'value': 12.4}, ...]
    if isinstance(raw_data, list):
        by_year: Dict[int, List[float]] = {}
        for item in raw_data:
            if not isinstance(item, dict):
                continue
            yr_raw = item.get("year")
            val_raw = item.get("value")
            if yr_raw is None or not is_valid_observation(val_raw):
                continue
            yr = int(yr_raw)
            if start_year is not None and yr < int(start_year):
                continue
            if end_year is not None and yr > int(end_year):
                continue
            by_year.setdefault(yr, []).append(float(val_raw))

        for yr in sorted(by_year.keys()):
            vals = by_year[yr]
            mean_val = sum(vals) / len(vals)
            annual_series.append({"year": yr, "value": round(mean_val, 4)})
        return annual_series

    # Caso 2: Diccionario de NASA POWER (claves 'YYYY', 'YYYYMM' o 'YYYYMMDD')
    if isinstance(raw_data, dict):
        yearly_buckets: Dict[int, List[float]] = {}
        key_lengths: Dict[int, int] = {}

        for key, val in raw_data.items():
            key_str = str(key).strip()
            if len(key_str) < 4 or not key_str[:4].isdigit():
                continue
            yr = int(key_str[:4])
            if start_year is not None and yr < int(start_year):
                continue
            if end_year is not None and yr > int(end_year):
                continue

            # En NASA POWER monthly, la clave 'YYYY13' es el resumen anual precalculado;
            # la ignoramos si estamos agregando los meses 01..12 para no duplicar peso.
            if len(key_str) == 6 and key_str[4:6] == "13":
                continue

            if not is_valid_observation(val):
                continue

            yearly_buckets.setdefault(yr, []).append(float(val))
            key_lengths[yr] = max(key_lengths.get(yr, 0), len(key_str))

        for yr in sorted(yearly_buckets.keys()):
            vals = yearly_buckets[yr]
            klen = key_lengths.get(yr, 4)
            # Validar completitud intra-anual según resolución mensual (6) o diaria (8)
            if klen == 6 and len(vals) < min_months_per_year:
                continue
            if klen == 8 and len(vals) < min_days_per_year:
                continue
            mean_val = sum(vals) / len(vals)
            annual_series.append({"year": yr, "value": round(mean_val, 4)})

    return annual_series


def evaluate_completeness(
    series: List[Dict[str, float]],
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    min_valid_years: int = 3,
    min_coverage_ratio: float = 0.70,
) -> Dict[str, Any]:
    """
    Evalúa los criterios de completitud de la serie anual en el período solicitado.
    """
    valid_years_set = {int(item["year"]) for item in series if is_valid_observation(item.get("value"))}

    if start_year is None:
        start_year = min(valid_years_set) if valid_years_set else 2000
    if end_year is None:
        end_year = max(valid_years_set) if valid_years_set else 2024

    start_year = int(start_year)
    end_year = int(end_year)
    expected_years = list(range(start_year, end_year + 1)) if end_year >= start_year else []
    n_expected = len(expected_years)

    missing_years = [yr for yr in expected_years if yr not in valid_years_set]
    n_valid = len(valid_years_set.intersection(expected_years))
    coverage_ratio = round(n_valid / n_expected, 4) if n_expected > 0 else 0.0

    is_complete = n_valid >= min_valid_years and coverage_ratio >= min_coverage_ratio

    return {
        "start_year": start_year,
        "end_year": end_year,
        "requested_years": n_expected,
        "valid_years": n_valid,
        "missing_years": missing_years,
        "coverage_ratio": coverage_ratio,
        "is_complete": is_complete,
    }


def _student_t_critical_95(df: int) -> float:
    """Retorna el valor crítico t_{0.975, df} para un intervalo de confianza del 95%."""
    if df <= 0:
        return 1.96
    if HAS_SCIPY and scipy_stats is not None:
        return float(scipy_stats.t.ppf(0.975, df))
    # Tabla exacta para grados de libertad pequeños y aproximación de Peizer-Pratt para df mayores
    t_table = {
        1: 12.7062, 2: 4.3027, 3: 3.1824, 4: 2.7764, 5: 2.5706,
        6: 2.4469, 7: 2.3646, 8: 2.3060, 9: 2.2622, 10: 2.2281,
        15: 2.1314, 20: 2.0860, 23: 2.0687, 25: 2.0595, 30: 2.0423,
    }
    if df in t_table:
        return t_table[df]
    z = 1.95996
    return z + (z**3 + z) / (4 * df) + (5 * z**5 + 16 * z**3 + 3 * z) / (96 * df**2)


def _Fallback_two_sided_t_pvalue(t_stat: float, df: int) -> float:
    """Cálculo de respaldo del p-valor bilateral para estadístico t si SciPy no está presente."""
    if df <= 0:
        return 1.0
    x = abs(t_stat)
    if x == 0.0:
        return 1.0
    # Transformación a normal estándar equivalente (aproximación de Wallace / Hill muy precisa para df >= 3)
    z = math.sqrt(df * math.log(1.0 + (x * x) / df)) * (1.0 - 1.0 / (4.0 * df))
    p = math.erfc(z / math.sqrt(2.0))
    return max(0.0, min(1.0, p))


def compute_linear_trend(
    series: List[Dict[str, float]],
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    alpha: float = 0.05,
    slope_tolerance: float = 1e-5,
) -> Dict[str, Any]:
    """
    Calcula la regresión lineal sobre una serie anual [{'year', 'value'}].
    Retorna el bloque 'statistics' compatible con el contrato de la API (Página 6 y 7 del PDF):
      - slope
      - intercept
      - change_per_decade (pendiente × 10)
      - total_change (pendiente × diferencia de años)
      - p_value
      - significant (p_value < 0.05)
      - direction ('increasing' | 'decreasing' | 'stable')
      - confidence_interval_95 ([ci_low, ci_high] para la pendiente)
      - r_value, r_squared, std_err, mean
    """
    clean = [
        {"year": int(d["year"]), "value": float(d["value"])}
        for d in series
        if isinstance(d, dict) and d.get("year") is not None and is_valid_observation(d.get("value"))
    ]
    clean.sort(key=lambda item: item["year"])

    if start_year is not None:
        clean = [d for d in clean if d["year"] >= int(start_year)]
    if end_year is not None:
        clean = [d for d in clean if d["year"] <= int(end_year)]

    n = len(clean)
    if n < 3:
        raise ValueError(
            f"Se requieren al menos 3 años válidos para calcular la regresión lineal (recibidos: {n})."
        )

    xs = [float(d["year"]) for d in clean]
    ys = [float(d["value"]) for d in clean]

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    if HAS_SCIPY and scipy_stats is not None:
        res = scipy_stats.linregress(xs, ys)
        slope = float(res.slope)
        intercept = float(res.intercept)
        r_value = float(res.rvalue) if not math.isnan(res.rvalue) else 0.0
        p_value = float(res.pvalue) if not math.isnan(res.pvalue) else 1.0
        std_err = float(res.stderr) if not math.isnan(res.stderr) else 0.0
    else:
        ss_xx = sum((x - mean_x) ** 2 for x in xs)
        ss_yy = sum((y - mean_y) ** 2 for y in ys)
        ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))

        slope = ss_xy / ss_xx if ss_xx > 0 else 0.0
        intercept = mean_y - slope * mean_x
        r_value = ss_xy / math.sqrt(ss_xx * ss_yy) if (ss_xx > 0 and ss_yy > 0) else 0.0

        residuals_sq = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
        df = n - 2
        s_err_resid = math.sqrt(residuals_sq / df) if df > 0 else 0.0
        std_err = s_err_resid / math.sqrt(ss_xx) if ss_xx > 0 else 0.0
        t_stat = slope / std_err if std_err > 0 else (1e9 if abs(slope) > 0 else 0.0)
        p_value = _Fallback_two_sided_t_pvalue(t_stat, df)

    df = n - 2
    t_crit = _student_t_critical_95(df)
    ci_low = slope - t_crit * std_err
    ci_high = slope + t_crit * std_err

    eff_start = int(start_year) if start_year is not None else int(xs[0])
    eff_end = int(end_year) if end_year is not None else int(xs[-1])
    year_span = max(1, eff_end - eff_start)

    change_per_decade = slope * 10.0
    total_change = slope * year_span
    significant = bool(p_value < alpha and abs(slope) > slope_tolerance)

    if abs(slope) <= slope_tolerance:
        direction = "stable"
    elif slope > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    return {
        "slope": round(slope, 5),
        "intercept": round(intercept, 4),
        "change_per_decade": round(change_per_decade, 4),
        "total_change": round(total_change, 3),
        "p_value": round(p_value, 5),
        "significant": significant,
        "direction": direction,
        "confidence_interval_95": [round(ci_low, 5), round(ci_high, 5)],
        "r_value": round(r_value, 4),
        "r_squared": round(r_value**2, 4),
        "std_err": round(std_err, 5),
        "mean": round(mean_y, 3),
        "n_years": n,
    }


def generate_conclusion(
    variable: str,
    statistics: Dict[str, Any],
    completeness: Optional[Dict[str, Any]] = None,
    location_name: Optional[str] = None,
) -> str:
    """
    Genera una conclusión en lenguaje científico accesible mediante reglas determinísticas
    basadas en dirección, magnitud, p-valor (< 0.05 vs >= 0.05), intervalo de confianza y variable.
    """
    var_code = (variable or "T2M").upper()
    var_meta = VARIABLES_CATALOG.get(
        var_code,
        {"name": var_code, "unit": "", "display_unit": ""},
    )
    unit_disp = var_meta["display_unit"] or var_meta["unit"]
    var_name = var_meta["name"].lower()

    slope = float(statistics.get("slope", 0.0))
    decadal = float(statistics.get("change_per_decade", slope * 10.0))
    total = float(statistics.get("total_change", 0.0))
    p_val = float(statistics.get("p_value", 1.0))
    significant = bool(statistics.get("significant", p_val < 0.05))
    direction = statistics.get("direction", "stable")
    ci = statistics.get("confidence_interval_95", [0.0, 0.0])

    dir_es = {
        "increasing": "ascendente",
        "decreasing": "descendente",
        "stable": "estable",
    }.get(direction, "estable")

    loc_clause = f" en {location_name}" if location_name else ""
    period_clause = ""
    if completeness and completeness.get("start_year") and completeness.get("end_year"):
        period_clause = f" ({completeness['start_year']}–{completeness['end_year']})"

    p_str = "< 0.0001" if p_val < 0.0001 else f"{p_val:.4f}"
    dec_sign = "+" if decadal >= 0 else ""
    tot_sign = "+" if total >= 0 else ""

    if significant:
        core_msg = (
            f"Se detectó una tendencia {dir_es} estadísticamente significativa{loc_clause}{period_clause} "
            f"para {var_name} (p = {p_str} < 0.05). "
            f"La tasa de cambio es de {dec_sign}{decadal:.3f} {unit_disp}/década "
            f"(cambio total estimado de {tot_sign}{total:.2f} {unit_disp}; "
            f"IC 95% de la pendiente: [{ci[0]:+.4f}, {ci[1]:+.4f}] {unit_disp}/año)."
        )
    else:
        core_msg = (
            f"No se encontró evidencia estadística suficiente de una tendencia lineal{loc_clause}{period_clause} "
            f"para {var_name} (p = {p_str} ≥ 0.05). "
            f"La variación estimada ({tot_sign}{total:.2f} {unit_disp}, {dec_sign}{decadal:.3f} {unit_disp}/década) "
            f"se encuentra dentro de la variabilidad interanual; un p-valor ≥ 0.05 no demuestra ausencia de cambio."
        )

    # Nota específica por variable según la Página 7 del PDF
    extra_notes = []
    if var_code == "RH2M":
        extra_notes.append("Nota: la humedad relativa atmosférica no equivale a la humedad del suelo.")
    if completeness and not completeness.get("is_complete", True):
        extra_notes.append(
            f"Advertencia de cobertura: se dispone del {int(completeness['coverage_ratio'] * 100)}% de los años del período."
        )

    if extra_notes:
        return f"{core_msg} {' '.join(extra_notes)}"
    return core_msg


def analyze_series(
    raw_data: Union[List[Dict[str, Any]], Dict[str, Any]],
    variable: str = "T2M",
    source: str = "NASA POWER / MERRA-2",
    unit: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    location_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Flujo completo de análisis estadístico que devuelve exactamente el contrato JSON
    acordado en la Página 6 del Plan de Desarrollo.
    """
    var_code = (variable or "T2M").upper()
    var_meta = VARIABLES_CATALOG.get(
        var_code,
        {"name": var_code, "unit": unit or "unknown", "display_unit": unit or ""},
    )
    resolved_unit = unit or var_meta["unit"]

    annual_series = aggregate_to_annual_series(
        raw_data, start_year=start_year, end_year=end_year
    )
    completeness = evaluate_completeness(
        annual_series, start_year=start_year, end_year=end_year
    )
    statistics = compute_linear_trend(
        annual_series, start_year=completeness["start_year"], end_year=completeness["end_year"]
    )
    conclusion = generate_conclusion(
        var_code, statistics, completeness=completeness, location_name=location_name
    )

    return {
        "variable": var_code,
        "source": source,
        "unit": resolved_unit,
        "series": annual_series,
        "statistics": statistics,
        "completeness": completeness,
        "conclusion": conclusion,
    }


def compare_two_locations(
    analysis_a: Dict[str, Any],
    analysis_b: Dict[str, Any],
    name_a: str = "Ubicación A",
    name_b: str = "Ubicación B",
) -> Dict[str, Any]:
    """
    Compara los resultados estadísticos de dos ubicaciones analizadas con la misma variable y período.
    """
    stats_a = analysis_a.get("statistics", {})
    stats_b = analysis_b.get("statistics", {})

    dec_a = float(stats_a.get("change_per_decade", 0.0))
    dec_b = float(stats_b.get("change_per_decade", 0.0))
    tot_a = float(stats_a.get("total_change", 0.0))
    tot_b = float(stats_b.get("total_change", 0.0))
    mean_a = float(stats_a.get("mean", 0.0))
    mean_b = float(stats_b.get("mean", 0.0))

    delta_decade = round(dec_a - dec_b, 4)
    delta_total = round(tot_a - tot_b, 3)
    delta_mean = round(mean_a - mean_b, 3)

    faster_location = name_a if abs(dec_a) >= abs(dec_b) else name_b
    unit = analysis_a.get("unit", "")

    comparison_conclusion = (
        f"Al comparar {name_a} y {name_b} bajo la variable {analysis_a.get('variable')}, "
        f"{faster_location} presenta la mayor magnitud de tendencia por década. "
        f"La diferencia de cambio acumulado (A − B) es de {delta_total:+.2f} {unit} "
        f"y la diferencia de media histórica es de {delta_mean:+.2f} {unit}."
    )

    return {
        "variable": analysis_a.get("variable"),
        "unit": unit,
        "location_a": {"name": name_a, **analysis_a},
        "location_b": {"name": name_b, **analysis_b},
        "deltas": {
            "mean_diff_a_minus_b": delta_mean,
            "decade_rate_diff_a_minus_b": delta_decade,
            "total_change_diff_a_minus_b": delta_total,
            "faster_changing_location": faster_location,
        },
        "comparison_conclusion": comparison_conclusion,
    }


def get_variable_color(variable: str, z_score: float) -> str:
    """
    Retorna el color hexadecimal en la paleta científica divergente correspondiente a la variable
    y al z-score de la observación anual.
    """
    var_code = (variable or "T2M").upper()
    z = float(z_score or 0.0)

    if var_code == "PRECTOTCORR":
        if z <= -2.0:
            return "#92400e"
        if z <= -1.2:
            return "#d97706"
        if z <= -0.4:
            return "#fcd34d"
        if z < 0.4:
            return "#e2e8f0"
        if z < 1.2:
            return "#38bdf8"
        if z < 2.0:
            return "#0284c7"
        return "#0369a1"

    if var_code == "RH2M":
        if z <= -2.0:
            return "#b45309"
        if z <= -1.2:
            return "#f59e0b"
        if z <= -0.4:
            return "#fde68a"
        if z < 0.4:
            return "#e2e8f0"
        if z < 1.2:
            return "#34d399"
        if z < 2.0:
            return "#10b981"
        return "#047857"

    if var_code == "WS2M":
        if z <= -2.0:
            return "#0284c7"
        if z <= -1.2:
            return "#38bdf8"
        if z <= -0.4:
            return "#bae6fd"
        if z < 0.4:
            return "#e2e8f0"
        if z < 1.2:
            return "#818cf8"
        if z < 2.0:
            return "#6366f1"
        return "#7e22ce"

    # Variables térmicas (T2M, T2M_MAX, T2M_MIN)
    if z <= -2.0:
        return "#1e3a8a"
    if z <= -1.2:
        return "#2563eb"
    if z <= -0.4:
        return "#93c5fd"
    if z < 0.4:
        return "#e2e8f0"
    if z < 1.2:
        return "#fbbf24"
    if z < 2.0:
        return "#f97316"
    return "#dc2626"


def compute_annual_anomalies(
    series: List[Dict[str, float]],
    variable: str = "T2M",
    statistics: Optional[Dict[str, Any]] = None,
    anomaly_z_threshold: float = 1.5,
) -> Dict[str, Any]:
    """
    Calcula para cada año el valor ajustado OLS, intervalo de confianza puntual,
    anomalía absoluta (y_t - media), z-score, percentil, nivel de anomalía y color.
    """
    clean = [
        {"year": int(d["year"]), "value": float(d["value"])}
        for d in series
        if isinstance(d, dict) and d.get("year") is not None and is_valid_observation(d.get("value"))
    ]
    clean.sort(key=lambda item: item["year"])
    n = len(clean)
    if n == 0:
        return {
            "timeline": [],
            "mean": 0.0,
            "std_dev": 0.0,
            "anomalies": {"threshold_z": anomaly_z_threshold, "count": 0, "max_record": None, "min_record": None, "events": []},
        }

    stats = statistics or (compute_linear_trend(clean) if n >= 3 else {})
    xs = [float(d["year"]) for d in clean]
    ys = [float(d["value"]) for d in clean]

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    variance_y = sum((y - mean_y) ** 2 for y in ys) / (n - 1) if n > 1 else 0.0
    std_y = math.sqrt(variance_y) if variance_y > 0 else 0.0

    slope = float(stats.get("slope", 0.0))
    intercept = float(stats.get("intercept", mean_y - slope * mean_x))

    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    residuals_sq = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    s_err_resid = math.sqrt(residuals_sq / (n - 2)) if n > 2 else 0.0
    t_crit = _student_t_critical_95(max(1, n - 2))

    sorted_vals = sorted(ys)
    timeline: List[Dict[str, Any]] = []
    anomaly_events: List[Dict[str, Any]] = []

    for d in clean:
        yr = d["year"]
        val = d["value"]
        y_hat = intercept + slope * yr
        se_fit = s_err_resid * math.sqrt(1.0 / n + ((yr - mean_x) ** 2) / ss_xx) if (n > 2 and ss_xx > 0) else 0.0
        margin = t_crit * se_fit

        anom = val - mean_y
        z = anom / std_y if std_y > 1e-9 else 0.0

        rank_count = sum(1 for v in sorted_vals if v <= val)
        percentile = round((rank_count / n) * 100.0, 1)

        abs_z = abs(z)
        if abs_z >= 2.0:
            level = "extreme_high" if z > 0 else "extreme_low"
        elif abs_z >= anomaly_z_threshold:
            level = "moderate_high" if z > 0 else "moderate_low"
        elif abs_z >= 1.0:
            level = "mild_high" if z > 0 else "mild_low"
        else:
            level = "normal"

        is_anom = bool(abs_z >= anomaly_z_threshold)
        color = get_variable_color(variable, z)

        point = {
            "year": yr,
            "value": round(val, 4),
            "trend_value": round(y_hat, 4),
            "ci_low": round(y_hat - margin, 4),
            "ci_high": round(y_hat + margin, 4),
            "anomaly": round(anom, 4),
            "z_score": round(z, 3),
            "percentile": percentile,
            "anomaly_level": level,
            "is_anomaly": is_anom,
            "color": color,
        }
        timeline.append(point)
        if is_anom:
            anomaly_events.append(point)

    max_point = max(timeline, key=lambda item: item["value"])
    min_point = min(timeline, key=lambda item: item["value"])

    return {
        "timeline": timeline,
        "mean": round(mean_y, 4),
        "std_dev": round(std_y, 4),
        "anomalies": {
            "threshold_z": anomaly_z_threshold,
            "count": len(anomaly_events),
            "max_record": max_point,
            "min_record": min_point,
            "events": sorted(anomaly_events, key=lambda item: abs(item["z_score"]), reverse=True),
        },
    }


def compare_time_periods(
    series: List[Dict[str, float]],
    variable: str = "T2M",
    split_year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Divide la serie temporal en dos sub-períodos (Época A: start..split_year-1 vs Época B: split_year..end)
    y calcula la diferencia de medias, cambio porcentual y prueba t de Welch bilateral.
    """
    clean = [
        {"year": int(d["year"]), "value": float(d["value"])}
        for d in series
        if isinstance(d, dict) and d.get("year") is not None and is_valid_observation(d.get("value"))
    ]
    clean.sort(key=lambda item: item["year"])
    if len(clean) < 4:
        raise ValueError("Se requieren al menos 4 años válidos para comparar dos sub-períodos.")

    years = [d["year"] for d in clean]
    min_yr, max_yr = years[0], years[-1]

    if split_year is None or int(split_year) <= min_yr + 1 or int(split_year) > max_yr - 1:
        eff_split = min_yr + (max_yr - min_yr + 1) // 2
    else:
        eff_split = int(split_year)

    group_a = [d for d in clean if d["year"] < eff_split]
    group_b = [d for d in clean if d["year"] >= eff_split]

    if len(group_a) < 2 or len(group_b) < 2:
        mid_idx = len(clean) // 2
        group_a = clean[:mid_idx]
        group_b = clean[mid_idx:]
        eff_split = group_b[0]["year"]

    vals_a = [d["value"] for d in group_a]
    vals_b = [d["value"] for d in group_b]
    n_a, n_b = len(vals_a), len(vals_b)

    mean_a = sum(vals_a) / n_a
    mean_b = sum(vals_b) / n_b
    var_a = sum((v - mean_a) ** 2 for v in vals_a) / (n_a - 1) if n_a > 1 else 0.0
    var_b = sum((v - mean_b) ** 2 for v in vals_b) / (n_b - 1) if n_b > 1 else 0.0
    std_a = math.sqrt(var_a)
    std_b = math.sqrt(var_b)

    delta_mean = mean_b - mean_a
    delta_pct = (delta_mean / abs(mean_a)) * 100.0 if abs(mean_a) > 1e-9 else 0.0

    se_diff_sq = (var_a / n_a) + (var_b / n_b)
    if se_diff_sq > 1e-12:
        t_stat = delta_mean / math.sqrt(se_diff_sq)
        num_df = se_diff_sq ** 2
        den_df = ((var_a / n_a) ** 2) / max(1, n_a - 1) + ((var_b / n_b) ** 2) / max(1, n_b - 1)
        df_welch = max(1, int(round(num_df / den_df))) if den_df > 0 else (n_a + n_b - 2)
        if HAS_SCIPY and scipy_stats is not None:
            p_val = float(scipy_stats.t.sf(abs(t_stat), df_welch) * 2.0)
        else:
            p_val = _Fallback_two_sided_t_pvalue(t_stat, df_welch)
    else:
        t_stat = 0.0
        p_val = 1.0 if abs(delta_mean) <= 1e-9 else 0.0001

    slope_a = compute_linear_trend(group_a)["change_per_decade"] if len(group_a) >= 3 else 0.0
    slope_b = compute_linear_trend(group_b)["change_per_decade"] if len(group_b) >= 3 else 0.0

    var_code = (variable or "T2M").upper()
    var_meta = VARIABLES_CATALOG.get(var_code, {"name": var_code, "display_unit": ""})
    unit_disp = var_meta.get("display_unit") or var_meta.get("unit", "")
    significant_shift = bool(p_val < 0.05 and abs(delta_mean) > 1e-5)

    label_a = f"{group_a[0]['year']}–{group_a[-1]['year']}"
    label_b = f"{group_b[0]['year']}–{group_b[-1]['year']}"
    sign_str = "+" if delta_mean >= 0 else ""
    p_str = "< 0.0001" if p_val < 0.0001 else f"{p_val:.4f}"

    if significant_shift:
        summary = (
            f"Al contrastar la época reciente ({label_b}) frente a la época base ({label_a}), "
            f"se registra un cambio estadísticamente significativo de {sign_str}{delta_mean:.2f} {unit_disp} "
            f"({sign_str}{delta_pct:.1f}%, p = {p_str} < 0.05)."
        )
    else:
        summary = (
            f"Entre la época base ({label_a}) y la época reciente ({label_b}), la diferencia media es de "
            f"{sign_str}{delta_mean:.2f} {unit_disp} ({sign_str}{delta_pct:.1f}%, p = {p_str} ≥ 0.05), "
            f"compatible con la variabilidad interanual del período."
        )

    return {
        "split_year": eff_split,
        "period_a": {
            "label": label_a,
            "start_year": group_a[0]["year"],
            "end_year": group_a[-1]["year"],
            "n_years": n_a,
            "mean": round(mean_a, 3),
            "std_dev": round(std_a, 3),
            "min": round(min(vals_a), 3),
            "max": round(max(vals_a), 3),
            "change_per_decade": round(float(slope_a), 4),
        },
        "period_b": {
            "label": label_b,
            "start_year": group_b[0]["year"],
            "end_year": group_b[-1]["year"],
            "n_years": n_b,
            "mean": round(mean_b, 3),
            "std_dev": round(std_b, 3),
            "min": round(min(vals_b), 3),
            "max": round(max(vals_b), 3),
            "change_per_decade": round(float(slope_b), 4),
        },
        "delta_mean": round(delta_mean, 3),
        "delta_percent": round(delta_pct, 2),
        "t_stat": round(t_stat, 4),
        "p_value": round(p_val, 5),
        "significant_shift": significant_shift,
        "summary": summary,
    }

