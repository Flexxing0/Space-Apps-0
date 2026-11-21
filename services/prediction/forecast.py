"""
EarthLens — Módulo Predictivo de Earth Time Machine (services/prediction/forecast.py)

Proyecta la tendencia observada de una variable NASA POWER / MERRA-2 hacia un intervalo
futuro y estima probabilidades de anomalías, récords y cruces de umbral, generando
conclusiones automáticas en lenguaje accesible.

Metodología (todo derivado de la serie anual histórica, sin datos externos):
  1. Ajuste OLS  y_t = a + b·t  sobre la serie anual limpia (n años).
  2. Distribución predictiva de un año futuro t (regresión clásica):
         y_t ~ ŷ_t + s_pred · T_{n-2}
         s_pred² = s² + s²·(1/n + (t - x̄)² / Sxx)·φ²
     donde s es el error estándar residual y φ = sqrt((1+r1)/(1-r1)) infla la
     incertidumbre de la tendencia cuando los residuos tienen autocorrelación lag-1 r1 > 0.
  3. Umbrales definidos con la climatología histórica del período (media ȳ, desvío s_y):
         anomalía moderada  |z| ≥ 1.5   ·   anomalía extrema |z| ≥ 2.0
         récords: máximo y mínimo observados.
  4. Probabilidad anual de cada evento:  P(y_t ≥ c) = 1 − F_T((c − ŷ_t)/s_pred).
     En el horizonte H:  años esperados = Σ p_t ;  P(≥ 1 evento) = 1 − Π(1 − p_t)
     (supone independencia interanual de los residuos).
  5. Escenario de referencia "clima estacionario": y ~ ȳ + s_y·sqrt(1 + 1/n)·T_{n-1}.
     El cociente de riesgo (risk ratio) compara ambos escenarios.

Limitaciones: es una extrapolación estadística (no un modelo climático físico tipo CMIP6),
supone que la tendencia y la variabilidad se mantienen, y representa celdas MERRA-2,
no estaciones puntuales.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from services.science.trend_analysis import VARIABLES_CATALOG, compute_linear_trend, is_valid_observation

try:
    from scipy import stats as scipy_stats  # type: ignore

    HAS_SCIPY = True
except ImportError:  # pragma: no cover - depende del entorno
    scipy_stats = None
    HAS_SCIPY = False


MIN_YEARS_FOR_FORECAST = 5
DEFAULT_HORIZON_YEARS = 10
MAX_HORIZON_YEARS = 30
MODERATE_Z = 1.5
EXTREME_Z = 2.0

# Límites físicos de cada variable (para no mostrar valores imposibles en la proyección)
PHYSICAL_BOUNDS: Dict[str, Tuple[Optional[float], Optional[float]]] = {
    "PRECTOTCORR": (0.0, None),
    "RH2M": (0.0, 100.0),
    "WS2M": (0.0, None),
}

EVENT_KEYS = (
    "high_moderate",
    "high_extreme",
    "low_moderate",
    "low_extreme",
    "record_high",
    "record_low",
    "above_mean",
)


# ---------------------------------------------------------------------------
# 1. Distribución t de Student (SciPy o respaldo exacto por función beta incompleta)
# ---------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float) -> float:
    """Fracción continua de la función beta incompleta (método de Lentz)."""
    max_iter, eps, fpmin = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betainc_regularized(a: float, b: float, x: float) -> float:
    """Función beta incompleta regularizada I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_bt = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log(1.0 - x)
    )
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def student_t_cdf(t_value: float, df: float) -> float:
    """Función de distribución acumulada de la t de Student."""
    if df <= 0:
        return 0.5 * math.erfc(-t_value / math.sqrt(2.0))
    if HAS_SCIPY and scipy_stats is not None:
        return float(scipy_stats.t.cdf(t_value, df))
    if math.isinf(t_value):
        return 1.0 if t_value > 0 else 0.0
    x = df / (df + t_value * t_value)
    tail = 0.5 * _betainc_regularized(df / 2.0, 0.5, x)
    return 1.0 - tail if t_value > 0 else tail


