"""GeoRef simulado a partir de los registros oficiales ya guardados."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.data.build_city_catalog import CITY_SPECS, GEOREF_URL, build_catalog
from services.geography.cities import load_catalog


class CityCatalogBuilderTests(unittest.TestCase):
    def setUp(self):
        self.responses = [{"localidades_censales": [deepcopy(city["coordinate_source"]["record"])], "total": 1}
                          for city in load_catalog()["cities"]]
        response = Mock()
        response.json.return_value = {"resultados": self.responses}
        patcher = patch("scripts.data.build_city_catalog.requests.post", return_value=response)
        self.network = patcher.start()
        self.addCleanup(patcher.stop)

    def test_bulk_georef_request_and_atomic_output(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            output = Path(directory) / "cities.json"
            catalog = build_catalog(output=output)
            self.assertEqual(len(load_catalog(output)["cities"]), 25)
            for city, result in zip(catalog["cities"], self.responses):
                self.assertEqual(city["coordinate_source"]["record"], result["localidades_censales"][0])
            args = self.network.call_args
            self.assertEqual(args.args[0], GEOREF_URL)
            self.assertEqual(len(args.kwargs["json"]["localidades_censales"]), len(CITY_SPECS))
            self.network.assert_called_once()

    def test_ambiguous_or_wrong_province_never_overwrites_catalog(self):
        for mutation in ("ambiguous", "wrong-province", "incomplete"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
                output = Path(directory) / "cities.json"
                output.write_text("previous valid catalog placeholder", encoding="utf-8")
                original = output.read_bytes()
                responses = deepcopy(self.responses)
                if mutation == "ambiguous":
                    responses[0]["localidades_censales"] *= 2
                elif mutation == "wrong-province":
                    responses[0]["localidades_censales"][0]["provincia"]["nombre"] = "Other"
                else:
                    responses.pop()
                self.network.return_value.json.return_value = {"resultados": responses}
                with self.assertRaises(ValueError):
                    build_catalog(output=output)
                self.assertEqual(output.read_bytes(), original)

    def test_check_only_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            output = Path(directory) / "absent.json"
            self.assertEqual(len(build_catalog(check_only=True, output=output)["cities"]), 25)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
