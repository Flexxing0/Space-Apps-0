"""El validador territorial de estas pruebas es simulado; no son límites reales."""

import unittest
from unittest.mock import Mock

from services.geography.geography import (
    OutsideArgentina, TerritoryEvidence, TerritoryValidationUnavailable,
    validate_argentina_location, validate_coordinates,
)


class GeographyTests(unittest.TestCase):
    def test_world_ranges_do_not_validate_argentina(self):
        self.assertEqual(validate_coordinates(-40, -60), (-40.0, -60.0))
        with self.assertRaises(TerritoryValidationUnavailable):
            validate_argentina_location(-40, -60)

    def test_invalid_coordinates(self):
        for coordinates in ((None, -60), (-91, -60), (-40, 181), (True, -60), (float("nan"), -60), (-40, float("inf"))):
            with self.subTest(coordinates=coordinates), self.assertRaises(ValueError):
                validate_coordinates(*coordinates)

    def test_bounding_box_is_never_definitive(self):
        validator = Mock(return_value=TerritoryEvidence(True, "AR", "bounding_box", "synthetic-test"))
        with self.assertRaises(TerritoryValidationUnavailable):
            validate_argentina_location(-40, -60, validator)

    def test_validated_inside_and_outside_with_mocked_boundaries(self):
        validator = Mock(return_value=TerritoryEvidence(True, "AR", "point_in_polygon", "synthetic-test-boundaries"))
        evidence = validate_argentina_location(-40, -60, validator)
        self.assertEqual(evidence["country_code"], "AR")
        validator.assert_called_once_with(-40.0, -60.0)
        for inside, country in ((False, "AR"), (True, "XX")):
            validator.return_value = TerritoryEvidence(inside, country, "point_in_polygon", "synthetic-test-boundaries")
            with self.assertRaises(OutsideArgentina):
                validate_argentina_location(-40, -60, validator)


if __name__ == "__main__":
    unittest.main()
