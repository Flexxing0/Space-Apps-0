"""Pruebas heredadas del catálogo; la muestra se usa sólo como fixture de software."""
"""Pruebas del catálogo y las misiones (Persona 5).

Ejecutar:  python -m pytest tests/science/test_datasets.py   (o  python -m unittest tests.science.test_datasets)
"""

import json
import unittest
from pathlib import Path

from services.science import guided_missions as datasets

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "samples" / "power_comodoro_2000_2024.json"


class CatalogTests(unittest.TestCase):
    def test_mvp_variables_present(self):
        for code in ("T2M", "PRECTOTCORR", "RH2M", "WS2M", "T2M_MAX", "T2M_MIN"):
            self.assertTrue(datasets.is_supported_variable(code), code)

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(datasets.get_variable("t2m")["code"], "T2M")
        self.assertIsNone(datasets.get_variable("NOPE"))

    def test_recommend_by_phenomenon(self):
        codes = [v["code"] for v in datasets.recommend_variables("sequia")]
        self.assertEqual(codes[0], "PRECTOTCORR")
        self.assertIn("RH2M", codes)
        self.assertEqual(datasets.recommend_variables("desconocido"), [])

    def test_phenomena_reference_known_variables(self):
        for p in datasets.list_phenomena():
            for code in p["variables"]:
                self.assertTrue(datasets.is_supported_variable(code), (p["id"], code))


class MissionTests(unittest.TestCase):
    def test_missions_are_consistent(self):
        missions = datasets.list_missions()
        self.assertGreaterEqual(len(missions), 3)
        for summary in missions:
            m = datasets.get_mission(summary["id"])
            self.assertIsNotNone(m["variable_info"], m["id"])
            self.assertLess(m["start_year"], m["end_year"])
            self.assertGreaterEqual(m["start_year"], m["variable_info"]["temporal_start"])
            for loc in m["locations"]:
                self.assertTrue(-90 <= loc["latitude"] <= 90)
                self.assertTrue(-180 <= loc["longitude"] <= 180)
            if m["mode"] == "compare":
                self.assertEqual(len(m["locations"]), 2)

    def test_unknown_mission(self):
        self.assertIsNone(datasets.get_mission("no-existe"))

    def test_target_urls(self):
        m = datasets.get_mission("patagonia-cambiante")
        self.assertTrue(m["explorer_url"].startswith("/explorer?"))
        self.assertIn("variable=T2M", m["explorer_url"])
        wind = datasets.get_mission("misterio-del-viento")
        self.assertTrue(wind["explorer_url"].startswith("/compare?"))
        self.assertIn("lat2=", wind["explorer_url"])


class HypothesisTests(unittest.TestCase):
    up_sig = {"direction": "increasing", "significant": True, "p_value": 0.01}
    up_ns = {"direction": "increasing", "significant": False, "p_value": 0.3}

    def test_supported(self):
        self.assertEqual(datasets.evaluate_hypothesis("increasing", self.up_sig)["verdict"], "supported")

    def test_contradicted(self):
        self.assertEqual(datasets.evaluate_hypothesis("decreasing", self.up_sig)["verdict"], "contradicted")
        self.assertEqual(datasets.evaluate_hypothesis("no_clear_trend", self.up_sig)["verdict"], "contradicted")

    def test_not_significant_is_inconclusive(self):
        self.assertEqual(datasets.evaluate_hypothesis("increasing", self.up_ns)["verdict"], "inconclusive")
        self.assertEqual(datasets.evaluate_hypothesis("no_clear_trend", self.up_ns)["verdict"], "supported")


@unittest.skipUnless(SAMPLE.exists(), "falta la muestra de NASA POWER")
class AnnualAggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
        cls.raw = cls.payload["properties"]["parameter"]

    def test_full_period(self):
        series = datasets.annual_series_from_power_monthly(self.payload, "T2M")
        self.assertEqual([p["year"] for p in series], list(range(2000, 2025)))

    def test_mean_matches_power_annual(self):
        for p in datasets.annual_series_from_power_monthly(self.payload, "T2M"):
            self.assertAlmostEqual(p["value"], self.raw["T2M"][f"{p['year']}13"], delta=0.05)

    def test_precipitation_is_annual_total(self):
        for p in datasets.annual_series_from_power_monthly(self.payload, "PRECTOTCORR"):
            # Total anual ≈ promedio anual de POWER (mm/día) × días del año
            expected = self.raw["PRECTOTCORR"][f"{p['year']}13"] * 365
            self.assertAlmostEqual(p["value"], expected, delta=0.05 * expected + 5)

    def test_extremes_match_power_annual(self):
        for code in ("T2M_MAX", "T2M_MIN"):
            for p in datasets.annual_series_from_power_monthly(self.payload, code):
                self.assertAlmostEqual(p["value"], self.raw[code][f"{p['year']}13"], delta=0.01)

    def test_incomplete_year_is_dropped(self):
        payload = json.loads(json.dumps(self.payload))
        payload["properties"]["parameter"]["T2M"]["200503"] = -999.0
        years = [p["year"] for p in datasets.annual_series_from_power_monthly(payload, "T2M")]
        self.assertNotIn(2005, years)


if __name__ == "__main__":
    unittest.main()
