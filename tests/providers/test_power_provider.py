"""Pruebas sin red con valores sintéticos, no observaciones ambientales."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

import requests

from services.providers.power import BASE_URL, VARIABLES, get_data, get_data_multi


def make_payload():
    """Simula únicamente el contrato JSON de NASA POWER."""
    units = {
        "T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C",
        "PRECTOTCORR": "mm/day", "RH2M": "%", "WS2M": "m/s",
    }
    return {
        "type": "Feature",
        "header": {
            "sources": ["MERRA2", "POWER"],
            "api": {"version": "synthetic-test"},
            "fill_value": -999.0,
            "time_standard": "LST",
            "start": "20240101",
            "end": "20241231",
        },
        "geometry": {"type": "Point", "coordinates": [-67.5, -45.86]},
        "parameters": {
            variable: {"units": unit, "longname": f"Synthetic {variable}"}
            for variable, unit in units.items()
        },
        "properties": {
            "parameter": {
                variable: {
                    "202403": -999.0,
                    "202402": 0.0,
                    "202401": 1.0,
                    "202404": None,
                    "202413": 1.0,
                }
                for variable in units
            }
        },
        "messages": ["Synthetic test message"],
        "times": {"data": 0.0},
    }


class PowerProviderTests(unittest.TestCase):
    def setUp(self):
        self.payload = make_payload()
        self.response = Mock()
        self.response.json.return_value = self.payload
        patcher = patch("services.providers.power.requests.get", return_value=self.response)
        self.request = patcher.start()
        self.addCleanup(patcher.stop)

    def fetch(self, variables=None):
        if variables is None:
            variables = list(VARIABLES)
        return get_data_multi(-45.86, -67.5, variables, 2024, 2024)

    def test_six_variables_use_one_request(self):
        results = self.fetch()
        self.request.assert_called_once_with(
            BASE_URL,
            params={
                "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M",
                "community": "AG",
                "latitude": -45.86,
                "longitude": -67.5,
                "start": 2024,
                "end": 2024,
                "format": "JSON",
            },
            timeout=60,
        )
        self.response.raise_for_status.assert_called_once_with()
        self.assertEqual(list(results), list(VARIABLES))
        for variable, result in results.items():
            with self.subTest(variable=variable):
                self.assertEqual(result["variable"], variable)
                self.assertEqual(result["unit"], self.payload["parameters"][variable]["units"])

    def test_legacy_signature_and_fields_are_preserved(self):
        result = get_data(-45.86, -67.5, "RH2M", 2000, 2024)
        self.assertEqual(
            {key: value for key, value in result.items() if key != "metadata"},
            {
                "provider": "NASA POWER", "dataset": "MERRA-2",
                "variable": "RH2M", "name": "Humedad relativa", "unit": "%",
                "latitude": -45.86, "longitude": -67.5,
                "start_year": 2000, "end_year": 2024, "frequency": "monthly",
                "series": [
                    {"date": "2024-01", "value": 1.0},
                    {"date": "2024-02", "value": 0.0},
                    {"date": "2024-03", "value": None},
                    {"date": "2024-04", "value": None},
                ],
            },
        )
        self.assertEqual(self.request.call_args.kwargs["params"]["parameters"], "RH2M")

    def test_keyword_call_matches_multivariable_result(self):
        single = get_data(
            latitude=-45.86, longitude=-67.5, variable="T2M",
            start_year=2024, end_year=2024,
        )
        self.assertEqual(single, self.fetch(["T2M"])["T2M"])

    def test_each_variable_keeps_its_own_series(self):
        self.payload["properties"]["parameter"]["RH2M"]["202401"] = 2.0
        self.payload["properties"]["parameter"]["WS2M"]["202402"] = -999.0
        results = self.fetch()
        self.assertEqual(results["T2M"]["series"][0]["value"], 1.0)
        self.assertEqual(results["RH2M"]["series"][0]["value"], 2.0)
        self.assertEqual(results["T2M"]["series"][1]["value"], 0.0)
        self.assertIsNone(results["WS2M"]["series"][1]["value"])

    def test_metadata_and_raw_response_are_preserved(self):
        original = deepcopy(self.payload)
        results = self.fetch()
        for variable, result in results.items():
            with self.subTest(variable=variable):
                expected = {
                    key: value for key, value in original.items()
                    if key not in ("properties", "parameters")
                }
                expected["parameter"] = original["parameters"][variable]
                self.assertEqual(result["metadata"], expected)
        self.assertEqual(self.payload, original)

    def test_missing_values_zero_and_annual_record(self):
        for result in self.fetch().values():
            self.assertEqual(result["series"], [
                {"date": "2024-01", "value": 1.0},
                {"date": "2024-02", "value": 0.0},
                {"date": "2024-03", "value": None},
                {"date": "2024-04", "value": None},
            ])

    def test_fill_value_from_header_is_used(self):
        self.payload["header"]["fill_value"] = -888.0
        self.payload["properties"]["parameter"]["T2M"]["202401"] = -888.0
        series = self.fetch(["T2M"])["T2M"]["series"]
        self.assertIsNone(series[0]["value"])
        self.assertEqual(series[2]["value"], -999.0)

    def test_legacy_defaults_when_optional_metadata_is_absent(self):
        del self.payload["header"]
        del self.payload["parameters"]
        for variable, result in self.fetch().items():
            self.assertEqual(result["unit"], VARIABLES[variable]["unit"])
            self.assertIsNone(result["series"][2]["value"])

    def test_duplicates_are_removed_and_order_is_preserved(self):
        results = self.fetch(("WS2M", "T2M", "WS2M"))
        self.assertEqual(list(results), ["WS2M", "T2M"])
        self.assertEqual(self.request.call_args.kwargs["params"]["parameters"], "WS2M,T2M")

    def test_invalid_variables_fail_before_network_access(self):
        for variables in ([], (), "T2M", b"T2M", 42, ["INVALID"], ["T2M", "INVALID"], [None], [["T2M"]]):
            with self.subTest(variables=variables), self.assertRaises(ValueError):
                get_data_multi(-45.86, -67.5, variables, 2024, 2024)
        self.request.assert_not_called()

    def test_invalid_legacy_variable_keeps_error(self):
        with self.assertRaisesRegex(ValueError, "^Variable no disponible$"):
            get_data(-45.86, -67.5, "INVALID", 2024, 2024)
        self.request.assert_not_called()

    def test_missing_requested_variable_fails_explicitly(self):
        del self.payload["properties"]["parameter"]["RH2M"]
        with self.assertRaisesRegex(ValueError, "no devolvió la variable RH2M"):
            self.fetch()

    def test_malformed_response_fails_explicitly(self):
        malformed = (None, [], {}, {"properties": None}, {"properties": {"parameter": []}})
        for payload in malformed:
            with self.subTest(payload=payload):
                self.response.json.return_value = payload
                with self.assertRaisesRegex(ValueError, "sin series válidas"):
                    self.fetch()

    def test_malformed_series_or_metadata_fails_explicitly(self):
        for container, key in (
            (self.payload["properties"]["parameter"], "T2M"),
            (self.payload["parameters"], "T2M"),
            (self.payload, "parameters"),
            (self.payload, "header"),
        ):
            with self.subTest(key=key):
                original = container[key]
                container[key] = None
                try:
                    with self.assertRaisesRegex(ValueError, "inválid"):
                        self.fetch()
                finally:
                    container[key] = original

    def test_network_and_http_errors_propagate(self):
        for error in (requests.Timeout("timeout"), requests.ConnectionError("connection")):
            with self.subTest(error=type(error).__name__):
                self.request.side_effect = error
                with self.assertRaises(type(error)):
                    self.fetch()
        self.request.side_effect = None
        self.response.raise_for_status.side_effect = requests.HTTPError("422")
        with self.assertRaises(requests.HTTPError):
            self.fetch()
        self.response.json.assert_not_called()

    def test_invalid_json_propagates(self):
        self.response.json.side_effect = requests.exceptions.JSONDecodeError("invalid", "", 0)
        with self.assertRaises(requests.exceptions.JSONDecodeError):
            self.fetch()


if __name__ == "__main__":
    unittest.main()
