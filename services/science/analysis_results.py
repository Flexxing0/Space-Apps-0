"""Contrato común de producto; no calcula ni reemplaza estadísticas del motor."""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
from urllib.parse import urlencode

from services.science import trend_analysis as engine
from services.providers.cache import utc_now


SCHEMA_VERSION = "earthlens.analysis.v1"
METHOD_VERSION = "earthlens.power.annual-ols.provisional.v1"
RESULT_STATUSES = ("valid", "insufficient", "provisional", "error")
EVIDENCE_STATUSES = ("provisional_signal", "provisional_no_signal", "provisional_inconsistent",
                     "insufficient_data", "error", "confirmed")
PRIMARY_VARIABLES = ("T2M", "PRECTOTCORR", "RH2M", "WS2M")
EXTREME_VARIABLES = ("T2M_MAX", "T2M_MIN")
INDICATORS = {
    "T2M": {"id": "annual_mean_monthly_temperature", "name": "Media anual de temperaturas mensuales", "group": "primary"},
    "PRECTOTCORR": {"id": "annual_mean_monthly_precipitation_rate", "name": "Tasa media de precipitación; no acumulado anual", "group": "primary"},
    "RH2M": {"id": "annual_mean_monthly_relative_humidity", "name": "Media anual de humedad relativa atmosférica", "group": "primary"},
    "WS2M": {"id": "annual_mean_monthly_wind_speed", "name": "Media anual de velocidad del viento", "group": "primary"},
    "T2M_MAX": {"id": "annual_mean_monthly_temperature_maxima", "name": "Media de máximos mensuales; no máximo absoluto anual", "group": "extreme"},
    "T2M_MIN": {"id": "annual_mean_monthly_temperature_minima", "name": "Media de mínimos mensuales; no mínimo absoluto anual", "group": "extreme"},
}
PENDING_DEPENDENCIES = [
    {"id": "methodology_approval", "status": "pending", "owner": "statistics", "description": "Validación conjunta de indicadores y criterios científicos."},
    {"id": "unrounded_statistics", "status": "pending", "owner": "statistics", "description": "Estadísticas y series con precisión completa entregadas por el motor."},
    {"id": "significance_consistency", "status": "pending", "owner": "statistics", "description": "Revisar slope_tolerance, redondeo y coherencia entre p-valor, significancia y conclusión."},
    {"id": "temporal_inference", "status": "pending", "owner": "statistics", "description": "Autocorrelación, estacionalidad, supuestos OLS y sensibilidad a faltantes."},
    {"id": "coverage_policy", "status": "pending", "owner": "statistics", "description": "Validar mínimos de meses/años y comparabilidad de cobertura estacional."},
    {"id": "multiple_testing", "status": "pending", "owner": "statistics", "description": "Definir familia y ajuste múltiple; no aplicado en esta versión."},
    {"id": "annual_aggregation", "status": "pending", "owner": "statistics", "description": "Acordar ponderación por días y acumulados; esta versión conserva medias y unidades NASA."},
]


def content_hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def methodology():
    try:
        scipy_version = version("scipy")
    except PackageNotFoundError:
        scipy_version = None
    return {
        "version": METHOD_VERSION, "validation_status": "pending", "engine": "services.science.trend_analysis",
        "engine_sha256": sha256(Path(engine.__file__).read_bytes()).hexdigest(), "scipy_version": scipy_version,
        "regression": "OLS", "aggregation": "unweighted_mean_of_valid_months",
        "input_frequency": "monthly", "output_frequency": "annual",
        "min_months_per_year": 9, "min_valid_years": 3, "min_coverage_ratio": 0.70,
        "alpha": 0.05, "confidence_level": 0.95, "slope_tolerance": 1e-5,
        "missing_values": "Sin imputación; se conservan los nulos. El motor excluye -99, -999, -9999 y valores <= -900.",
        "pending_dependencies": deepcopy(PENDING_DEPENDENCIES),
    }


def links(city_id, variable, period):
    query = urlencode({"city_id": city_id, "variable": variable, **period})
    return {"explorer": "/explorer?" + query, "results": "/results?" + query}