def student_t_ppf(prob: float, df: float) -> float:
    """Cuantil de la t de Student (inversa de la CDF) por bisección si no hay SciPy."""
    prob = min(max(prob, 1e-12), 1.0 - 1e-12)
    if HAS_SCIPY and scipy_stats is not None:
        return float(scipy_stats.t.ppf(prob, df))
    lo, hi = -1.0, 1.0
    while student_t_cdf(lo, df) > prob:
        lo *= 2.0
    while student_t_cdf(hi, df) < prob:
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if student_t_cdf(mid, df) < prob:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-10:
            break
    return 0.5 * (lo + hi)


def _prob_above(threshold: float, mu: float, scale: float, df: float) -> float:
    if scale <= 1e-12:
        return 1.0 if mu >= threshold else 0.0
    return max(0.0, min(1.0, 1.0 - student_t_cdf((threshold - mu) / scale, df)))


def _prob_below(threshold: float, mu: float, scale: float, df: float) -> float:
    if scale <= 1e-12:
        return 1.0 if mu <= threshold else 0.0
    return max(0.0, min(1.0, student_t_cdf((threshold - mu) / scale, df)))


# ---------------------------------------------------------------------------
# 2. Utilidades
# ---------------------------------------------------------------------------
def _clip_physical(variable: str, value: float) -> float:
    low, high = PHYSICAL_BOUNDS.get(variable, (None, None))
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


def lag1_autocorrelation(residuals: List[float]) -> float:
    """Autocorrelación de primer orden de los residuos (persistencia interanual)."""
    n = len(residuals)
    if n < 3:
        return 0.0
    mean_r = sum(residuals) / n
    centered = [r - mean_r for r in residuals]
    den = sum(c * c for c in centered)
    if den <= 1e-12:
        return 0.0
    num = sum(centered[i] * centered[i - 1] for i in range(1, n))
    return max(-0.99, min(0.99, num / den))


def resolve_forecast_window(
    last_year: int,
    forecast_start: Any = None,
    forecast_end: Any = None,
    horizon: Any = None,
) -> Tuple[int, int]:
    """
    Normaliza el intervalo futuro solicitado:
      - inicio dentro de [último_año + 1, último_año + MAX_HORIZON_YEARS]
      - fin dentro de [inicio, último_año + MAX_HORIZON_YEARS]
    Si no se indica, se usa el horizonte por defecto (10 años).
    """
    max_year = last_year + MAX_HORIZON_YEARS

    def _to_int(value: Any) -> Optional[int]:
        if value is None or str(value).strip() == "":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    start = _to_int(forecast_start)
    end = _to_int(forecast_end)
    h = _to_int(horizon)

    if start is None:
        start = last_year + 1
    start = max(last_year + 1, min(max_year, start))

    if end is None:
        span = h if (h is not None and h > 0) else DEFAULT_HORIZON_YEARS
        end = start + span - 1
    end = max(start, min(max_year, end))
    return start, end


