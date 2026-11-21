"""Catálogo de variables, fuentes y misiones del Modo detective.

Responsable: Persona 5 (feature/datasets-missions).

Este módulo no depende de Flask: solo lee data/variables.json y
data/missions.json y ofrece funciones puras que pueden usar las rutas
(routes/missions_routes.py), el backend (services/power.py) y las pruebas.
"""

from __future__ import annotations

import calendar
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

POWER_FILL_VALUE = -999.0
SIGNIFICANCE_LEVEL = 0.05


# --------------------------------------------------------------------------
# Carga de catálogos
# --------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def variables_catalog() -> dict:
    """Catálogo completo: variables, fenómenos y fuentes."""
    data = _load("mission_variables.json")
    return {k: v for k, v in data.items() if not k.startswith("_")}


def list_variables() -> list[dict]:
    return variables_catalog()["variables"]


def get_variable(code: str) -> dict | None:
    code = (code or "").upper()
    return next((v for v in list_variables() if v["code"] == code), None)


def is_supported_variable(code: str) -> bool:
    return get_variable(code) is not None


def list_sources() -> list[dict]:
    return variables_catalog()["sources"]


# --------------------------------------------------------------------------
# Recomendador de variables por fenómeno
# --------------------------------------------------------------------------

def list_phenomena() -> list[dict]:
    return variables_catalog()["phenomena"]


def recommend_variables(phenomenon: str) -> list[dict]:
    """Variables sugeridas para un fenómeno, en orden de relevancia.

    Primero se usa la lista curada de `phenomena`; si el id no existe,
    se buscan variables cuyo campo `phenomena` lo contenga.
    """
    key = (phenomenon or "").strip().lower()
    curated = next((p for p in list_phenomena() if p["id"] == key), None)
    if curated:
        return [get_variable(c) for c in curated["variables"] if get_variable(c)]
    return [v for v in list_variables() if key in v.get("phenomena", [])]


# --------------------------------------------------------------------------
# Misiones
# --------------------------------------------------------------------------

def _missions_data() -> dict:
    return _load("guided_missions.json")


def list_hypotheses() -> list[dict]:
    return _missions_data()["hypotheses"]


def list_missions() -> list[dict]:
    """Resumen de cada misión (para las tarjetas del listado)."""
    fields = ("id", "number", "title", "question", "difficulty", "mode",
              "variable", "image")
    return [{k: m[k] for k in fields if k in m} for m in _missions_data()["missions"]]


def get_mission(mission_id: str) -> dict | None:
    """Detalle completo de una misión, con la variable expandida y el link al explorador."""
    mission = next((m for m in _missions_data()["missions"] if m["id"] == mission_id), None)
    if mission is None:
        return None
    detail = dict(mission)
    detail["variable_info"] = get_variable(mission["variable"])
    detail["supporting_variables_info"] = [
        get_variable(c) for c in mission.get("supporting_variables", []) if get_variable(c)
    ]
    detail["hypotheses"] = list_hypotheses()
    detail["explorer_url"] = mission_target_url(mission)
    return detail


def mission_target_url(mission: dict, hypothesis: str | None = None) -> str:
    """URL del explorador o comparador con los parámetros de la misión precargados.

    Explorador: /explorer?lat=..&lon=..&variable=..&start=..&end=..&mission=..
    Comparador: /compare?lat1=..&lon1=..&lat2=..&lon2=..&variable=..&start=..&end=..&mission=..
    """
    locs = mission["locations"]
    params: dict = {}
    if mission.get("mode") == "compare" and len(locs) >= 2:
        path = "/compare"
        for i, loc in enumerate(locs[:2], start=1):
            params[f"lat{i}"] = loc["latitude"]
            params[f"lon{i}"] = loc["longitude"]
    else:
        path = "/explorer"
        params["lat"] = locs[0]["latitude"]
        params["lon"] = locs[0]["longitude"]
    params.update({
        "variable": mission["variable"],
        "start": mission["start_year"],
        "end": mission["end_year"],
        "mission": mission["id"],
    })
    if hypothesis:
        params["hypothesis"] = hypothesis
    return f"{path}?{urlencode(params)}"


