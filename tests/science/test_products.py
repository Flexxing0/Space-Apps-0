"""Radar/Fingerprint: NASA simulada y observaciones sintéticas; nunca resultados científicos."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from app import create_app
from scripts.maintenance.generate_radar import main
from services.science import trend_analysis as engine
from services.science.analysis_results import make_result, methodology
from services.providers.bulk import make_query
from services.geography.cities import get_city
from services.science.fingerprint import compare_compatibility
from tests.providers.test_bulk import synthetic_payload


class ProductFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.cache_dir = self.directory / "power"
        self.artifact = self.directory / "radar" / "latest.json"
        self.app = create_app({"TESTING": True, "CACHE_DIR": self.cache_dir, "POWER_REQUEST_DELAY": 0,
                               "POWER_CACHE_MAX_AGE_DAYS": None, "RADAR_ARTIFACT_PATH": self.artifact})
        self.client = self.app.test_client()
        self.analysis = self.app.extensions["earthlens_analysis"]
        self.fingerprint = self.app.extensions["earthlens_fingerprint"]
        self.radar = self.app.extensions["earthlens_radar"]
        self.mutate = None

        def respond(url, *, params, timeout):
            payload = synthetic_payload(params)
            for values in payload["properties"]["parameter"].values():
                for date, value in values.items():
                    values[date] = value + (int(date[:4]) - params["start"]) * 0.01 + int(date[4:]) / 1200
            if self.mutate:
                self.mutate(payload)
            return Mock(json=Mock(return_value=payload))

        patcher = patch("services.providers.power.requests.get", side_effect=respond)
        self.network = patcher.start()
        self.addCleanup(patcher.stop)

    def seed(self):
        report = self.analysis.data_service.bulk.collect_cities()
        self.assertEqual(report["summary"]["succeeded"], 25)
        self.network.reset_mock()


class ProductWithoutSciPyTests(ProductFixture):
    def test_cache_only_missing_records_never_access_network(self):
        records = self.analysis.results({"city_id": "mendoza"}, cache_only=True)
        self.assertEqual(len(records), 6)
        self.assertTrue(all(row["status"] == "error" and row["error"]["code"] == "cache_unavailable" for row in records))
        self.assertTrue(all(row["statistics"] is None and row["unit"] is None for row in records))
        self.assertFalse(self.cache_dir.exists())
        self.network.assert_not_called()

    def test_missing_study_returns_503_without_generating_or_fetching(self):
        response = self.client.get("/api/radar")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "radar_unavailable")
        self.assertFalse(self.artifact.exists())
        self.network.assert_not_called()

    def test_invalid_filters_and_fingerprint_requests_fail_before_network(self):
        for url in ("/api/radar?variable=unknown", "/api/radar?direction=up", "/api/radar?evidence_status=significant",
                    "/api/radar?force=true", "/api/radar?region=", "/api/radar?variable=T2M&variable=WS2M",
                    "/api/fingerprint/unknown", "/api/fingerprint/MENDOZA", "/api/fingerprint/mendoza?latitude=-33",
                    "/api/fingerprint/mendoza?start_year=bad", "/api/fingerprint/mendoza?start_year=2024",
                    "/api/fingerprint/mendoza?start_year=2020&start_year=2021"):
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (400, 404))
        self.network.assert_not_called()

    def test_dry_run_defines_full_family_without_creating_files(self):
        with redirect_stdout(io.StringIO()) as output:
            code = main(["--cache-dir", str(self.cache_dir), "--output", str(self.artifact), "--dry-run"])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(len(result["tests"]), 150)
        self.assertEqual(len({item["test_id"] for item in result["tests"]}), 150)
        self.assertFalse(self.cache_dir.exists())
        self.assertFalse(self.artifact.exists())
        self.network.assert_not_called()

    def test_all_missing_study_keeps_all_errors_and_persists_no_observations(self):
        with redirect_stdout(io.StringIO()):
            code = main(["--cache-dir", str(self.cache_dir), "--output", str(self.artifact)])
        self.assertEqual(code, 1)
        study = self.radar.read()
        self.assertEqual(study["summary"]["statuses"]["error"], 150)
        self.assertEqual(len(study["family"]["exclusions"]), 150)
        self.assertEqual(study["family"]["eligible_test_ids"], [])
        self.assertTrue(all(row["location"]["country_code"] == "AR" for row in study["results"]))
        self.assertFalse(self.cache_dir.exists())
        self.network.assert_not_called()

    def test_corrupt_and_wrong_root_artifacts_are_safe_errors(self):
        self.artifact.parent.mkdir(parents=True)
        for content in ('{"SECRET":', '"SECRET"', '[]', '{}'):
            self.artifact.write_text(content, encoding="utf-8")
            response = self.client.get("/api/radar")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json()["error"]["code"], "radar_invalid_artifact")
            self.assertNotIn(b"SECRET", response.data)
        self.network.assert_not_called()

    def test_provider_failure_creates_explicit_errors_without_raw_exceptions(self):
        self.network.side_effect = requests.Timeout("SECRET path/credentials")
        response = self.client.get("/api/fingerprint/mendoza")
        self.assertEqual(response.status_code, 200)
        profile = response.get_json()["data"]
        self.assertEqual(profile["status"], "error")
        self.assertEqual(profile["summary"]["statuses"]["error"], 6)
        self.assertTrue(all(row["error"]["code"] == "provider_timeout" for row in profile["results"]))
        self.assertNotIn(b"SECRET", response.data)

    def test_cache_only_rejects_force(self):
        with self.assertRaises(ValueError):
            self.analysis.data_service.bulk.collect_cities(cache_only=True, force=True)
        self.network.assert_not_called()

    def test_expired_cache_only_read_preserves_original_bytes(self):
        self.analysis.data_service.get_data({"city_id": "mendoza"})
        path = next(self.cache_dir.glob("*.json"))
        original = path.read_bytes()
        self.analysis.data_service.bulk.max_age_days = 0
        self.network.reset_mock()
        rows = self.analysis.results({"city_id": "mendoza"}, cache_only=True)
        self.assertTrue(all(row["error"]["code"] == "cache_unavailable" for row in rows))
        self.assertEqual(path.read_bytes(), original)
        self.network.assert_not_called()


@unittest.skipUnless(engine.HAS_SCIPY, "SciPy requerido: ejecutar dentro de Docker")
class CommonResultTests(ProductFixture):
    def test_six_variables_share_one_fetch_and_keep_metadata_and_indicators(self):
        records = self.analysis.results({"city_id": "mendoza"})
        self.assertEqual(len(records), 6)
        self.assertEqual(self.network.call_count, 1)
        self.assertTrue(all(row["status"] == "provisional" and row["data_status"] == "valid" for row in records))
        self.assertTrue(all(row["evidence"]["confirmed"] is False for row in records))
        self.assertTrue(all(len(row["series"]) == 25 for row in records))
        precipitation = next(row for row in records if row["variable"] == "PRECTOTCORR")
        self.assertEqual(precipitation["unit"], "mm/day")
        self.assertIn("rate", precipitation["indicator"]["id"])
        self.assertEqual(precipitation["source"]["metadata"]["header"]["api"]["version"], "synthetic-test")
        self.assertEqual(len(precipitation["provenance"]["input_sha256"]), 64)
        self.assertEqual(precipitation["coverage"]["monthly"]["valid_count"], 300)
        self.assertTrue(all(row["available_months"] == 12 for row in precipitation["coverage"]["by_year"]))
        self.assertEqual(precipitation["methodology"]["validation_status"], "pending")
        self.assertIn("unrounded_statistics", [row["id"] for row in precipitation["methodology"]["pending_dependencies"]])

    def test_statistics_equal_existing_endpoint_without_another_rounding(self):
        legacy = self.client.post("/api/analyze", json={"city_id": "mendoza", "variable": "T2M"}).get_json()["data"]
        records = self.analysis.results({"city_id": "mendoza"}, cache_only=True)
        result = next(row for row in records if row["variable"] == "T2M")
        self.assertEqual(result["statistics"], legacy["statistics"])
        self.assertEqual(result["series"], legacy["series"])
        self.assertEqual(result["provenance"]["fetched_at"], legacy["provenance"]["fetched_at"])
        self.assertFalse(result["precision"]["unrounded_available"])
        self.assertIsNone(result["statistics_unrounded"])
        self.assertEqual(self.network.call_count, 1)

    def test_future_unrounded_contract_preserves_received_precision(self):
        self.client.post("/api/data", json={"city_id": "mendoza"})
        data, meta = self.analysis.data_service.get_data({"city_id": "mendoza"})
        legacy = self.analysis._analyze(data["variables"]["T2M"], data, meta)
        full = {**legacy["statistics"], "p_value": 0.04999999999987654, "slope": 0.01234567890123456}
        result = make_result(data["city"], "T2M", {"start_year": 2000, "end_year": 2024}, method=methodology(),
                             row=data["variables"]["T2M"], meta=meta, analysis=legacy, unrounded_statistics=full)
        self.assertEqual(result["statistics_unrounded"], full)
        full["p_value"] = 1
        self.assertEqual(result["statistics_unrounded"]["p_value"], 0.04999999999987654)
        self.assertTrue(result["precision"]["unrounded_available"])
        self.assertFalse(result["evidence"]["confirmed"])

    def test_insufficient_variable_keeps_coverage_without_inventing_statistics(self):
        def missing(payload):
            values = payload["properties"]["parameter"]["T2M"]
            for key in values:
                if int(key[4:]) <= 4:
                    values[key] = -999
        self.mutate = missing
        rows = self.analysis.results({"city_id": "mendoza"})
        row = next(row for row in rows if row["variable"] == "T2M")
        self.assertEqual(row["status"], "insufficient")
        self.assertEqual(row["coverage"]["annual"]["valid_years"], 0)
        self.assertEqual(row["coverage"]["by_year"][0]["engine_usable_months"], 8)
        self.assertIsNone(row["statistics"])
        self.assertEqual(sum(row["status"] == "provisional" for row in rows), 5)

    def test_motor_failure_is_isolated_and_safe(self):
        original = self.analysis._analyze
        def fail_one(row, data, meta):
            if row["variable"] == "RH2M":
                raise RuntimeError("SECRET")
            return original(row, data, meta)
        with patch.object(self.analysis, "_analyze", side_effect=fail_one):
            rows = self.analysis.results({"city_id": "mendoza"})
        self.assertEqual(sum(row["status"] == "provisional" for row in rows), 5)
        error = next(row for row in rows if row["variable"] == "RH2M")
        self.assertEqual(error["status"], "error")
        self.assertIsNone(error["statistics"])
        self.assertNotIn("SECRET", json.dumps(error))

    def test_nonfinite_motor_output_becomes_error_instead_of_invalid_json(self):
        original = self.analysis._analyze
        def nonfinite(row, data, meta):
            result = original(row, data, meta)
            result["statistics"]["slope"] = float("nan")
            return result
        with patch.object(self.analysis, "_analyze", side_effect=nonfinite):
            records = self.analysis.results({"city_id": "mendoza"})
        self.assertTrue(all(row["status"] == "error" and row["statistics"] is None for row in records))
        json.dumps(records, allow_nan=False)

    def test_significance_inconsistency_is_flagged_without_changing_motor_output(self):
        original = self.analysis._analyze
        def inconsistent(row, data, meta):
            result = original(row, data, meta)
            result["statistics"].update(p_value=0.001, significant=False)
            return result
        with patch.object(self.analysis, "_analyze", side_effect=inconsistent):
            records = self.analysis.results({"city_id": "mendoza"})
        self.assertTrue(all(row["evidence"]["status"] == "provisional_inconsistent" for row in records))
        self.assertFalse(records[0]["statistics"]["significant"])


@unittest.skipUnless(engine.HAS_SCIPY, "SciPy requerido: ejecutar dentro de Docker")
class FingerprintTests(ProductFixture):
    def test_endpoint_groups_extremes_and_exposes_six_evidence_records(self):
        response = self.client.get("/api/fingerprint/comodoro-rivadavia")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["status"], "provisional")
        self.assertEqual(len(data["groups"]["primary"]), 4)
        self.assertEqual(set(data["groups"]["extreme"]), {"T2M_MAX", "T2M_MIN"})
        self.assertEqual(len(data["results"]), 6)
        self.assertTrue(data["summary"]["data_complete"])
        for record in data["results"]:
            self.assertEqual(len(record["statistics"]["confidence_interval_95"]), 2)
            self.assertIn("change_per_decade", record["statistics"])
            self.assertIn("city_id=comodoro-rivadavia", record["links"]["explorer"])
            self.assertNotIn("score", record)
        self.assertEqual(self.network.call_count, 1)

    def test_mendoza_posadas_profiles_are_compatible_but_other_methods_or_units_are_not(self):
        a = self.fingerprint.profile("mendoza")
        b = self.fingerprint.profile("posadas")
        self.assertTrue(compare_compatibility(a, b)["compatible"])
        self.assertEqual(a["comparison"]["key"], b["comparison"]["key"])
        b["results"][0]["unit"] = "OTHER"
        self.assertFalse(compare_compatibility(a, b)["compatible"])

    def test_compatibility_includes_monthly_coverage(self):
        a = self.fingerprint.profile("mendoza")
        b = deepcopy(a)
        b["results"][0]["coverage"]["by_year"][0]["available_months"] = 11
        self.assertFalse(compare_compatibility(a, b)["compatible"])

    def test_selected_period_is_preserved(self):
        response = self.client.get("/api/fingerprint/posadas?start_year=2020&end_year=2024")
        profile = response.get_json()["data"]
        self.assertEqual(profile["period"], {"start_year": 2020, "end_year": 2024})
        self.assertTrue(all(len(row["series"]) == 5 for row in profile["results"]))
        params = self.network.call_args.kwargs["params"]
        self.assertEqual((params["start"], params["end"]), (2020, 2024))


@unittest.skipUnless(engine.HAS_SCIPY, "SciPy requerido: ejecutar dentro de Docker")
class RadarTests(ProductFixture):
    def setUp(self):
        super().setUp()
        self.seed()

    def test_full_study_is_cache_only_and_all_tests_are_provisional(self):
        study = self.radar.generate()
        self.assertEqual(study["family"]["planned_tests"], 150)
        self.assertEqual(study["summary"]["cities"], 25)
        self.assertEqual(study["summary"]["computed"], 150)
        self.assertEqual(study["summary"]["cache_hit_cities"], 25)
        self.assertEqual(len(study["family"]["eligible_test_ids"]), 150)
        self.assertEqual(study["family"]["exclusions"], [])
        self.assertFalse(study["multiple_testing"]["ready_for_adjustment"])
        self.assertEqual(study["multiple_testing"]["status"], "not_applied")
        self.assertTrue(all(row["evidence"]["adjusted_p_value"] is None for row in study["results"]))
        self.assertEqual(study["summary"]["confirmed_discoveries"], 0)
        self.network.assert_not_called()

    def test_persisted_records_match_analysis_and_integrity(self):
        study = self.radar.generate()
        persisted = self.radar.persist(study)
        read = self.radar.read()
        self.assertEqual(read, persisted)
        self.assertEqual(read["results"], study["results"])
        profile = self.fingerprint.profile("mendoza", cache_only=True)
        rows = [row for row in read["results"] if row["location"]["id"] == "mendoza"]
        for a, b in zip(rows, profile["results"]):
            for key in ("statistics", "coverage", "series", "analysis_id", "provenance"):
                self.assertEqual(a[key], b[key])
        self.network.assert_not_called()

    def test_filters_never_recompute_or_change_family(self):
        self.radar.persist(self.radar.generate())
        original_bytes = self.artifact.read_bytes()
        base = self.client.get("/api/radar").get_json()["data"]
        with patch.object(engine, "analyze_series", side_effect=AssertionError("No recomputar")):
            for query, expected in (("variable=T2M", 25), ("region=Cuyo", 18), ("province=CABA", 6),
                                    ("variable=T2M&direction=increasing", 25), ("evidence_status=confirmed", 0),
                                    ("province=unknown", 0)):
                response = self.client.get("/api/radar?" + query)
                self.assertEqual(response.status_code, 200)
                filtered = response.get_json()["data"]
                self.assertEqual(filtered["view"]["count"], expected)
                for key in ("study_id", "run_id", "family", "multiple_testing", "summary", "artifact_integrity"):
                    self.assertEqual(filtered[key], base[key])
        self.assertEqual(self.artifact.read_bytes(), original_bytes)
        self.network.assert_not_called()

    def test_missing_city_excludes_six_tests_without_network(self):
        city = get_city("mendoza")
        query = make_query(city["latitude"], city["longitude"], 2000, 2024)
        self.analysis.data_service.bulk.cache.path_for(query).unlink()
        study = self.radar.generate()
        self.assertEqual(study["summary"]["computed"], 144)
        self.assertEqual(study["summary"]["statuses"]["error"], 6)
        self.assertEqual(len(study["family"]["exclusions"]), 6)
        self.assertEqual(len(study["results"]), 150)
        self.network.assert_not_called()

    def test_insufficient_and_inconsistent_tests_are_recorded_in_full_family(self):
        from services.api_service import ServiceError
        original = self.analysis._analyze
        def mixed(row, data, meta):
            if data["city"]["id"] == "mendoza" and row["variable"] == "T2M":
                raise ServiceError("insufficient_data", "Cobertura sintética insuficiente", details={
                    "completeness": {"valid_years": 2, "requested_years": 25, "is_complete": False}})
            result = original(row, data, meta)
            if data["city"]["id"] == "posadas" and row["variable"] == "WS2M":
                result["statistics"].update(p_value=0.001, significant=False)
            return result
        with patch.object(self.analysis, "_analyze", side_effect=mixed):
            study = self.radar.generate()
        self.assertEqual(len(study["results"]), 150)
        self.assertEqual(len(study["family"]["eligible_test_ids"]), 148)
        exclusions = {item["test_id"]: item["reason"] for item in study["family"]["exclusions"]}
        self.assertEqual(exclusions, {"mendoza:T2M": "insufficient_data", "posadas:WS2M": "provisional_inconsistent"})
        self.assertEqual(study["summary"]["statuses"]["insufficient"], 1)
        self.radar.persist(study)
        self.network.assert_not_called()

    def test_persistence_rejects_a_subfamily_or_false_confirmation(self):
        study = self.radar.generate()
        incomplete = deepcopy(study)
        incomplete["results"].pop()
        with self.assertRaises(ValueError):
            self.radar.persist(incomplete)
        study["results"][0]["evidence"]["confirmed"] = True
        with self.assertRaises(ValueError):
            self.radar.persist(study)
        self.assertFalse(self.artifact.exists())

    def test_atomic_failure_preserves_previous_study(self):
        self.radar.persist(self.radar.generate())
        original = self.artifact.read_bytes()
        with patch("services.providers.cache.os.replace", side_effect=OSError("Synthetic write failure")):
            with self.assertRaises(OSError):
                self.radar.persist(self.radar.generate())
        self.assertEqual(self.artifact.read_bytes(), original)
        self.assertEqual(len(list(self.artifact.parent.glob(".tmp-*"))), 0)

    def test_tampering_is_detected_without_leaking_content(self):
        document = self.radar.persist(self.radar.generate())
        document["results"][0]["statistics"]["slope"] = 123456
        self.artifact.write_text(json.dumps(document), encoding="utf-8")
        response = self.client.get("/api/radar")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "radar_invalid_artifact")
        self.assertNotIn(b"123456", response.data)

    def test_cannot_overwrite_power_cache_with_study(self):
        target = next(self.cache_dir.glob("*.json"))
        original = target.read_bytes()
        self.radar.artifact_path = target
        with self.assertRaises(ValueError):
            self.radar.persist(self.radar.generate())
        self.assertEqual(target.read_bytes(), original)

    def test_rerun_reuses_study_identity_but_has_separate_execution_id(self):
        a, b = self.radar.generate(), self.radar.generate()
        self.assertEqual(a["family"]["id"], b["family"]["id"])
        self.assertEqual(a["study_id"], b["study_id"])
        self.assertNotEqual(a["run_id"], b["run_id"])
        self.network.assert_not_called()

    def test_cli_uses_existing_cache_and_writes_complete_study(self):
        with redirect_stdout(io.StringIO()) as output:
            code = main(["--cache-dir", str(self.cache_dir), "--output", str(self.artifact)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["summary"]["tests"], 150)
        self.assertEqual(self.radar.read()["study_id"], result["study_id"])
        self.network.assert_not_called()
