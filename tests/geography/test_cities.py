"""Integridad del catálogo real y validaciones con mutaciones sintéticas."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from services.geography.cities import get_city, list_cities, load_catalog, validate_catalog


class CitiesTests(unittest.TestCase):
    def test_requested_25_argentine_cities_and_regions(self):
        cities = list_cities()
        expected = {
            "comodoro-rivadavia", "puerto-madryn", "trelew", "rio-gallegos", "ushuaia", "bariloche", "neuquen",
            "buenos-aires", "la-plata", "mar-del-plata", "bahia-blanca", "rosario", "cordoba", "santa-fe",
            "mendoza", "san-juan", "san-luis", "salta", "san-salvador-de-jujuy", "san-miguel-de-tucuman",
            "santiago-del-estero", "posadas", "corrientes", "resistencia", "formosa",
        }
        self.assertEqual({city["id"] for city in cities}, expected)
        self.assertEqual(len(cities), 25)
        for city in cities:
            self.assertEqual(city["country"], "Argentina")
            self.assertEqual(city["country_code"], "AR")
            source = city["coordinate_source"]
            self.assertEqual(source["record"]["centroide"], {"lat": city["latitude"], "lon": city["longitude"]})
        for region, count in (("Patagonia", 7), ("centro-pampeana", 7), ("Cuyo", 3), ("NOA", 4), ("NEA", 4)):
            self.assertEqual(len(list_cities(region=region)), count)

    def test_lookup_and_isolated_return_values(self):
        for identifier, province in (("comodoro-rivadavia", "Chubut"), ("mendoza", "Mendoza"), ("posadas", "Misiones")):
            self.assertEqual(get_city(identifier)["province"], province)
        self.assertIsNone(get_city("not-found"))
        get_city("mendoza")["name"] = "Changed in test"
        self.assertEqual(get_city("mendoza")["name"], "Mendoza")

    def test_province_and_region_filters(self):
        self.assertEqual(len(list_cities(province="Chubut")), 3)
        self.assertEqual(len(list_cities(province="26")), 3)
        self.assertEqual(len(list_cities(province="Buenos Aires")), 3)
        self.assertEqual(list_cities(province="CABA")[0]["id"], "buenos-aires")
        self.assertEqual(list_cities(province="Tierra del Fuego")[0]["id"], "ushuaia")
        self.assertEqual(list_cities(province="rio negro", region="PATAGONIA")[0]["id"], "bariloche")
        self.assertEqual(list_cities(province="Misiones", region="Cuyo"), [])
        self.assertEqual(list_cities(region="not-found"), [])
        with self.assertRaises(ValueError):
            list_cities(region="")

    def test_invalid_catalogs_are_rejected(self):
        original = load_catalog()
        mutations = (
            lambda data: data["cities"].append(deepcopy(data["cities"][0])),
            lambda data: data["cities"][0].update(country="Other", country_code="XX"),
            lambda data: data["cities"][0].update(latitude=float("nan")),
            lambda data: data["cities"][0].update(longitude=181),
            lambda data: data["cities"][0].update(latitude=True),
            lambda data: data["cities"][0].update(province="Other"),
            lambda data: data["cities"][0].update(coordinate_source={}),
            lambda data: data["cities"][0]["coordinate_source"].update(entity_id="Other"),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                catalog = deepcopy(original)
                mutate(catalog)
                with self.assertRaises(ValueError):
                    validate_catalog(catalog)

    def test_catalog_size_is_not_hardcoded_in_loader(self):
        catalog = load_catalog()
        catalog["cities"] = catalog["cities"][:3]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cities.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            self.assertEqual(len(list_cities(catalog_path=path)), 3)


if __name__ == "__main__":
    unittest.main()