def evaluate_hypothesis(hypothesis: str, statistics: dict) -> dict:
    """Contrasta la hipótesis del usuario con el resultado estadístico.

    `statistics` sigue el contrato de /api/analyze
    (direction, significant, p_value, change_per_decade).
    Devuelve {"verdict": supported|contradicted|inconclusive, "message": str}.
    """
    significant = bool(statistics.get("significant"))
    direction = statistics.get("direction")
    p = statistics.get("p_value")
    p_txt = f" (p = {p:.3f})" if isinstance(p, (int, float)) else ""

    if not significant:
        if hypothesis == "no_clear_trend":
            return {
                "verdict": "supported",
                "message": "Los datos no muestran una tendencia significativa"
                           f"{p_txt}, como suponías. Ojo: eso no demuestra que no haya "
                           "cambio, solo que la evidencia no alcanza para afirmarlo.",
            }
        return {
            "verdict": "inconclusive",
            "message": "La tendencia no es estadísticamente significativa"
                       f"{p_txt}. No hay evidencia suficiente para confirmar ni "
                       "descartar tu hipótesis. Probá con un período más largo.",
        }

    if hypothesis == direction:
        return {
            "verdict": "supported",
            "message": f"La evidencia apoya tu hipótesis: hay una tendencia significativa{p_txt}.",
        }
    if hypothesis == "no_clear_trend":
        return {
            "verdict": "contradicted",
            "message": f"Los datos sí muestran una tendencia significativa{p_txt}, "
                       "aunque suponías que no habría un cambio claro.",
        }
    return {
        "verdict": "contradicted",
        "message": f"La evidencia contradice tu hipótesis: la tendencia significativa{p_txt} "
                   "va en la dirección opuesta.",
    }


# --------------------------------------------------------------------------
# Agregación anual de referencia (endpoint mensual de NASA POWER)
# --------------------------------------------------------------------------

def annual_series_from_power_monthly(payload: dict, code: str,
                                     min_valid_months: int = 12) -> list[dict]:
    """Construye la serie anual de una variable a partir de la respuesta del
    endpoint mensual de POWER (/api/temporal/monthly/point).

    Reglas (según `annual_aggregation` del catálogo):
      mean -> promedio de los 12 meses ponderado por días
      sum  -> suma de (mm/día × días del mes)  => mm/año
      max  -> máximo de los meses   (T2M_MAX ya es el extremo mensual)
      min  -> mínimo de los meses   (T2M_MIN ya es el extremo mensual)

    Se ignora la clave AAAA13 (anual de POWER) para no mezclar criterios.
    Un año con menos de `min_valid_months` meses válidos se descarta.
    """
    var = get_variable(code)
    if var is None:
        raise ValueError(f"Variable no soportada: {code}")
    raw = payload["properties"]["parameter"][var["code"]]
    fill = payload.get("header", {}).get("fill_value", POWER_FILL_VALUE)
    lo, hi = var["valid_range"]

    by_year: dict[int, list[tuple[int, float]]] = {}
    for key, value in raw.items():
        year, month = int(key[:4]), int(key[4:])
        if month == 13 or value is None or value == fill or not lo <= value <= hi:
            continue
        by_year.setdefault(year, []).append((month, float(value)))

    agg = var["annual_aggregation"]
    series = []
    for year in sorted(by_year):
        months = by_year[year]
        if len(months) < min_valid_months:
            continue
        days = [calendar.monthrange(year, m)[1] for m, _ in months]
        values = [v for _, v in months]
        if agg == "sum":
            value = sum(v * d for v, d in zip(values, days))
        elif agg == "max":
            value = max(values)
        elif agg == "min":
            value = min(values)
        else:
            value = sum(v * d for v, d in zip(values, days)) / sum(days)
        series.append({"year": year, "value": round(value, 3)})
    return series
