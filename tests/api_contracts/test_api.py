"""Cliente Flask con NASA simulada; los valores son datos de prueba únicamente."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from app import create_app
from services.providers.bulk import make_query
from services.geography.cities import get_city
from services.providers.power import BASE_URL, VARIABLES
from tests.providers.test_bulk import synthetic_payload


class ApiTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cache_dir = Path(directory.name) / "cache"
        self.app = create_app({"TESTING": True, "CACHE_DIR": self.cache_dir, "POWER_REQUEST_DELAY": 0,
                               "POWER_CACHE_MAX_AGE_DAYS": None, "MAX_CONTENT_LENGTH": 16384})
        self.client = self.app.test_client()
        self.body = {"city_id": "mendoza", "variables": ["T2M"], "start_year": 2024, "end_year": 2024}
        self.mutate = None
        self.upstream_error = None
        patcher = patch("services.providers.power.requests.get", side_effect=self.respond)
        self.network = patcher.start()
        self.addCleanup(patcher.stop)

    def respond(self, url, *, params, timeout):
        self.assertEqual(url, BASE_URL)
        self.assertEqual(params["parameters"], ",".join(VARIABLES))
        if self.upstream_error is not None:
            raise self.upstream_error
        payload = synthetic_payload(params)
        if self.mutate:
            self.mutate(payload)
        response = Mock()
        response.json.return_value = payload
        return response

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.mimetype, "application/json")
        body = response.get_json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["code"], code)
        self.assertIsInstance(body["error"]["details"], dict)
        self.assertEqual(body["meta"]["api_version"], "1")
        self.assertNotIn("SECRET", response.get_data(as_text=True))
        return body

    def test_factory_isolated_and_without_network_or_cache_creation(self):
        other = create_app({"TESTING": True, "CACHE_DIR": self.cache_dir / "other"})
        self.assertIsNot(other.extensions["earthlens_service"], self.app.extensions["earthlens_service"])
        self.assertFalse(self.cache_dir.exists())
        self.network.assert_not_called()

    def test_health_is_liveness_only(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "status": "ok", "data": {"service": "EarthLens", "status": "up", "country_code": "AR"},
            "meta": {"api_version": "1"},
        })
        self.network.assert_not_called()

    def test_variables_reuse_provider_catalog(self):
        response = self.client.get("/api/variables")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["meta"]["count"], 6)
        self.assertEqual([variable["code"] for variable in body["data"]], list(VARIABLES))
        for variable in body["data"]:
            self.assertEqual(variable["unit"], VARIABLES[variable["code"]]["unit"])
            self.assertEqual(variable["name"], VARIABLES[variable["code"]]["name"])
            self.assertEqual(variable["sources"][0]["url"], BASE_URL)
        self.network.assert_not_called()

    def test_city_catalog_filters_and_no_matches(self):
        response = self.client.get("/api/cities")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["meta"]["count"], 25)
        self.assertTrue(all(city["country_code"] == "AR" for city in response.get_json()["data"]))
        for filters, count in (({"province": "Chubut"}, 3), ({"region": "Cuyo"}, 3),
                               ({"province": "Misiones", "region": "NEA"}, 1),
                               ({"province": "CABA"}, 1), ({"province": "26"}, 3),
                               ({"region": "centro-pampeana"}, 7), ({"province": "rio negro"}, 1),
                               ({"province": "not-found"}, 0)):
            with self.subTest(filters=filters):
                filtered = self.client.get("/api/cities", query_string=filters)
                self.assertEqual(filtered.status_code, 200)
                self.assertEqual(filtered.get_json()["meta"]["count"], count)
                self.assertEqual(filtered.get_json()["meta"]["filters"], filters)
        self.network.assert_not_called()

    def test_city_details_preserve_official_coordinate_source(self):
        response = self.client.get("/api/cities/comodoro-rivadavia")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], get_city("comodoro-rivadavia"))
        self.assert_error(self.client.get("/api/cities/unknown"), 404, "city_not_found")
        self.assert_error(self.client.get("/api/cities/INVALID_ID"), 400, "invalid_request")
        self.network.assert_not_called()

    def test_regions_are_derived_from_catalog(self):
        response = self.client.get("/api/regions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["meta"]["count"], 5)
        self.assertEqual({region["name"]: region["city_count"] for region in response.get_json()["data"]},
                         {"Patagonia": 7, "Centro y región pampeana": 7, "Cuyo": 3, "NOA": 4, "NEA": 4})
        self.network.assert_not_called()

    def test_unknown_empty_and_repeated_query_parameters(self):
        for url in ("/api/cities?region=", "/api/cities?province=Chubut&province=Mendoza",
                    "/api/cities?latitude=-40", "/api/health?debug=true", "/api/regions?country=XX"):
            with self.subTest(url=url):
                self.assert_error(self.client.get(url), 400, "invalid_request")
        self.assert_error(self.client.post("/api/data?force=true", json=self.body), 400, "invalid_request")
        self.network.assert_not_called()

    def test_selected_variables_and_all_six_cached_without_internal_paths(self):
        response = self.client.post("/api/data", json={**self.body, "variables": ["T2M", "RH2M"]})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(set(body["data"]["variables"]), {"T2M", "RH2M"})
        self.assertEqual(body["data"]["city"]["id"], "mendoza")
        self.assertEqual(body["data"]["variables"]["T2M"]["unit"], "C")
        self.assertEqual(body["meta"]["origin"], "nasa_power")
        self.assertEqual(body["meta"]["quality"]["T2M"]["expected_count"], 12)
        self.assertNotIn("cache_path", response.get_data(as_text=True))
        self.assertNotIn(str(self.cache_dir), response.get_data(as_text=True))
        entries = list(self.cache_dir.glob("*.json"))
        self.assertEqual(len(entries), 1)
        cached = json.loads(entries[0].read_text(encoding="utf-8"))
        self.assertEqual(set(cached["data"]), set(VARIABLES))
        self.assertEqual(body["data"]["variables"]["T2M"]["metadata"], cached["data"]["T2M"]["metadata"])
        self.network.assert_called_once()

    def test_cache_is_shared_by_different_variable_subsets(self):
        first = self.client.post("/api/data", json=self.body).get_json()
        paths = list(self.cache_dir.glob("*.json"))
        original = paths[0].read_bytes()
        response = self.client.post("/api/data", json={**self.body, "variables": ["WS2M"]})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["meta"]["origin"], "cache")
        self.assertEqual(body["meta"]["fetched_at"], first["meta"]["fetched_at"])
        self.assertEqual(paths[0].read_bytes(), original)
        self.network.assert_called_once()

    def test_defaults_are_all_variables_and_2000_2024(self):
        response = self.client.post("/api/data", json={"city_id": "posadas"})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(set(body["data"]["variables"]), set(VARIABLES))
        self.assertEqual(body["data"]["start_year"], 2000)
        self.assertEqual(body["data"]["end_year"], 2024)
        self.assertEqual(len(body["data"]["variables"]["T2M"]["series"]), 300)

    def test_duplicate_variable_codes_preserve_requested_order(self):
        response = self.client.post("/api/data", json={**self.body, "variables": ["RH2M", "T2M", "RH2M"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["meta"]["requested_variables"], ["RH2M", "T2M"])

    def test_missing_values_remain_json_null(self):
        self.mutate = lambda payload: payload["properties"]["parameter"]["T2M"].update({"202401": -999})
        response = self.client.post("/api/data", json=self.body)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIsNone(body["data"]["variables"]["T2M"]["series"][0]["value"])
        self.assertEqual(body["meta"]["quality"]["T2M"]["missing_count"], 1)

    def test_request_types_variables_years_and_force_are_validated_before_network(self):
        invalid = [None, [], "text", {}, {**self.body, "city_id": 1}, {**self.body, "city_id": ""},
                   {**self.body, "city_id": "MENDOZA"}, {**self.body, "variables": []},
                   {**self.body, "variables": "T2M"}, {**self.body, "variables": [None]},
                   {**self.body, "variables": [True]}, {**self.body, "variables": [["T2M"]]},
                   {**self.body, "variables": ["UNKNOWN"]}, {**self.body, "variables": ["t2m"]},
                   {**self.body, "start_year": "2000"}, {**self.body, "start_year": True},
                   {**self.body, "start_year": 1980}, {**self.body, "start_year": 2025},
                   {**self.body, "start_year": 2000.0}, {**self.body, "end_year": None},
                   {**self.body, "end_year": 9999}, {**self.body, "force": "false"},
                   {**self.body, "force": 0}, {**self.body, "extra": "not allowed"}]
        for payload in invalid:
            with self.subTest(payload=payload):
                response = self.client.post("/api/data", data=json.dumps(payload), content_type="application/json")
                self.assert_error(response, 400, "invalid_request")
        self.network.assert_not_called()

    def test_unknown_city_and_free_coordinates_never_access_provider(self):
        self.assert_error(self.client.post("/api/data", json={**self.body, "city_id": "unknown"}), 404, "city_not_found")
        for field in ("latitude", "longitude", "lat", "lon", "coordinates"):
            with self.subTest(field=field):
                self.assert_error(self.client.post("/api/data", json={**self.body, field: -40}), 400, "coordinates_not_supported")
        self.assert_error(self.client.post("/api/data", json={"city_ids": ["mendoza"]}), 400, "invalid_request")
        self.network.assert_not_called()

    def test_bad_json_content_type_and_body_size(self):
        self.assert_error(self.client.post("/api/data", data="{}", content_type="text/plain"), 415, "unsupported_media_type")
        for body in ("", "{broken", "{\"city_id\":"):
            self.assert_error(self.client.post("/api/data", data=body, content_type="application/json"), 400, "invalid_request")
        self.assert_error(self.client.post("/api/data", json={"city_id": "x" * 17000}), 413, "request_too_large")
        self.network.assert_not_called()

    def test_provider_errors_map_to_safe_http_responses(self):
        for exception, status, code in (
            (requests.Timeout("SECRET URL with credentials"), 504, "provider_timeout"),
            (requests.ConnectTimeout("SECRET"), 504, "provider_timeout"),
            (requests.ReadTimeout("SECRET"), 504, "provider_timeout"),
            (requests.ConnectionError("SECRET"), 503, "provider_unavailable"),
            (requests.HTTPError("SECRET"), 502, "provider_error"),
            (requests.exceptions.JSONDecodeError("SECRET", "", 0), 502, "provider_invalid_response"),
            (RuntimeError("SECRET internal path"), 500, "internal_error"),
        ):
            with self.subTest(exception=type(exception).__name__):
                self.upstream_error = exception
                self.assert_error(self.client.post("/api/data", json=self.body), status, code)

    def test_incomplete_provider_response_is_not_cached(self):
        self.mutate = lambda payload: payload["properties"]["parameter"].pop("RH2M")
        self.assert_error(self.client.post("/api/data", json=self.body), 502, "provider_invalid_response")
        self.assertFalse(list(self.cache_dir.glob("*.json")))

    def test_force_refresh_and_failed_refresh_preserve_valid_cache(self):
        self.client.post("/api/data", json=self.body)
        self.mutate = lambda payload: payload["properties"]["parameter"]["T2M"].update({"202401": 2.0})
        response = self.client.post("/api/data", json={**self.body, "force": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["variables"]["T2M"]["series"][0]["value"], 2.0)
        path = list(self.cache_dir.glob("*.json"))[0]
        original = path.read_bytes()
        self.upstream_error = requests.Timeout("SECRET")
        body = self.assert_error(self.client.post("/api/data", json={**self.body, "force": True}), 504, "provider_timeout")
        self.assertTrue(body["meta"]["cache_preserved"])
        self.assertEqual(path.read_bytes(), original)
        self.assertIsInstance(body["meta"]["previous_fetched_at"], str)
        self.assertEqual(self.client.post("/api/data", json=self.body).get_json()["meta"]["origin"], "cache")
        self.assertEqual(self.network.call_count, 3)

    def test_cache_recovery_warning_is_safe(self):
        city = get_city("mendoza")
        query = make_query(city["latitude"], city["longitude"], 2024, 2024)
        cache = self.app.extensions["earthlens_service"].bulk.cache
        path = cache.path_for(query)
        path.parent.mkdir(parents=True)
        path.write_text("SECRET corrupted cache", encoding="utf-8")
        response = self.client.post("/api/data", json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["meta"]["warnings"][0]["code"], "cache_recovered")
        self.assertNotIn("SECRET", response.get_data(as_text=True))
        self.assertNotIn("cache_path", response.get_data(as_text=True))

    def test_cache_write_failure_returns_data_with_safe_warning(self):
        with patch("services.providers.cache.os.replace", side_effect=PermissionError("SECRET C:/private/path")):
            response = self.client.post("/api/data", json=self.body)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertFalse(body["meta"]["cache_available"])
        self.assertEqual(body["meta"]["warnings"][0]["code"], "cache_write_failed")
        self.assertNotIn("SECRET", response.get_data(as_text=True))
        self.assertNotIn("C:/private/path", response.get_data(as_text=True))

    def test_unexpected_internal_errors_are_json_and_sanitized(self):
        with patch("services.geography.cities.load_catalog", side_effect=OSError("SECRET internal filesystem path")):
            self.assert_error(self.client.get("/api/cities"), 500, "internal_error")

    def test_unknown_routes_and_wrong_methods_are_json_with_allow_header(self):
        self.assert_error(self.client.get("/api/not-found"), 404, "not_found")
        self.assert_error(self.client.get("/api/fingerprint-not-found/mendoza"), 404, "not_found")
        response = self.client.get("/api/data")
        self.assert_error(response, 405, "method_not_allowed")
        self.assertIn("POST", response.headers["Allow"])
        self.assert_error(self.client.post("/api/health", json={}), 405, "method_not_allowed")

    def test_cors_is_not_enabled_for_unspecified_frontend_origin(self):
        headers = {"Origin": "https://frontend.example.invalid", "Access-Control-Request-Method": "POST"}
        response = self.client.options("/api/data", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        self.assertNotIn("Access-Control-Allow-Credentials", response.headers)
        response = self.client.get("/api/health", headers=headers)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        self.network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
