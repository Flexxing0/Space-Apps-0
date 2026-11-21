"""Obtención y CLI con NASA completamente simulada; ninguna observación real."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from scripts.data.fetch_power import main
from services.providers.bulk import PowerBulkService, make_query
from services.providers.cache import JsonCache
from services.geography.cities import get_city
from services.geography.geography import TerritoryEvidence
from services.providers.power import BASE_URL, VARIABLES


def synthetic_payload(params):
    """Replica el formato mensual con números de prueba, no mediciones."""
    units = {"T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C", "PRECTOTCORR": "mm/day", "RH2M": "%", "WS2M": "m/s"}
    return {
        "type": "Feature",
        "header": {"sources": ["MERRA2", "POWER"], "fill_value": -999.0,
                   "api": {"version": "synthetic-test"}, "time_standard": "LST"},
        "geometry": {"type": "Point", "coordinates": [params["longitude"], params["latitude"]]},
        "parameters": {variable: {"units": units[variable], "longname": f"Synthetic {variable}"} for variable in VARIABLES},
        "properties": {"parameter": {
            variable: {f"{year}{month:02d}": float(index) for year in range(params["start"], params["end"] + 1)
                       for month in range(1, 14)}
            for index, variable in enumerate(VARIABLES)
        }},
        "messages": [],
    }


class BulkTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.cache = JsonCache(self.directory / "cache")
        self.service = PowerBulkService(self.cache, request_delay=0)
        self.mutate = None
        self.fail_latitude = None
        patcher = patch("services.providers.power.requests.get", side_effect=self.respond)
        self.network = patcher.start()
        self.addCleanup(patcher.stop)

    def respond(self, url, *, params, timeout):
        self.assertEqual(url, BASE_URL)
        self.assertEqual(params["parameters"], ",".join(VARIABLES))
        self.assertEqual(timeout, 60)
        if params["latitude"] == self.fail_latitude:
            raise requests.Timeout("synthetic timeout")
        payload = synthetic_payload(params)
        if self.mutate:
            self.mutate(payload)
        response = Mock()
        response.json.return_value = payload
        return response

    def test_three_initial_cities_default_period_and_cache_reuse(self):
        identifiers = ["comodoro-rivadavia", "mendoza", "posadas"]
        report = self.service.collect_cities(city_ids=identifiers)
        self.assertEqual(report["summary"], {"requested": 3, "succeeded": 3, "failed": 0, "cache_hits": 0, "downloaded": 3})
        self.assertEqual(self.network.call_count, 3)
        for result in report["results"]:
            self.assertEqual(set(result["data"]), set(VARIABLES))
            self.assertEqual(result["quality"]["T2M"], {"expected_count": 300, "valid_count": 300, "missing_count": 0})
            self.assertEqual(result["data"]["T2M"]["series"][0], {"date": "2000-01", "value": 0.0})
            cached = self.cache.read(result["query"])
            self.assertEqual(cached["location"]["coordinate_source"], result["location"]["coordinate_source"])
            self.assertEqual(cached["data"]["T2M"]["unit"], "C")
            self.assertEqual(cached["data"]["RH2M"]["metadata"]["header"]["sources"], ["MERRA2", "POWER"])
        again = self.service.collect_cities(city_ids=identifiers)
        self.assertEqual(again["summary"]["cache_hits"], 3)
        self.assertEqual(self.network.call_count, 3)
        for first, second in zip(report["results"], again["results"]):
            self.assertEqual(first["data"], second["data"])
            self.assertEqual(first["fetched_at"], second["fetched_at"])

    def test_single_subset_region_and_province(self):
        self.assertEqual(self.service.collect_city("posadas", start_year=2024, end_year=2024)["status"], "ok")
        subset = self.service.collect_cities(city_ids=["mendoza", "mendoza", "posadas"], start_year=2024, end_year=2024)
        self.assertEqual(subset["summary"]["requested"], 2)
        self.assertEqual(self.service.collect_cities(region="Cuyo")["summary"]["requested"], 3)
        self.assertEqual(self.service.collect_cities(province="Chubut")["summary"]["requested"], 3)
        self.assertEqual(self.service.collect_cities(province="Misiones", region="NEA")["summary"]["requested"], 1)

    def test_entire_catalog_is_only_simulated(self):
        report = self.service.collect_cities(start_year=2024, end_year=2024)
        self.assertEqual(report["summary"]["succeeded"], 25)
        self.assertEqual(self.network.call_count, 25)

    def test_one_timeout_and_unknown_id_do_not_stop_other_cities(self):
        self.fail_latitude = get_city("mendoza")["latitude"]
        report = self.service.collect_cities(city_ids=["comodoro-rivadavia", "mendoza", "unknown", "posadas"])
        self.assertEqual([result["status"] for result in report["results"]], ["ok", "error", "error", "ok"])
        self.assertEqual(report["summary"]["failed"], 2)
        self.assertEqual(self.network.call_count, 3)
        self.assertEqual(report["results"][1]["error"]["type"], "Timeout")

    def test_failed_incomplete_or_degraded_refresh_preserves_valid_cache(self):
        first = self.service.collect_city("mendoza", start_year=2024, end_year=2024)
        path = self.cache.path_for(first["query"])
        original = path.read_bytes()
        mutations = (
            lambda data: data["properties"]["parameter"].pop("RH2M"),
            lambda data: data["properties"]["parameter"]["T2M"].pop("202401"),
            lambda data: data["properties"]["parameter"]["RH2M"].update({f"2024{month:02d}": -999 for month in range(1, 13)}),
            lambda data: data["properties"]["parameter"]["T2M"].update({"202401": -999}),
            lambda data: data["parameters"]["T2M"].update(units=None),
            lambda data: data["header"].update(sources=[]),
            lambda data: data["properties"]["parameter"]["T2M"].update({"202401": float("nan")}),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.mutate = mutation
                result = self.service.collect_city("mendoza", start_year=2024, end_year=2024, force=True)
                self.assertEqual(result["status"], "error")
                self.assertTrue(result["cache_preserved"])
                self.assertEqual(path.read_bytes(), original)
        self.mutate = None
        self.fail_latitude = get_city("mendoza")["latitude"]
        result = self.service.collect_city("mendoza", start_year=2024, end_year=2024, force=True)
        self.assertTrue(result["cache_preserved"])
        self.assertEqual(path.read_bytes(), original)
        cached = self.service.collect_city("mendoza", start_year=2024, end_year=2024)
        self.assertEqual(cached["origin"], "cache")
        self.assertEqual(cached["fetched_at"], first["fetched_at"])

    def test_uncached_incomplete_response_is_not_written(self):
        self.mutate = lambda data: data["properties"]["parameter"]["T2M"].pop("202401")
        result = self.service.collect_city("posadas", start_year=2024, end_year=2024)
        self.assertEqual(result["status"], "error")
        self.assertFalse(list(self.cache.directory.glob("*.json")))

    def test_scientific_null_is_preserved_and_counted(self):
        self.mutate = lambda data: data["properties"]["parameter"]["T2M"].update({"202401": -999})
        result = self.service.collect_city("posadas", start_year=2024, end_year=2024)
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["data"]["T2M"]["series"][0]["value"])
        self.assertEqual(result["quality"]["T2M"]["missing_count"], 1)
        self.assertEqual(self.service.collect_city("posadas", start_year=2024, end_year=2024)["origin"], "cache")

    def test_period_change_and_force_success(self):
        first = self.service.collect_city("mendoza", start_year=2024, end_year=2024)
        changed = self.service.collect_city("mendoza", start_year=2023, end_year=2024)
        self.assertNotEqual(first["cache_path"], changed["cache_path"])
        self.mutate = lambda data: data["properties"]["parameter"]["T2M"].update({"202401": 2.0})
        updated = self.service.collect_city("mendoza", start_year=2024, end_year=2024, force=True)
        self.assertEqual(updated["origin"], "nasa_power")
        self.assertEqual(updated["data"]["T2M"]["series"][0]["value"], 2.0)
        self.assertEqual(self.network.call_count, 3)

    def test_expiration_and_corrupt_cache_trigger_refetch(self):
        result = self.service.collect_city("mendoza", start_year=2024, end_year=2024)
        expired_service = PowerBulkService(self.cache, request_delay=0, max_age_days=0)
        self.assertEqual(expired_service.collect_city("mendoza", start_year=2024, end_year=2024)["origin"], "nasa_power")
        self.cache.path_for(result["query"]).write_text("broken-json", encoding="utf-8")
        repaired = self.service.collect_city("mendoza", start_year=2024, end_year=2024)
        self.assertEqual(repaired["status"], "ok")
        self.assertTrue(repaired["warnings"])
        self.assertEqual(self.network.call_count, 3)

    def test_cache_write_failure_reports_valid_data_and_preserves_file(self):
        first = self.service.collect_city("mendoza", start_year=2024, end_year=2024)
        path = self.cache.path_for(first["query"])
        original = path.read_bytes()
        with patch("services.providers.cache.os.replace", side_effect=OSError("synthetic disk error")):
            result = self.service.collect_city("mendoza", start_year=2024, end_year=2024, force=True)
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["cache_written"])
        self.assertTrue(result["warnings"])
        self.assertEqual(path.read_bytes(), original)

    def test_network_pacing_excludes_cache_hits(self):
        self.service.request_delay = 1
        with patch("services.providers.bulk.time.monotonic", side_effect=[0, 0.1, 1]), patch("services.providers.bulk.time.sleep") as sleep:
            self.service.collect_cities(city_ids=["mendoza", "posadas"], start_year=2024, end_year=2024)
            self.service.collect_city("mendoza", start_year=2024, end_year=2024)
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 0.9)
        self.assertEqual(self.network.call_count, 2)

    def test_arbitrary_location_requires_territorial_evidence(self):
        result = self.service.collect_location(-40, -60, start_year=2024, end_year=2024)
        self.assertEqual(result["error"]["type"], "TerritoryValidationUnavailable")
        self.network.assert_not_called()
        validator = Mock(return_value=TerritoryEvidence(True, "AR", "point_in_polygon", "synthetic-test-only"))
        service = PowerBulkService(self.cache, request_delay=0, territory_validator=validator)
        self.assertEqual(service.collect_location(-40, -60, start_year=2024, end_year=2024)["status"], "ok")
        validator.return_value = TerritoryEvidence(False, "XX", "point_in_polygon", "synthetic-test-only")
        self.assertEqual(service.collect_location(-40, -60)["error"]["type"], "OutsideArgentina")
        self.assertEqual(self.network.call_count, 1)

    def test_bad_periods_and_selections_fail_before_network(self):
        for args in ({"start_year": 2025, "end_year": 2024}, {"start_year": "2000"},
                     {"start_year": True}, {"start_year": 1980}, {"city_ids": "mendoza"},
                     {"city_ids": []}, {"city_ids": [None]}, {"region": "not-found"},
                     {"city_id": "mendoza", "city_ids": ["posadas"]}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.service.collect_cities(**args)
        for args in ({"request_delay": -1}, {"request_delay": float("nan")}, {"max_age_days": -1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                PowerBulkService(self.cache, **args)
        self.network.assert_not_called()

    def test_cli_requires_explicit_selection(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main([])
        self.assertEqual(error.exception.code, 2)
        self.network.assert_not_called()

    def test_cli_dry_run_and_subset_execution(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--all", "--dry-run", "--cache-dir", str(self.cache.directory)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["count"], 25)
        self.network.assert_not_called()
        self.assertFalse(self.cache.directory.exists())
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--cities", "comodoro-rivadavia", "mendoza", "posadas",
                         "--cache-dir", str(self.cache.directory), "--delay", "0"])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["summary"]["downloaded"], 3)
        self.assertNotIn("data", report["results"][0])
        self.assertEqual(self.network.call_count, 3)


if __name__ == "__main__":
    unittest.main()
