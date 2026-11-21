"""Contratos integrados con NASA simulada y caché temporal; datos sintéticos."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from app import create_app
from services.science import trend_analysis as engine
from tests.providers.test_bulk import synthetic_payload


class WebIntegrationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.client = create_app({"TESTING": True, "CACHE_DIR": Path(directory.name),
                                  "POWER_REQUEST_DELAY": 0}).test_client()
        self.mutate = None

        def respond(url, *, params, timeout):
            payload = synthetic_payload(params)
            if self.mutate:
                self.mutate(payload)
            return Mock(json=Mock(return_value=payload))

        patcher = patch("services.providers.power.requests.get", side_effect=respond)
        self.network = patcher.start()
        self.addCleanup(patcher.stop)

    def test_all_pages_render_and_assets_are_served_without_network(self):
        for page in ("/", "/index.html", "/explorer", "/explorer.html", "/results", "/results.html",
                     "/compare", "/compare.html", "/missions", "/about"):
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "text/html")
                self.assertNotIn(b"{%", response.data)
        for asset in ("shared/api.js", "exploration/index.js", "exploration/explorer.js", "shared/map.js",
                      "exploration/results.js", "exploration/compare.js", "shared/charts.js"):
            with self.client.get("/static/js/" + asset) as response:
                self.assertEqual(response.status_code, 200)
        self.network.assert_not_called()

    def test_missions_available_and_unknown_mission_is_safe(self):
        missions = self.client.get("/api/missions").get_json()["data"]
        self.assertEqual(len(missions), 3)
        self.assertEqual(self.client.get("/api/missions/" + missions[0]["id"]).status_code, 200)
        self.assertEqual(self.client.get("/api/missions/unknown").status_code, 404)
        self.network.assert_not_called()

    def test_guided_missions_and_recommendations_use_active_catalog_and_units(self):
        detail = self.client.get("/api/missions/en-busca-del-agua").get_json()["data"]
        self.assertEqual(detail["locations"][0]["id"], "mendoza")
        self.assertIn("city_id=mendoza", detail["explorer_url"])
        self.assertNotIn("lat=", detail["explorer_url"])
        self.assertEqual(detail["variable_info"]["power_unit"], "mm/day")
        wind = self.client.get("/api/missions/misterio-del-viento").get_json()["data"]
        self.assertIn("city_id_b=buenos-aires", wind["explorer_url"])
        catalog = self.client.get("/api/catalog").get_json()["data"]
        self.assertEqual(len(catalog["variables"]), 6)
        recommended = self.client.get("/api/variables/recommend?phenomenon=sequia").get_json()["data"]
        self.assertEqual(recommended["variables"][0]["code"], "PRECTOTCORR")
        self.assertEqual(self.client.get("/api/variables/recommend").status_code, 400)
        self.network.assert_not_called()

    def test_invalid_analysis_requests_and_free_coordinates_never_access_nasa(self):
        for body in (None, [], {}, {"city_id": "unknown"}, {"city_id": "mendoza", "latitude": -33},
                     {"city_id": "mendoza", "variable": "INVALID"}, {"city_id": "mendoza", "force": True},
                     {"city_id": "mendoza", "start_year": 2024}, {"city_id": "mendoza", "start_year": True}):
            with self.subTest(body=body):
                self.assertIn(self.client.post("/api/analyze", json=body).status_code, (400, 404, 415))
        self.assertEqual(self.client.get("/api/summary?lat=-33&lon=-68").status_code, 400)
        self.assertEqual(self.client.get("/api/summary?city_id=mendoza&start_year=bad").status_code, 400)
        self.assertEqual(self.client.post("/api/compare", json={"city_id_a": "mendoza", "city_id_b": "unknown"}).status_code, 404)
        self.network.assert_not_called()

    @unittest.skipUnless(engine.HAS_SCIPY, "SciPy requerido; verificar dentro de Docker")
    def test_analysis_uses_existing_monthly_cache_and_real_engine_contract(self):
        monthly = self.client.post("/api/data", json={"city_id": "mendoza"}).get_json()
        response = self.client.post("/api/analyze", json={"city_id": "mendoza", "variable": "PRECTOTCORR"})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        result = body["data"]
        self.assertFalse(result["is_mock"])
        self.assertEqual(result["unit"], "mm/day")
        self.assertEqual(len(result["series"]), 25)
        self.assertEqual(body["meta"]["origin"], "cache")
        self.assertEqual(body["meta"]["fetched_at"], monthly["meta"]["fetched_at"])
        self.assertEqual(result["metadata"], monthly["data"]["variables"]["PRECTOTCORR"]["metadata"])
        self.assertEqual(result["completeness"]["coverage_ratio"], 1)
        self.assertIn("confidence_interval_95", result["statistics"])
        self.assertGreater(result["statistics"]["t_critical_95"], 1.96)
        self.assertEqual(self.network.call_count, 1)

    @unittest.skipUnless(engine.HAS_SCIPY, "SciPy requerido; verificar dentro de Docker")
    def test_summary_fetches_once_for_all_six_variables(self):
        response = self.client.get("/api/summary?city_id=mendoza")
        self.assertEqual(response.status_code, 200)
        result = response.get_json()["data"]
        self.assertEqual(len(result["estimations"]), 6)
        self.assertTrue(all(len(item["series"]) == 25 for item in result["estimations"].values()))
        self.assertEqual(self.network.call_count, 1)

    @unittest.skipUnless(engine.HAS_SCIPY, "SciPy requerido; verificar dentro de Docker")
    def test_incomplete_annual_coverage_returns_422_without_fake_results(self):
        def missing(payload):
            values = payload["properties"]["parameter"]["T2M"]
            for key in values:
                if int(key[:4]) < 2022:
                    values[key] = -999
        self.mutate = missing
        response = self.client.post("/api/analyze", json={"city_id": "mendoza"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["code"], "insufficient_data")
        self.assertNotIn("statistics", response.get_json())

    @unittest.skipUnless(engine.HAS_SCIPY, "SciPy requerido; verificar dentro de Docker")
    def test_comparison_requires_compatible_annual_coverage(self):
        def missing(payload):
            if payload["geometry"]["coordinates"][0] < -68:
                payload["properties"]["parameter"]["T2M"]["200001"] = -999
                for month in range(2, 6):
                    payload["properties"]["parameter"]["T2M"][f"2000{month:02d}"] = -999
        self.mutate = missing
        response = self.client.post("/api/compare", json={"city_id_a": "mendoza", "city_id_b": "comodoro-rivadavia"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["code"], "incompatible_analysis")

    @unittest.skipUnless(engine.HAS_SCIPY, "SciPy requerido; verificar dentro de Docker")
    def test_provider_failure_is_reported_without_fallback_or_raw_exception(self):
        self.network.side_effect = requests.Timeout("SECRET")
        response = self.client.post("/api/analyze", json={"city_id": "mendoza"})
        self.assertEqual(response.status_code, 504)
        self.assertNotIn(b"SECRET", response.data)
        self.assertNotIn(b"statistics", response.data)

    def test_missing_scipy_returns_service_error_without_approximate_results(self):
        with patch.object(engine, "HAS_SCIPY", False):
            response = self.client.post("/api/analyze", json={"city_id": "mendoza"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "analysis_unavailable")
