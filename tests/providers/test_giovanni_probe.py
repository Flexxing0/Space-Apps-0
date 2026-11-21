"""Pruebas de software del sondeo Giovanni; no son datos científicos."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from scripts.data.probe_giovanni import probe


class GiovanniProbeTests(unittest.TestCase):
    def test_raw_response_does_not_publish_series_or_store_authorization(self):
        catalog=Mock();catalog.json.return_value={'configured_variables':['software-test-only']}
        response=Mock();response.status_code=200;response.url='https://api.giovanni.earthdata.nasa.gov/timeseries?data=software-test-only'
        response.text='SOFTWARE TEST ONLY';response.content=response.text.encode();response.headers={'Content-Type':'text/csv'}
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'EARTHDATA_TOKEN':'synthetic-secret'}),patch(
                'scripts.data.probe_giovanni.requests.get',side_effect=[catalog,response]):
            result,path=probe('mendoza','software-test-only',2024,2024,root=Path(directory))
            self.assertFalse(result['variables_enabled'])
            self.assertNotIn('synthetic-secret',path.read_text())
            self.assertEqual(list(Path(directory).glob('series/**/*.json')),[])

    def test_credential_in_remote_body_is_never_saved(self):
        catalog=Mock();catalog.json.return_value={'configured_variables':['software-test-only']}
        response=Mock();response.text='synthetic-secret'
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'EARTHDATA_TOKEN':'synthetic-secret'}),patch(
                'scripts.data.probe_giovanni.requests.get',side_effect=[catalog,response]):
            with self.assertRaises(ValueError):probe('mendoza','software-test-only',2024,2024,root=Path(directory))
            self.assertEqual(list(Path(directory).glob('**/*.json')),[])