def result_counts(records):
    counts = Counter(record["status"] for record in records)
    return {status: counts[status] for status in RESULT_STATUSES}


def coverage_for(row, period, annual=None):
    points = row["series"]
    by_year = []
    for year in range(period["start_year"], period["end_year"] + 1):
        months = [point for point in points if point["date"].startswith(str(year) + "-")]
        valid = sum(point["value"] is not None for point in months)
        usable = sum(engine.is_valid_observation(point["value"]) for point in months)
        by_year.append({"year": year, "expected_months": 12, "available_months": valid,
                        "engine_usable_months": usable,
                        "excluded_months": [point["date"] for point in months if not engine.is_valid_observation(point["value"])],
                        "included_in_annual_series": usable >= 9})
    valid = sum(point["value"] is not None for point in points)
    return {"monthly": {"expected_count": len(points), "valid_count": valid, "missing_count": len(points) - valid},
            "annual": deepcopy(annual), "by_year": by_year}


def make_result(city, variable, period, *, method, row=None, meta=None, analysis=None, error=None,
                unrounded_statistics=None, analyzed_at=None):
    """Conserva la salida del motor. El argumento futuro unrounded_statistics nunca se reconstruye aquí."""
    if unrounded_statistics is not None:
        if analysis is None:
            raise ValueError("Las estadísticas de precisión completa requieren un análisis")
        content_hash(unrounded_statistics)  # Valida JSON finito, sin alterar la precisión recibida.
    statistics = deepcopy(analysis["statistics"]) if analysis else None
    insufficient = error is not None and error.code == "insufficient_data"
    status = "provisional" if analysis else ("insufficient" if insufficient else "error")
    annual = analysis["completeness"] if analysis else (error.details.get("completeness") if error else None)
    issues = []
    if statistics is not None and statistics["significant"] != (statistics["p_value"] < method["alpha"]):
        issues.append("significance_p_value_mismatch")
    evidence_status = ("provisional_inconsistent" if issues else
                       ("provisional_signal" if statistics["significant"] else "provisional_no_signal")) if analysis else (
                           "insufficient_data" if insufficient else "error")
    input_hash = content_hash(row) if row else None
    return {
        "schema_version": SCHEMA_VERSION, "result_id": f"{city['id']}:{variable}",
        "analysis_id": content_hash({"location": city, "variable": variable, "period": period,
                                     "method": method, "input_sha256": input_hash}),
        "variable": variable, "indicator": deepcopy(INDICATORS[variable]), "unit": row["unit"] if row else None,
        "location": deepcopy(city), "period": deepcopy(period),
        "status": status, "data_status": "valid" if analysis else ("insufficient" if insufficient else "error"),
        "evidence": {"status": evidence_status, "confirmed": False, "issues": issues,
                     "adjustment_status": "not_applied", "adjusted_p_value": None},
        "statistics": statistics, "statistics_unrounded": deepcopy(unrounded_statistics),
        "precision": {"statistics": "as_returned_by_engine", "upstream_rounding": "legacy_rounded",
                      "unrounded_available": unrounded_statistics is not None,
                      "unrounded_source": "statistics_engine" if unrounded_statistics is not None else None,
                      "note": "No se agrega redondeo. No reconstruir p-valores ni coeficientes desde la salida redondeada."},
        "direction": statistics["direction"] if statistics else None,
        "series": deepcopy(analysis["series"]) if analysis else [],
        "coverage": coverage_for(row, period, annual) if row else {"monthly": None, "annual": None, "by_year": []},
        "source": {"provider": "NASA POWER", "dataset": "MERRA-2", "metadata": deepcopy(row["metadata"]) if row else None},
        "provenance": {"origin": meta.get("origin") if meta else None, "fetched_at": meta.get("fetched_at") if meta else None,
                       "input_sha256": input_hash},
        "analyzed_at": analyzed_at or utc_now(), "methodology": deepcopy(method),
        "error": {"code": error.code, "message": error.message} if error else None,
        "links": links(city["id"], variable, period),
    }
