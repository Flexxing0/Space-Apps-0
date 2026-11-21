"""Reconstruye el catálogo argentino usando exclusivamente respuestas GeoRef."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import unicodedata

import requests


GEOREF_URL = "https://apis.datos.gob.ar/georef/api/localidades-censales"
CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "cities.json"

# Selección y regiones definidas por Patagonia Prime, no una división de GeoRef.
# Los IDs de EarthLens son independientes del nombre/ID de la fuente oficial.
CITY_SPECS = [
    ("comodoro-rivadavia", "Comodoro Rivadavia", "Chubut", "Patagonia", ()),
    ("puerto-madryn", "Puerto Madryn", "Chubut", "Patagonia", ()),
    ("trelew", "Trelew", "Chubut", "Patagonia", ()),
    ("rio-gallegos", "Río Gallegos", "Santa Cruz", "Patagonia", ()),
    ("ushuaia", "Ushuaia", "Tierra del Fuego", "Patagonia", ()),
    ("bariloche", "Bariloche", "Río Negro", "Patagonia", ("San Carlos de Bariloche",)),
    ("neuquen", "Neuquén", "Neuquén", "Patagonia", ()),
    ("buenos-aires", "Buenos Aires", "Ciudad Autónoma de Buenos Aires", "Centro y región pampeana", ("Ciudad Autónoma de Buenos Aires",)),
    ("la-plata", "La Plata", "Buenos Aires", "Centro y región pampeana", ()),
    ("mar-del-plata", "Mar del Plata", "Buenos Aires", "Centro y región pampeana", ()),
    ("bahia-blanca", "Bahía Blanca", "Buenos Aires", "Centro y región pampeana", ()),
    ("rosario", "Rosario", "Santa Fe", "Centro y región pampeana", ()),
    ("cordoba", "Córdoba", "Córdoba", "Centro y región pampeana", ()),
    ("santa-fe", "Santa Fe", "Santa Fe", "Centro y región pampeana", ("Santa Fe de la Vera Cruz",)),
    ("mendoza", "Mendoza", "Mendoza", "Cuyo", ("Ciudad de Mendoza",)),
    ("san-juan", "San Juan", "San Juan", "Cuyo", ()),
    ("san-luis", "San Luis", "San Luis", "Cuyo", ()),
    ("salta", "Salta", "Salta", "NOA", ()),
    ("san-salvador-de-jujuy", "San Salvador de Jujuy", "Jujuy", "NOA", ()),
    ("san-miguel-de-tucuman", "San Miguel de Tucumán", "Tucumán", "NOA", ()),
    ("santiago-del-estero", "Santiago del Estero", "Santiago del Estero", "NOA", ()),
    ("posadas", "Posadas", "Misiones", "NEA", ()),
    ("corrientes", "Corrientes", "Corrientes", "NEA", ()),
    ("resistencia", "Resistencia", "Chaco", "NEA", ()),
    ("formosa", "Formosa", "Formosa", "NEA", ()),
]


def normalized_name(value):
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    ).strip()


def build_catalog(*, check_only=False, output=CATALOG_PATH):
    queries = [
        {"nombre": aliases[0] if city_id == "buenos-aires" else name,
         "provincia": province, "max": 50}
        for city_id, name, province, region, aliases in CITY_SPECS
    ]
    response = requests.post(
        GEOREF_URL, json={"localidades_censales": queries}, timeout=60,
    )
    response.raise_for_status()
    responses = response.json()["resultados"]
    if len(responses) != len(CITY_SPECS):
        raise ValueError("GeoRef no devolvió todas las consultas")

    fetched_at = datetime.now(timezone.utc).isoformat()
    cities = []
    unresolved = []
    for spec, query, result in zip(CITY_SPECS, queries, responses):
        city_id, name, province, region, aliases = spec
        candidates = result.get("localidades_censales", [])
        names = {normalized_name(value) for value in (name, *aliases)}
        matches = [record for record in candidates if normalized_name(record["nombre"]) in names]
        if len(matches) != 1:
            unresolved.append({"id": city_id, "query": query, "response": result})
            continue
        record = matches[0]
        actual_province = normalized_name(record["provincia"]["nombre"])
        expected_province = normalized_name(province)
        if (actual_province != expected_province
                and not (expected_province == "tierra del fuego" and actual_province.startswith("tierra del fuego,"))):
            unresolved.append({"id": city_id, "query": query, "response": result})
            continue
        city = {
            "id": city_id,
            "name": name,
            "province": record["provincia"]["nombre"],
            "province_id": record["provincia"]["id"],
            "region": region,
            "country": "Argentina",
            "country_code": "AR",
            "latitude": record["centroide"]["lat"],
            "longitude": record["centroide"]["lon"],
            "coordinate_source": {
                "name": "GeoRef Argentina",
                "url": GEOREF_URL,
                "method": "POST",
                "query": query,
                "entity": "localidades_censales",
                "entity_id": record["id"],
                "coordinate_field": "centroide",
                "retrieved_at": fetched_at,
                "record": record,
            },
        }
        cities.append(city)
        print(json.dumps({key: city[key] for key in ("id", "province", "latitude", "longitude")}, ensure_ascii=True))

    if unresolved:
        raise ValueError("Selecciones GeoRef sin resolver: " + json.dumps(unresolved, ensure_ascii=True))

    catalog = {
        "schema_version": 1,
        "country": "Argentina",
        "country_code": "AR",
        "region_definition": "Agrupación del proyecto EarthLens definida por Patagonia Prime",
        "generated_at": fetched_at,
        "cities": cities,
    }
    from services.providers.cache import write_json_atomic
    from services.geography.cities import validate_catalog

    validate_catalog(catalog)
    if not check_only:
        write_json_atomic(Path(output), catalog)
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Consultar y mostrar sin escribir el catálogo")
    parser.add_argument("--output", type=Path, default=CATALOG_PATH)
    args = parser.parse_args()
    build_catalog(check_only=args.check_only, output=args.output)


if __name__ == "__main__":
    main()
