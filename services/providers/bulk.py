"""Obtención secuencial y caché de las seis variables POWER para Argentina."""

from datetime import datetime, timezone
import math
import time

from services.providers.cache import JsonCache, parse_timestamp, utc_now
from services.geography.cities import CATALOG_PATH, list_cities
from services.geography.geography import validate_argentina_location, validate_coordinates
from services.providers import power


DEFAULT_START_YEAR = 2000
DEFAULT_END_YEAR = 2024


class IncompletePowerResponse(ValueError):
    pass


class CacheUnavailable(ValueError):
    """No hay una copia válida y vigente para una lectura sin red."""


def validate_period(start_year, end_year):
    if (type(start_year) is not int or type(end_year) is not int
            or start_year < 1981 or end_year < start_year):
        raise ValueError("El período debe usar años enteros desde 1981, con inicio <= fin")


def make_query(latitude, longitude, start_year, end_year):
    latitude, longitude = validate_coordinates(latitude, longitude)
    validate_period(start_year, end_year)
    return {
        "provider": "NASA POWER", "dataset": "MERRA-2", "endpoint": power.BASE_URL,
        "community": "AG", "frequency": "monthly",
        "latitude": latitude, "longitude": longitude,
        "start_year": start_year, "end_year": end_year,
        "variables": sorted(power.VARIABLES),
    }


def validate_power_data(data, query):
    """Exige estructura completa; los nulos científicos se conservan y cuentan."""
    if not isinstance(data, dict) or set(data) != set(query["variables"]):
        raise IncompletePowerResponse("NASA POWER no devolvió las seis variables")
    dates = [f"{year}-{month:02d}" for year in range(query["start_year"], query["end_year"] + 1)
             for month in range(1, 13)]
    quality = {}
    for variable in query["variables"]:
        result = data[variable]
        if not isinstance(result, dict):
            raise IncompletePowerResponse(f"Resultado inválido: {variable}")
        for field in ("provider", "dataset", "frequency", "latitude", "longitude", "start_year", "end_year"):
            if result.get(field) != query[field]:
                raise IncompletePowerResponse(f"{variable}: {field} no coincide con la consulta")
        unit = result.get("unit")
        metadata = result.get("metadata")
        if not isinstance(metadata, dict):
            raise IncompletePowerResponse(f"{variable}: faltan metadatos")
        header = metadata.get("header")
        parameter = metadata.get("parameter")
        if (result.get("variable") != variable or not isinstance(unit, str) or not unit.strip()
                or not isinstance(parameter, dict) or parameter.get("units") != unit
                or not isinstance(header, dict) or not isinstance(header.get("sources"), list)
                or not header["sources"] or not all(isinstance(source, str) and source.strip() for source in header["sources"])):
            raise IncompletePowerResponse(f"{variable}: faltan unidades o fuentes originales")
        series = result.get("series")
        if (not isinstance(series, list) or not all(isinstance(point, dict) for point in series)
                or [point.get("date") for point in series] != dates):
            raise IncompletePowerResponse(f"{variable}: faltan meses, hay duplicados o fechas fuera de período")
        missing = 0
        for point in series:
            if "value" not in point:
                raise IncompletePowerResponse(f"{variable}: registro sin valor")
            value = point["value"]
            if value is None:
                missing += 1
            elif (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value == header.get("fill_value", -999)):
                raise IncompletePowerResponse(f"{variable}: valor inválido o relleno sin normalizar")
        if missing == len(dates):
            raise IncompletePowerResponse(f"{variable}: la serie no contiene datos disponibles")
        quality[variable] = {"expected_count": len(dates), "valid_count": len(dates) - missing, "missing_count": missing}
    return quality


def ensure_not_degraded(data, previous):
    for variable, result in data.items():
        for new, old in zip(result["series"], previous[variable]["series"]):
            if old["value"] is not None and new["value"] is None:
                raise IncompletePowerResponse(f"{variable}: la actualización perdería datos válidos en {new['date']}")


def failure(location, error, *, cache_preserved=False, previous_fetched_at=None, warnings=None):
    return {
        "location": location, "status": "error", "origin": None, "data": None,
        "error": {"type": type(error).__name__, "message": str(error)},
        "cache_preserved": cache_preserved, "previous_fetched_at": previous_fetched_at,
        "warnings": warnings or [],
    }


