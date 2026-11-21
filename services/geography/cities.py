"""Catálogo local extensible de localidades argentinas verificadas con GeoRef."""

import json
from pathlib import Path
import re
import unicodedata

from services.geography.geography import validate_coordinates


CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "cities.json"
GEOREF_URL = "https://apis.datos.gob.ar/georef/api/localidades-censales"
REGIONS = ("Patagonia", "Centro y región pampeana", "Cuyo", "NOA", "NEA")


def normalize_label(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("El filtro debe ser un texto no vacío")
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold().strip())
        if not unicodedata.combining(char)
    )


def validate_catalog(catalog):
    if (not isinstance(catalog, dict) or catalog.get("schema_version") != 1
            or catalog.get("country_code") != "AR" or catalog.get("country") != "Argentina"
            or not isinstance(catalog.get("cities"), list) or not catalog["cities"]):
        raise ValueError("Catálogo argentino inválido")
    identifiers = set()
    for city in catalog["cities"]:
        if not isinstance(city, dict):
            raise ValueError("Registro de ciudad inválido")
        city_id = city.get("id")
        if (not isinstance(city_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", city_id)
                or city_id in identifiers):
            raise ValueError("Los IDs deben ser únicos, estables y usar minúsculas ASCII y guiones")
        identifiers.add(city_id)
        for field in ("name", "province", "province_id"):
            if not isinstance(city.get(field), str) or not city[field].strip():
                raise ValueError(f"Falta {field} en {city_id}")
        if (city.get("country") != "Argentina" or city.get("country_code") != "AR"
                or city.get("region") not in REGIONS):
            raise ValueError(f"La ciudad {city_id} debe pertenecer al catálogo argentino")
        latitude, longitude = validate_coordinates(city.get("latitude"), city.get("longitude"))
        source = city.get("coordinate_source")
        if (not isinstance(source, dict) or source.get("url") != GEOREF_URL
                or source.get("coordinate_field") != "centroide"
                or not source.get("retrieved_at")):
            raise ValueError(f"Falta procedencia GeoRef para {city_id}")
        record = source.get("record", {})
        if (not isinstance(record, dict) or not record.get("id")
                or record.get("id") != source.get("entity_id")
                or record.get("centroide") != {"lat": latitude, "lon": longitude}
                or record.get("provincia") != {"id": city["province_id"], "nombre": city["province"]}):
            raise ValueError(f"Los datos de {city_id} no coinciden con su registro GeoRef")
    return catalog


def load_catalog(catalog_path=CATALOG_PATH):
    with Path(catalog_path).open(encoding="utf-8") as stream:
        return validate_catalog(json.load(stream))


def list_cities(province=None, region=None, *, catalog_path=CATALOG_PATH):
    """Lista o filtra por provincia/ID provincial y región; ignora tildes y caso."""
    cities = load_catalog(catalog_path)["cities"]
    return filter_cities(cities, province=province, region=region)


def filter_cities(cities, province=None, region=None):
    """Aplica los mismos filtros a un catálogo ya leído o al snapshot de un estudio."""
    if province is not None:
        value = normalize_label(province)
        value = {
            "caba": "ciudad autonoma de buenos aires",
            "tierra del fuego": "tierra del fuego, antartida e islas del atlantico sur",
        }.get(value, value)
        cities = [city for city in cities
                  if value in (normalize_label(city["province"]), city["province_id"])]
    if region is not None:
        value = normalize_label(region)
        value = {"centro-pampeana": "centro y region pampeana"}.get(value, value)
        cities = [city for city in cities if normalize_label(city["region"]) == value]
    return cities


def get_city(city_id, *, catalog_path=CATALOG_PATH):
    """Devuelve un registro nuevo por ID exacto o None si no existe."""
    return next((city for city in list_cities(catalog_path=catalog_path)
                 if city["id"] == city_id), None)
