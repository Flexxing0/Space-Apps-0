"""Adaptación de los servicios existentes al contrato de aplicación de la API."""

from collections import Counter
from datetime import datetime, timezone
import re
from threading import Lock

from services.geography import cities
from services.providers.bulk import DEFAULT_END_YEAR, DEFAULT_START_YEAR, validate_period
from services.providers import power


class ServiceError(Exception):
    """Sólo contiene mensajes y campos explícitamente aptos para el cliente."""

    def __init__(self, code, message, *, details=None, meta=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.meta = meta or {}


def validate_city_id(city_id):
    if not isinstance(city_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", city_id):
        raise ServiceError("invalid_request", "city_id debe ser un ID del catálogo en minúsculas y con guiones.", details={"field": "city_id"})


def validate_data_request(payload):
    if not isinstance(payload, dict):
        raise ServiceError("invalid_request", "El cuerpo JSON debe ser un objeto.")
    if {"latitude", "longitude", "lat", "lon", "coordinates"} & set(payload):
        raise ServiceError("coordinates_not_supported", "Las coordenadas libres no están habilitadas; seleccionar una ciudad argentina del catálogo.")
    if set(payload) - {"city_id", "variables", "start_year", "end_year", "force"}:
        raise ServiceError("invalid_request", "El cuerpo JSON contiene campos no admitidos.")
    validate_city_id(payload.get("city_id"))
    variables = payload.get("variables", list(power.VARIABLES))
    if (not isinstance(variables, list) or not variables
            or any(not isinstance(variable, str) or variable not in power.VARIABLES for variable in variables)):
        raise ServiceError("invalid_request", "variables debe ser una lista no vacía de códigos admitidos.", details={"field": "variables", "allowed": list(power.VARIABLES)})
    start_year = payload.get("start_year", DEFAULT_START_YEAR)
    end_year = payload.get("end_year", DEFAULT_END_YEAR)
    try:
        validate_period(start_year, end_year)
    except ValueError:
        raise ServiceError("invalid_request", "Usar años enteros desde 1981, con start_year <= end_year.", details={"fields": ["start_year", "end_year"]}) from None
    if end_year > datetime.now(timezone.utc).year:
        raise ServiceError("invalid_request", "No se admiten períodos futuros.", details={"field": "end_year"})
    force = payload.get("force", False)
    if type(force) is not bool:
        raise ServiceError("invalid_request", "force debe ser un booleano JSON.", details={"field": "force"})
    return {"city_id": payload["city_id"], "variables": list(dict.fromkeys(variables)),
            "start_year": start_year, "end_year": end_year, "force": force}


def public_provider_error(result):
    error_type = result.get("error", {}).get("type")
    if error_type == "CacheUnavailable":
        code, message = "cache_unavailable", "No hay datos válidos en caché para el período solicitado; preparar los datos con el servicio de obtención."
    elif error_type in {"Timeout", "ConnectTimeout", "ReadTimeout"}:
        code, message = "provider_timeout", "NASA POWER no respondió dentro del tiempo permitido."
    elif error_type in {"ConnectionError", "ProxyError", "SSLError", "RetryError"}:
        code, message = "provider_unavailable", "No se pudo establecer comunicación con NASA POWER."
    elif error_type in {"JSONDecodeError", "IncompletePowerResponse", "ValueError"}:
        code, message = "provider_invalid_response", "NASA POWER no devolvió una respuesta completa y válida para el período solicitado."
    elif error_type in {"HTTPError", "RequestException", "TooManyRedirects", "ChunkedEncodingError", "ContentDecodingError"}:
        code, message = "provider_error", "No se pudieron obtener los datos de NASA POWER."
    else:
        code, message = "internal_error", "No se pudo procesar la solicitud."
    meta = {"cache_preserved": result.get("cache_preserved") is True}
    if meta["cache_preserved"]:
        meta["previous_fetched_at"] = result.get("previous_fetched_at")
    # Nunca enviar error.message, warnings o cache_path del servicio interno.
    return ServiceError(code, message, meta=meta)


class EarthLensService:
    def __init__(self, bulk):
        self.bulk = bulk
        # Evita descargas duplicadas y escrituras simultáneas desde esta app.
        # La coordinación es dentro del proceso, no entre múltiples workers.
        self._data_lock = Lock()

    def list_variables(self):
        return [{"code": code, "name": metadata["name"], "unit": metadata["unit"],
                 "provider": "NASA POWER", "dataset": "MERRA-2", "frequency": "monthly",
                 "sources": [{"name": "NASA POWER", "url": power.BASE_URL}]}
                for code, metadata in power.VARIABLES.items()]

    def list_cities(self, province=None, region=None):
        return cities.list_cities(province=province, region=region, catalog_path=self.bulk.catalog_path)

    def get_city(self, city_id):
        validate_city_id(city_id)
        city = cities.get_city(city_id, catalog_path=self.bulk.catalog_path)
        if city is None:
            raise ServiceError("city_not_found", "La ciudad solicitada no existe en el catálogo argentino.")
        return city

    def list_regions(self):
        counts = Counter(city["region"] for city in self.list_cities())
        return [{"name": name, "city_count": count} for name, count in counts.items()]

    def get_data(self, payload, *, cache_only=False):
        selection = validate_data_request(payload)
        self.get_city(selection["city_id"])
        with self._data_lock:
            result = self.bulk.collect_city(
                selection["city_id"], start_year=selection["start_year"],
                end_year=selection["end_year"], force=selection["force"], cache_only=cache_only,
            )
        if result["status"] != "ok":
            raise public_provider_error(result)
        variables = selection["variables"]
        warnings = []
        if result["warnings"]:
            if not result["cache_written"]:
                warnings.append({"code": "cache_write_failed", "message": "Los datos se obtuvieron, pero no se pudieron guardar en caché."})
            else:
                warnings.append({"code": "cache_recovered", "message": "La copia local no pudo reutilizarse; se obtuvieron datos del proveedor."})
        data = {
            "city": result["location"], "provider": "NASA POWER", "dataset": "MERRA-2",
            "frequency": "monthly", "start_year": selection["start_year"], "end_year": selection["end_year"],
            "variables": {variable: result["data"][variable] for variable in variables},
        }
        meta = {
            "origin": result["origin"], "fetched_at": result["fetched_at"],
            "requested_variables": variables,
            "quality": {variable: result["quality"][variable] for variable in variables},
            "cache_available": result["cache_written"], "warnings": warnings,
        }
        return data, meta