class PowerBulkService:
    def __init__(self, cache=None, *, catalog_path=CATALOG_PATH, request_delay=1.0,
                 max_age_days=None, territory_validator=None):
        for name, value in (("request_delay", request_delay), ("max_age_days", max_age_days)):
            if value is None and name == "max_age_days":
                continue
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} debe ser un número finito no negativo")
        self.cache = cache if cache is not None else JsonCache()
        self.catalog_path = catalog_path
        self.request_delay = request_delay
        self.max_age_days = max_age_days
        self.territory_validator = territory_validator
        self._last_request = None

    def plan_cities(self, *, city_id=None, city_ids=None, province=None, region=None,
                    start_year=DEFAULT_START_YEAR, end_year=DEFAULT_END_YEAR):
        """Resuelve selección y consultas sin acceder a POWER ni escribir cachés."""
        validate_period(start_year, end_year)
        if city_id is not None and city_ids is not None:
            raise ValueError("Usar city_id o city_ids, no ambos")
        if city_id is not None:
            city_ids = [city_id]
        if city_ids is not None:
            if isinstance(city_ids, (str, bytes)):
                raise ValueError("city_ids debe ser una colección de IDs")
            try:
                city_ids = list(city_ids)
            except TypeError as exc:
                raise ValueError("city_ids debe ser una colección de IDs") from exc
            if not city_ids or any(not isinstance(item, str) or not item for item in city_ids):
                raise ValueError("Se requiere al menos un ID de ciudad válido")
            city_ids = list(dict.fromkeys(city_ids))
        cities = list_cities(province=province, region=region, catalog_path=self.catalog_path)
        by_id = {city["id"]: city for city in cities}
        if city_ids is None:
            city_ids = list(by_id)
            if not city_ids:
                raise ValueError("No hay ciudades para los filtros solicitados")
        plans = []
        for identifier in city_ids:
            city = by_id.get(identifier)
            if city is None:
                plans.append({"location": {"id": identifier}, "query": None,
                              "error": f"Ciudad no encontrada en la selección argentina: {identifier}"})
            else:
                plans.append({"location": city, "query": make_query(
                    city["latitude"], city["longitude"], start_year, end_year), "error": None})
        return plans

    def collect_cities(self, *, city_id=None, city_ids=None, province=None, region=None,
                       start_year=DEFAULT_START_YEAR, end_year=DEFAULT_END_YEAR, force=False,
                       cache_only=False):
        if cache_only and force:
            raise ValueError("cache_only no admite force")
        started_at = utc_now()
        plans = self.plan_cities(city_id=city_id, city_ids=city_ids, province=province,
                                 region=region, start_year=start_year, end_year=end_year)
        results = []
        for plan in plans:
            if plan["error"]:
                results.append(failure(plan["location"], ValueError(plan["error"])))
            else:
                results.append(self._collect(plan["location"], plan["query"], force=force, cache_only=cache_only))
        return {
            "started_at": started_at, "finished_at": utc_now(),
            "start_year": start_year, "end_year": end_year,
            "summary": {
                "requested": len(results),
                "succeeded": sum(result["status"] == "ok" for result in results),
                "failed": sum(result["status"] == "error" for result in results),
                "cache_hits": sum(result["origin"] == "cache" for result in results),
                "downloaded": sum(result["origin"] == "nasa_power" for result in results),
            },
            "results": results,
        }

    def collect_city(self, city_id, **kwargs):
        return self.collect_cities(city_id=city_id, **kwargs)["results"][0]

    def collect_location(self, latitude, longitude, *, start_year=DEFAULT_START_YEAR,
                         end_year=DEFAULT_END_YEAR, force=False):
        """Admite cualquier ubicación argentina con un validador territorial real."""
        location = {"latitude": latitude, "longitude": longitude}
        try:
            evidence = validate_argentina_location(latitude, longitude, self.territory_validator)
            location.update(country="Argentina", country_code="AR", territory_validation=evidence)
            query = make_query(latitude, longitude, start_year, end_year)
        except ValueError as exc:
            return failure(location, exc)
        return self._collect(location, query, force=force)

    def _collect(self, location, query, *, force, cache_only=False):
        previous = None
        warnings = []
        try:
            previous = self.cache.read(query)
            if previous is not None:
                quality = validate_power_data(previous["data"], query)
                age = (datetime.now(timezone.utc) - parse_timestamp(previous["fetched_at"])).total_seconds()
                if age < 0:
                    raise ValueError("La fecha de caché está en el futuro")
                fresh = self.max_age_days is None or age < self.max_age_days * 86400
                if not force and fresh:
                    return self._success(location, query, previous, quality, "cache", True, warnings)
        except (OSError, ValueError) as exc:
            previous = None
            warnings.append(f"Caché descartada para lectura: {exc}")

        if cache_only:
            return failure(location, CacheUnavailable("No hay caché válida y vigente para este período"),
                           cache_preserved=previous is not None,
                           previous_fetched_at=previous["fetched_at"] if previous else None)

        try:
            if self._last_request is not None:
                remaining = self.request_delay - (time.monotonic() - self._last_request)
                if remaining > 0:
                    time.sleep(remaining)
            self._last_request = time.monotonic()
            data = power.get_data_multi(
                latitude=query["latitude"], longitude=query["longitude"],
                variables=list(power.VARIABLES), start_year=query["start_year"], end_year=query["end_year"],
            )
            quality = validate_power_data(data, query)
            if previous is not None:
                ensure_not_degraded(data, previous["data"])
            entry = {"data": data, "fetched_at": utc_now()}
            cache_written = True
            try:
                self.cache.write(query, data, entry["fetched_at"], location=location)
            except (OSError, ValueError) as exc:
                cache_written = False
                warnings.append(f"Datos obtenidos, pero no se pudo actualizar la caché: {exc}")
            return self._success(location, query, entry, quality, "nasa_power", cache_written, warnings)
        except Exception as exc:
            # Cada ciudad falla de manera independiente; KeyboardInterrupt se propaga.
            return failure(location, exc, cache_preserved=previous is not None,
                           previous_fetched_at=previous["fetched_at"] if previous else None,
                           warnings=warnings)

    def _success(self, location, query, entry, quality, origin, cache_written, warnings):
        return {
            "location": location, "query": query, "status": "ok", "origin": origin,
            "data": entry["data"], "fetched_at": entry["fetched_at"], "quality": quality,
            "cache_path": str(self.cache.path_for(query)), "cache_written": cache_written,
            "warnings": warnings,
        }
