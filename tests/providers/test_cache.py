"""Pruebas de persistencia, corrupción y protección de reemplazos locales."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.providers.bulk import make_query
from services.providers.cache import CacheError, JsonCache


class CacheTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cache = JsonCache(Path(directory.name))
        self.query = make_query(-40, -60, 2024, 2024)
        self.timestamp = "2024-12-31T23:59:59+00:00"

    def test_cache_round_trip_preserves_data_and_timestamp(self):
        self.assertIsNone(self.cache.read(self.query))
        data = {"synthetic": {"series": [{"date": "2024-01", "value": None}], "unit": "C"}}
        self.cache.write(self.query, data, self.timestamp, location={"country_code": "AR"})
        cached = self.cache.read(self.query)
        self.assertEqual(cached["data"], data)
        self.assertEqual(cached["query"], self.query)
        self.assertEqual(cached["fetched_at"], self.timestamp)
        self.assertEqual(cached["location"], {"country_code": "AR"})

    def test_keys_are_canonical_and_distinguish_query_identity(self):
        self.assertEqual(self.cache.path_for(self.query), self.cache.path_for(dict(reversed(list(self.query.items())))))
        for field, value in (("latitude", -41), ("longitude", -61), ("start_year", 2000), ("end_year", 2025),
                             ("frequency", "daily"), ("variables", ["T2M"]), ("provider", "other"),
                             ("dataset", "other"), ("community", "RE"), ("endpoint", "other")):
            with self.subTest(field=field):
                changed = {**self.query, field: value}
                self.assertNotEqual(self.cache.path_for(changed), self.cache.path_for(self.query))

    def test_corruption_or_mismatched_entry_is_reported(self):
        path = self.cache.path_for(self.query)
        for content in ("not-json", "null", "{}", json.dumps({"schema_version": 1, "query": self.query, "data": {}, "fetched_at": "not-a-date"})):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(CacheError):
                    self.cache.read(self.query)

    def test_atomic_failure_preserves_previous_bytes(self):
        self.cache.write(self.query, {"synthetic": 1}, self.timestamp)
        path = self.cache.path_for(self.query)
        original = path.read_bytes()
        with patch("services.providers.cache.os.replace", side_effect=OSError("simulated write failure")):
            with self.assertRaises(OSError):
                self.cache.write(self.query, {"synthetic": 2}, self.timestamp)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(path.parent.glob(".tmp-*")), [])

    def test_nonfinite_data_never_overwrites_existing_file(self):
        self.cache.write(self.query, {"synthetic": 1}, self.timestamp)
        path = self.cache.path_for(self.query)
        original = path.read_bytes()
        with self.assertRaises(ValueError):
            self.cache.write(self.query, {"synthetic": float("nan")}, self.timestamp)
        self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
