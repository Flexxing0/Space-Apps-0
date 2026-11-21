"""Conecta las misiones existentes con el catálogo territorial y método activos."""

from urllib.parse import urlencode

from services.science import guided_missions
from services.science.analysis_service import METHOD
from services.api_service import ServiceError
from services.providers.power import VARIABLES


MISSION_CITIES = {
    "patagonia-cambiante": ["comodoro-rivadavia"],
    "en-busca-del-agua": ["mendoza"],
    "misterio-del-viento": ["comodoro-rivadavia", "buenos-aires"],
}


def variable_info(code):
    original = guided_missions.get_variable(code)
    return {"code": code, "name": VARIABLES[code]["name"],
            "short_name": original["short_name"], "power_unit": VARIABLES[code]["unit"],
            "source": "NASA POWER", "description": original["description"],
            "notes": "Las consultas actuales conservan unidades y usan medias aritméticas anuales de meses válidos; no son acumulados ni mediciones de estaciones."}


def catalog():
    return {"variables": [variable_info(code) for code in VARIABLES],
            "phenomena": guided_missions.list_phenomena(), "method": METHOD}


def mission_detail(mission_id, data_service):
    original = guided_missions.get_mission(mission_id)
    if original is None:
        return None
    ids = MISSION_CITIES[mission_id]
    locations = [data_service.get_city(city_id) for city_id in ids]
    params = {"variable": original["variable"], "start_year": original["start_year"],
              "end_year": original["end_year"], "mission": mission_id}
    if original["mode"] == "compare":
        path = "/compare"
        params.update(city_id_a=ids[0], city_id_b=ids[1])
    else:
        path = "/explorer"
        params["city_id"] = ids[0]
    return {**original, "locations": locations, "variable_info": variable_info(original["variable"]),
            "supporting_variables_info": [variable_info(code) for code in original.get("supporting_variables", [])],
            "explorer_url": path + "?" + urlencode(params), "method": METHOD,
            "caveats": [*original["caveats"], *METHOD["limitations"]]}


def recommendations(phenomenon):
    if not isinstance(phenomenon, str) or not phenomenon.strip():
        raise ServiceError("invalid_request", "Seleccionar un fenómeno.")
    return {"phenomenon": phenomenon,
            "variables": [variable_info(row["code"]) for row in guided_missions.recommend_variables(phenomenon)]}