# ---------------------------------------------------------------------------
# 3. Vocabulario automático por variable (terreno / impactos)
# ---------------------------------------------------------------------------
VARIABLE_TERMS: Dict[str, Dict[str, str]] = {
    "T2M": {
        "high": "años anómalamente cálidos",
        "high_one": "un año anómalamente cálido",
        "label_high": "Año cálido anómalo",
        "low": "años anómalamente fríos",
        "low_one": "un año anómalamente frío",
        "label_low": "Año frío anómalo",
        "impact_up": (
            "Calentamiento sostenido: mayor evapotranspiración y estrés térmico sobre suelos y "
            "vegetación, aumento de la demanda hídrica del terreno y del riesgo de incendios en zonas secas."
        ),
        "impact_down": (
            "Enfriamiento: mayor frecuencia de heladas y ciclos de congelamiento que afectan "
            "la estructura del suelo, la vegetación y los cultivos."
        ),
    },
    "T2M_MAX": {
        "high": "años con máximas anómalamente altas",
        "high_one": "un año con máximas anómalamente altas",
        "label_high": "Máximas anómalamente altas",
        "low": "años con máximas anómalamente bajas",
        "low_one": "un año con máximas anómalamente bajas",
        "label_low": "Máximas anómalamente bajas",
        "impact_up": (
            "Máximas en ascenso: más días de calor extremo, mayor desecación superficial del suelo "
            "y riesgo creciente de olas de calor e incendios."
        ),
        "impact_down": "Máximas en descenso: veranos más moderados y menor estrés térmico diurno.",
    },
    "T2M_MIN": {
        "high": "años con mínimas anómalamente altas",
        "high_one": "un año con mínimas anómalamente altas",
        "label_high": "Mínimas anómalamente altas",
        "low": "años con mínimas anómalamente bajas",
        "low_one": "un año con mínimas anómalamente bajas",
        "label_low": "Mínimas anómalamente bajas",
        "impact_up": (
            "Mínimas en ascenso: menos noches frías y heladas; puede adelantar ciclos de la "
            "vegetación y reducir la acumulación de frío que necesitan algunos cultivos."
        ),
        "impact_down": "Mínimas en descenso: mayor riesgo de heladas intensas y daño por congelamiento.",
    },
    "PRECTOTCORR": {
        "high": "años anómalamente lluviosos",
        "high_one": "un año anómalamente lluvioso",
        "label_high": "Año lluvioso anómalo",
        "low": "años anómalamente secos",
        "low_one": "un año anómalamente seco",
        "label_low": "Año seco anómalo",
        "impact_up": (
            "Más precipitación: mejora potencial de la humedad disponible, pero mayor riesgo de "
            "anegamientos, escorrentía y erosión hídrica del terreno en eventos intensos."
        ),
        "impact_down": (
            "Menos precipitación: menor recarga de suelos y acuíferos, mayor riesgo de sequía y de "
            "degradación o desertificación del terreno."
        ),
    },
    "RH2M": {
        "high": "años con humedad atmosférica anómalamente alta",
        "high_one": "un año con humedad atmosférica anómalamente alta",
        "label_high": "Aire anómalamente húmedo",
        "low": "años con aire anómalamente seco",
        "low_one": "un año con aire anómalamente seco",
        "label_low": "Aire anómalamente seco",
        "impact_up": (
            "Atmósfera más húmeda: menor demanda evaporativa sobre el terreno. "
            "(La humedad relativa del aire no equivale a la humedad del suelo.)"
        ),
        "impact_down": (
            "Aire más seco: aumenta la demanda evaporativa y el riesgo de incendios. "
            "(La humedad relativa del aire no equivale a la humedad del suelo.)"
        ),
    },
    "WS2M": {
        "high": "años con viento anómalamente intenso",
        "high_one": "un año con viento anómalamente intenso",
        "label_high": "Viento anómalamente intenso",
        "low": "años con calma eólica anómala",
        "low_one": "un año con calma eólica anómala",
        "label_low": "Calma eólica anómala",
        "impact_up": (
            "Viento más intenso: mayor riesgo de erosión eólica y voladura de suelos, "
            "especialmente en suelos desnudos o degradados, y mayor evaporación."
        ),
        "impact_down": (
            "Viento menos intenso: disminuye la erosión eólica, aunque también la dispersión de "
            "contaminantes y el potencial de generación eólica."
        ),
    },
}


def _pct(p: float) -> str:
    if p >= 0.995:
        return "> 99 %"
    if p < 0.005:
        return "< 1 %"
    return f"{p * 100:.0f} %"


