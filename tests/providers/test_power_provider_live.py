"""Verificación optativa contra NASA POWER; requiere acceso a Internet."""

import os
import unittest

from services.providers.power import VARIABLES, get_data, get_data_multi


@unittest.skipUnless(
    os.environ.get("EARTHLENS_POWER_LIVE") == "1",
    "Definir EARTHLENS_POWER_LIVE=1 para consultar NASA POWER",
)
class PowerProviderLiveTests(unittest.TestCase):
    def test_six_variables_and_legacy_query(self):
        results = get_data_multi(-45.86, -67.5, list(VARIABLES), 2024, 2024)
        expected_units = {
            "T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C",
            "PRECTOTCORR": "mm/day", "RH2M": "%", "WS2M": "m/s",
        }
        expected_dates = [f"2024-{month:02d}" for month in range(1, 13)]
        self.assertEqual(set(results), set(VARIABLES))
        for variable, result in results.items():
            with self.subTest(variable=variable):
                self.assertEqual(result["unit"], expected_units[variable])
                self.assertEqual([point["date"] for point in result["series"]], expected_dates)
                self.assertEqual(result["metadata"]["parameter"]["units"], result["unit"])
                self.assertTrue(result["metadata"]["header"]["sources"])
                self.assertEqual(result["metadata"]["geometry"]["type"], "Point")
                fill_value = result["metadata"]["header"]["fill_value"]
                for point in result["series"]:
                    self.assertNotEqual(point["value"], fill_value)
                    self.assertTrue(point["value"] is None or isinstance(point["value"], (int, float)))

        # Repite la consulta original de scripts/audit/probe_nasa_power.py y compara el año en común.
        legacy = get_data(-45.86, -67.5, "RH2M", 2000, 2024)
        self.assertEqual(len(legacy["series"]), 25 * 12)
        self.assertEqual(legacy["series"][0]["date"], "2000-01")
        self.assertEqual(legacy["series"][-12:], results["RH2M"]["series"])
        self.assertEqual(legacy["unit"], results["RH2M"]["unit"])


if __name__ == "__main__":
    unittest.main()