# ---------------------------------------------------------------------------
# 4. Motor principal
# ---------------------------------------------------------------------------
def build_forecast(
    series: List[Dict[str, Any]],
    variable: str = "T2M",
    forecast_start: Any = None,
    forecast_end: Any = None,
    horizon: Any = None,
    custom_threshold: Any = None,
    custom_direction: str = "above",
    location_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Construye la proyección estadística, las probabilidades de eventos y las conclusiones
    automáticas para el intervalo futuro [forecast_start, forecast_end].
    """
    var_code = (variable or "T2M").upper()
    var_meta = VARIABLES_CATALOG.get(var_code, {"name": var_code, "display_unit": "", "unit": ""})
    unit = var_meta.get("display_unit") or var_meta.get("unit", "")
    var_name = var_meta.get("name", var_code)
    terms = VARIABLE_TERMS.get(var_code, VARIABLE_TERMS["T2M"])

    clean = sorted(
        (
            {"year": int(d["year"]), "value": float(d["value"])}
            for d in series
            if isinstance(d, dict) and d.get("year") is not None and is_valid_observation(d.get("value"))
        ),
        key=lambda item: item["year"],
    )
    n = len(clean)
    if n < MIN_YEARS_FOR_FORECAST:
        return {
            "available": False,
            "reason": (
                f"Se requieren al menos {MIN_YEARS_FOR_FORECAST} años válidos para proyectar "
                f"(disponibles: {n})."
            ),
        }

    xs = [float(d["year"]) for d in clean]
    ys = [d["value"] for d in clean]
    first_year, last_year = int(xs[0]), int(xs[-1])
    f_start, f_end = resolve_forecast_window(last_year, forecast_start, forecast_end, horizon)
    horizon_years = f_end - f_start + 1

    # --- Ajuste OLS sin redondeos ---
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx if sxx > 0 else 0.0
    intercept = mean_y - slope * mean_x
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    df = n - 2
    s_resid = math.sqrt(sum(r * r for r in residuals) / df) if df > 0 else 0.0
    sd_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys) / (n - 1)) if n > 1 else 0.0

    trend_stats = compute_linear_trend(clean)
    p_value = float(trend_stats["p_value"])
    significant = bool(trend_stats["significant"])
    r_squared = float(trend_stats["r_squared"])

    r1 = lag1_autocorrelation(residuals)
    inflation = min(2.0, math.sqrt((1.0 + r1) / (1.0 - r1))) if r1 > 0 else 1.0
    t_crit = student_t_ppf(0.975, df)

    # --- Umbrales climatológicos ---
    record_high_pt = max(clean, key=lambda d: d["value"])
    record_low_pt = min(clean, key=lambda d: d["value"])
    thresholds = {
        "mean": mean_y,
        "high_moderate": mean_y + MODERATE_Z * sd_y,
        "high_extreme": mean_y + EXTREME_Z * sd_y,
        "low_moderate": mean_y - MODERATE_Z * sd_y,
        "low_extreme": mean_y - EXTREME_Z * sd_y,
        "record_high": record_high_pt["value"],
        "record_low": record_low_pt["value"],
    }

    custom_value: Optional[float] = None
    if custom_threshold is not None and str(custom_threshold).strip() != "":
        try:
            custom_value = float(custom_threshold)
            if math.isnan(custom_value) or math.isinf(custom_value):
                custom_value = None
        except (TypeError, ValueError):
            custom_value = None
    custom_dir = "below" if str(custom_direction).lower() in ("below", "<=", "le", "menor") else "above"

    def event_probs(mu: float, scale: float, dof: float) -> Dict[str, float]:
        probs = {
            "high_moderate": _prob_above(thresholds["high_moderate"], mu, scale, dof),
            "high_extreme": _prob_above(thresholds["high_extreme"], mu, scale, dof),
            "low_moderate": _prob_below(thresholds["low_moderate"], mu, scale, dof),
            "low_extreme": _prob_below(thresholds["low_extreme"], mu, scale, dof),
            "record_high": _prob_above(thresholds["record_high"], mu, scale, dof),
            "record_low": _prob_below(thresholds["record_low"], mu, scale, dof),
            "above_mean": _prob_above(thresholds["mean"], mu, scale, dof),
        }
        if custom_value is not None:
            probs["custom"] = (
                _prob_below(custom_value, mu, scale, dof)
                if custom_dir == "below"
                else _prob_above(custom_value, mu, scale, dof)
            )
        return probs

    # --- Escenario de referencia: clima estacionario ---
    baseline_scale = sd_y * math.sqrt(1.0 + 1.0 / n)
    baseline_probs = event_probs(mean_y, baseline_scale, n - 1)

    # --- Proyección año por año ---
    years_out: List[Dict[str, Any]] = []
    for year in range(f_start, f_end + 1):
        y_hat = intercept + slope * year
        se_mean = s_resid * math.sqrt(1.0 / n + ((year - mean_x) ** 2) / sxx) * inflation if sxx > 0 else 0.0
        se_pred = math.sqrt(s_resid ** 2 + se_mean ** 2)
        probs = event_probs(y_hat, se_pred, df)
        z_expected = (y_hat - mean_y) / sd_y if sd_y > 1e-9 else 0.0
        abs_z = abs(z_expected)
        if abs_z >= EXTREME_Z:
            level = "extreme_high" if z_expected > 0 else "extreme_low"
        elif abs_z >= MODERATE_Z:
            level = "moderate_high" if z_expected > 0 else "moderate_low"
        elif abs_z >= 1.0:
            level = "mild_high" if z_expected > 0 else "mild_low"
        else:
            level = "normal"

        years_out.append(
            {
                "year": year,
                "expected": round(_clip_physical(var_code, y_hat), 4),
                "pi_low": round(_clip_physical(var_code, y_hat - t_crit * se_pred), 4),
                "pi_high": round(_clip_physical(var_code, y_hat + t_crit * se_pred), 4),
                "ci_low": round(_clip_physical(var_code, y_hat - t_crit * se_mean), 4),
                "ci_high": round(_clip_physical(var_code, y_hat + t_crit * se_mean), 4),
                "z_expected": round(z_expected, 3),
                "expected_level": level,
                "probabilities": {k: round(v, 4) for k, v in probs.items()},
            }
        )

    # --- Agregados del intervalo ---
    event_keys = list(EVENT_KEYS) + (["custom"] if custom_value is not None else [])
    summary: Dict[str, Dict[str, Any]] = {}
    for key in event_keys:
        annual = [y["probabilities"][key] for y in years_out]
        expected_years = sum(annual)
        prob_none = 1.0
        for p in annual:
            prob_none *= (1.0 - p)
        p0 = baseline_probs[key]
        mean_annual = expected_years / horizon_years
        summary[key] = {
            "threshold": round(custom_value if key == "custom" else thresholds["mean" if key == "above_mean" else key], 4),
            "prob_at_least_one": round(1.0 - prob_none, 4),
            "expected_years": round(expected_years, 2),
            "mean_annual_prob": round(mean_annual, 4),
            "baseline_annual_prob": round(p0, 4),
            "baseline_expected_years": round(p0 * horizon_years, 2),
            "baseline_prob_at_least_one": round(1.0 - (1.0 - p0) ** horizon_years, 4),
            "risk_ratio": round(mean_annual / p0, 2) if p0 > 1e-6 else None,
            "first_likely_year": next((y["year"] for y in years_out if y["probabilities"][key] >= 0.5), None),
        }

    historical_frequency = {
        "high_moderate": sum(1 for v in ys if v >= thresholds["high_moderate"]),
        "low_moderate": sum(1 for v in ys if v <= thresholds["low_moderate"]),
        "high_extreme": sum(1 for v in ys if v >= thresholds["high_extreme"]),
        "low_extreme": sum(1 for v in ys if v <= thresholds["low_extreme"]),
        "n_years": n,
    }

    # --- Año en que la tendencia media cruza el umbral de anomalía moderada ---
    crossing: Optional[Dict[str, Any]] = None
    if abs(slope) > 1e-9:
        target_key = "high_moderate" if slope > 0 else "low_moderate"
        cross_year = (thresholds[target_key] - intercept) / slope
        crossing = {
            "threshold_key": target_key,
            "threshold": round(thresholds[target_key], 4),
            "year": int(math.ceil(cross_year)),
            "already_crossed": cross_year <= last_year,
            "within_window": f_start <= cross_year <= f_end,
            "reliable": significant,
        }

    # --- Nivel de confianza de la proyección ---
    score = 0
    score += 2 if p_value < 0.05 else (1 if p_value < 0.20 else 0)
    score += 1 if r_squared >= 0.30 else 0
    score += 1 if n >= 20 else (-1 if n < 10 else 0)
    lead = f_end - last_year
    score += 1 if lead <= n / 2 else (-1 if lead > n else 0)
    score -= 1 if r1 > 0.40 else 0
    confidence = "alta" if (score >= 4 and r_squared >= 0.30) else ("media" if score >= 2 else "baja")

    last_point = years_out[-1]
    conclusions = _build_conclusions(
        var_code=var_code,
        var_name=var_name,
        unit=unit,
        terms=terms,
        location_name=location_name,
        first_year=first_year,
        last_year=last_year,
        f_start=f_start,
        f_end=f_end,
        horizon_years=horizon_years,
        slope=slope,
        p_value=p_value,
        significant=significant,
        mean_y=mean_y,
        sd_y=sd_y,
        last_point=last_point,
        summary=summary,
        thresholds=thresholds,
        record_high_pt=record_high_pt,
        record_low_pt=record_low_pt,
        crossing=crossing,
        confidence=confidence,
        r1=r1,
        n=n,
        custom_value=custom_value,
        custom_dir=custom_dir,
    )

    headline = conclusions[0]["text"] if conclusions else ""

    return {
        "available": True,
        "variable": var_code,
        "unit": unit,
        "method": "OLS + intervalo de predicción t de Student (n-2 g.l.) con corrección por autocorrelación lag-1",
        "history": {"start_year": first_year, "end_year": last_year, "n_years": n},
        "window": {"start_year": f_start, "end_year": f_end, "horizon_years": horizon_years,
                   "max_end_year": last_year + MAX_HORIZON_YEARS},
        "model": {
            "slope": round(slope, 6),
            "intercept": round(intercept, 4),
            "change_per_decade": round(slope * 10.0, 4),
            "p_value": round(p_value, 5),
            "significant": significant,
            "r_squared": round(r_squared, 4),
            "residual_std": round(s_resid, 4),
            "lag1_autocorrelation": round(r1, 3),
            "uncertainty_inflation": round(inflation, 3),
            "t_critical_95": round(t_crit, 4),
            "historical_mean": round(mean_y, 4),
            "historical_std": round(sd_y, 4),
        },
        "thresholds": {
            "mean": round(thresholds["mean"], 4),
            "high_moderate": round(thresholds["high_moderate"], 4),
            "high_extreme": round(thresholds["high_extreme"], 4),
            "low_moderate": round(thresholds["low_moderate"], 4),
            "low_extreme": round(thresholds["low_extreme"], 4),
            "record_high": {"value": round(record_high_pt["value"], 4), "year": record_high_pt["year"]},
            "record_low": {"value": round(record_low_pt["value"], 4), "year": record_low_pt["year"]},
            "custom": (
                {"value": round(custom_value, 4), "direction": custom_dir} if custom_value is not None else None
            ),
        },
        "event_labels": _event_labels(terms, unit, custom_value, custom_dir),
        "years": years_out,
        "summary": summary,
        "historical_frequency": historical_frequency,
        "crossing": crossing,
        "confidence": confidence,
        "headline": headline,
        "conclusions": conclusions,
        "disclaimer": (
            "Proyección estadística por extrapolación de la tendencia observada en datos NASA POWER / MERRA-2. "
            "No reemplaza escenarios de modelos climáticos físicos (CMIP6) y supone que la tendencia y la "
            "variabilidad interanual se mantienen."
        ),
    }


def _event_labels(terms: Dict[str, str], unit: str, custom_value: Optional[float], custom_dir: str) -> Dict[str, str]:
    """Etiquetas legibles de cada evento probabilístico para la interfaz."""
    labels = {
        "high_moderate": f"{terms['label_high']} (≥ +1.5σ)",
        "high_extreme": "Extremo alto (≥ +2σ)",
        "low_moderate": f"{terms['label_low']} (≤ −1.5σ)",
        "low_extreme": "Extremo bajo (≤ −2σ)",
        "record_high": "Nuevo récord máximo",
        "record_low": "Nuevo récord mínimo",
        "above_mean": "Año sobre la media histórica",
    }
    if custom_value is not None:
        sym = "≤" if custom_dir == "below" else "≥"
        labels["custom"] = f"Umbral personalizado ({sym} {custom_value:.2f} {unit})"
    return labels


def _build_conclusions(**ctx: Any) -> List[Dict[str, str]]:
    """Reglas determinísticas que traducen los resultados numéricos a conclusiones legibles."""
    unit = ctx["unit"]
    terms = ctx["terms"]
    summary = ctx["summary"]
    thresholds = ctx["thresholds"]
    loc = f" en {ctx['location_name']}" if ctx.get("location_name") else ""
    f_start, f_end, horizon = ctx["f_start"], ctx["f_end"], ctx["horizon_years"]
    window_label = f"{f_start}–{f_end}" if f_end > f_start else f"{f_start}"
    p_val = ctx["p_value"]
    p_str = "< 0.0001" if p_val < 0.0001 else f"{p_val:.4f}"
    dec = ctx["slope"] * 10.0
    last = ctx["last_point"]
    out: List[Dict[str, str]] = []

    # 1. Proyección central
    if ctx["significant"]:
        out.append({
            "kind": "projection",
            "level": "info",
            "title": "Proyección de la tendencia",
            "text": (
                f"Si continúa la tendencia observada{loc} ({ctx['first_year']}–{ctx['last_year']}: "
                f"{dec:+.3f} {unit}/década, p = {p_str}), el valor esperado de {ctx['var_name'].lower()} "
                f"para {f_end} es {last['expected']:.2f} {unit} (intervalo de predicción 95 %: "
                f"{last['pi_low']:.2f} a {last['pi_high']:.2f} {unit}), frente a una media histórica de "
                f"{ctx['mean_y']:.2f} {unit}."
            ),
        })
    else:
        out.append({
            "kind": "projection",
            "level": "warning",
            "title": "Proyección exploratoria (tendencia no significativa)",
            "text": (
                f"La tendencia observada{loc} ({dec:+.3f} {unit}/década) no es estadísticamente "
                f"significativa (p = {p_str} ≥ 0.05). Extrapolándola, {f_end} rondaría "
                f"{last['expected']:.2f} {unit} (IP 95 %: {last['pi_low']:.2f} a {last['pi_high']:.2f} {unit}), "
                f"pero un clima estable alrededor de la media ({ctx['mean_y']:.2f} {unit}) es igual de compatible "
                f"con los datos."
            ),
        })

    # 2-3. Riesgo de anomalías en cada cola
    for side, key in (("high", "high_moderate"), ("low", "low_moderate")):
        s = summary[key]
        rr = s["risk_ratio"]
        p1 = s["prob_at_least_one"]
        sym = "≥" if side == "high" else "≤"
        sigma = "+1.5σ" if side == "high" else "−1.5σ"
        if rr is not None and rr >= 2.0 and p1 >= 0.5:
            level = "danger"
        elif rr is not None and rr >= 1.25:
            level = "warning"
        elif rr is not None and rr <= 0.75:
            level = "success"
        else:
            level = "info"
        rr_text = ""
        if rr is not None:
            if rr >= 1.25:
                rr_text = f" — {rr:.1f} veces más frecuente que en un clima estable"
            elif rr <= 0.75:
                rr_text = f" — menos frecuente que en un clima estable (×{rr:.2f})"
            else:
                rr_text = " — similar a un clima estable"
        if not ctx["significant"] and rr is not None and rr >= 1.25:
            level = "warning" if level == "danger" else level
            rr_text += (
                " (aumento debido sobre todo a la incertidumbre de extrapolar una tendencia no confirmada,"
                " no a un cambio demostrado)"
            )
        out.append({
            "kind": f"risk_{side}",
            "level": level,
            "title": f"Probabilidad de {terms[side]}",
            "text": (
                f"En {window_label} la probabilidad de registrar al menos {terms[side + '_one']} "
                f"({sym} {s['threshold']:.2f} {unit}, {sigma}) es {_pct(p1)}. Se esperan ≈ "
                f"{s['expected_years']:.1f} de {horizon} años, frente a {s['baseline_expected_years']:.1f} "
                f"si el clima fuera estacionario{rr_text}."
            ),
        })

    # 4. Récords
    rh = summary["record_high"]
    rl = summary["record_low"]
    rec_hi_pt, rec_lo_pt = ctx["record_high_pt"], ctx["record_low_pt"]
    dominant = rh if ctx["slope"] >= 0 else rl
    out.append({
        "kind": "records",
        "level": "warning" if dominant["prob_at_least_one"] >= 0.5 else "info",
        "title": "Probabilidad de nuevos récords",
        "text": (
            f"Probabilidad de superar el máximo histórico ({rec_hi_pt['value']:.2f} {unit}, {rec_hi_pt['year']}) "
            f"al menos una vez en {window_label}: {_pct(rh['prob_at_least_one'])}. "
            f"Probabilidad de quedar por debajo del mínimo histórico ({rec_lo_pt['value']:.2f} {unit}, "
            f"{rec_lo_pt['year']}): {_pct(rl['prob_at_least_one'])}."
        ),
    })

    # 5. Cruce de umbral por la tendencia media
    crossing = ctx.get("crossing")
    if crossing and crossing["reliable"]:
        side_word = "anomalía alta" if crossing["threshold_key"] == "high_moderate" else "anomalía baja"
        if crossing["already_crossed"]:
            text = (
                f"La recta de tendencia ya supera el umbral de {side_word} ({crossing['threshold']:.2f} {unit}): "
                f"lo que en el período histórico era excepcional ya es la condición típica."
            )
            level = "danger"
        elif crossing["year"] <= ctx["last_year"] + 50:
            text = (
                f"Al ritmo actual, el año «promedio» alcanzaría el umbral de {side_word} "
                f"({crossing['threshold']:.2f} {unit}) hacia {crossing['year']}: lo que hoy es excepcional "
                f"pasaría a ser habitual."
            )
            level = "danger" if crossing["within_window"] else "warning"
        else:
            text = None
            level = "info"
        if text:
            out.append({"kind": "crossing", "level": level, "title": "Cambio de normalidad", "text": text})

    # 6. Interpretación sobre el terreno
    if p_val < 0.20:
        impact = terms["impact_up"] if ctx["slope"] > 0 else terms["impact_down"]
        prefix = "" if ctx["significant"] else "Señal débil (0.05 ≤ p < 0.20). "
        out.append({"kind": "impact", "level": "info", "title": "Qué implicaría para el terreno",
                    "text": prefix + impact})
    else:
        out.append({
            "kind": "impact",
            "level": "info",
            "title": "Qué implicaría para el terreno",
            "text": (
                "Sin una tendencia clara, el comportamiento futuro estará dominado por la variabilidad "
                "interanual: conviene planificar en función del rango histórico observado y de los años extremos."
            ),
        })

    # 7. Umbral personalizado
    if ctx.get("custom_value") is not None and "custom" in summary:
        cs = summary["custom"]
        sym = "≤" if ctx["custom_dir"] == "below" else "≥"
        first = f" El primer año con probabilidad ≥ 50 % sería {cs['first_likely_year']}." if cs["first_likely_year"] else ""
        out.append({
            "kind": "custom",
            "level": "info",
            "title": f"Umbral personalizado ({sym} {ctx['custom_value']:.2f} {unit})",
            "text": (
                f"Probabilidad de al menos un año {sym} {ctx['custom_value']:.2f} {unit} en {window_label}: "
                f"{_pct(cs['prob_at_least_one'])} (≈ {cs['expected_years']:.1f} años esperados; "
                f"clima estable: {cs['baseline_expected_years']:.1f}).{first}"
            ),
        })

    # 8. Advertencias metodológicas
    caveats = [f"Confianza de la proyección: {ctx['confidence']}."]
    if ctx["r1"] > 0.30:
        caveats.append(
            f"Los residuos muestran persistencia interanual (r1 = {ctx['r1']:.2f}); se amplió la incertidumbre."
        )
    if (f_end - ctx["last_year"]) > ctx["n"] / 2:
        caveats.append(
            f"El horizonte ({f_end - ctx['last_year']} años) supera la mitad del registro histórico "
            f"({ctx['n']} años): la extrapolación pierde fiabilidad."
        )
    caveats.append("Supone que la tendencia lineal y la variabilidad actuales se mantienen; no es un modelo climático físico.")
    out.append({
        "kind": "caveat",
        "level": "warning" if ctx["confidence"] == "baja" else "info",
        "title": "Fiabilidad y supuestos",
        "text": " ".join(caveats),
    })
    return out
