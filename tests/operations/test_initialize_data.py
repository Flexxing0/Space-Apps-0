"""Inicialización con reportes simulados de software, sin observaciones ni red."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.maintenance.initialize_data import initialize


class InitializeDataTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.cache_dir=Path(temporary.name)/'power'
        self.bulk=Mock();self.radar=Mock()
        data=Mock();data.bulk=self.bulk
        self.app=Mock();self.app.extensions={'earthlens_service':data,'earthlens_radar':self.radar}
        self.radar.artifact_path=self.cache_dir.parent/'radar/latest.json'
        self.bulk.collect_cities.return_value={
            'summary':{'requested':1,'succeeded':1,'failed':0,'downloaded':1,'cache_hits':0},
            'results':[{'status':'ok','data':{'T2M':{'unit':'C'}},'quality':{'T2M':{'expected_count':12,'valid_count':11,'missing_count':1}}}],
        }

    def test_success_audits_real_service_report_and_regenerates_only_from_cache(self):
        self.radar.generate.return_value={'summary':{'computed':1,'tests':1}}
        self.radar.persist.return_value={'study_id':'software-test','summary':{'computed':1,'tests':1}}
        with patch('scripts.maintenance.initialize_data.create_app',return_value=self.app):
            report,path=initialize(cache_dir=self.cache_dir,start_year=2024,end_year=2024)
        self.assertTrue(report['radar']['regenerated'])
        self.assertEqual(report['audit']['missing_records'],1)
        self.assertEqual(report['audit']['available_records'],11)
        self.bulk.collect_cities.assert_called_once_with(start_year=2024,end_year=2024,force=False)
        self.radar.generate.assert_called_once_with(start_year=2024,end_year=2024)
        self.assertNotIn('data',json.loads(path.read_text())['results'][0])

    def test_failed_or_insufficient_initialization_preserves_previous_radar(self):
        original=deepcopy(self.bulk.collect_cities.return_value)
        for failure in ('download','analysis'):
            with self.subTest(failure=failure):
                self.radar.reset_mock()
                report=deepcopy(original)
                if failure=='download':
                    report['summary']['failed']=1
                self.bulk.collect_cities.return_value=report
                self.radar.generate.return_value={'summary':{'computed':0,'tests':1}}
                with patch('scripts.maintenance.initialize_data.create_app',return_value=self.app):
                    result,path=initialize(cache_dir=self.cache_dir,start_year=2024,end_year=2024)
                self.assertFalse(result['radar']['regenerated'])
                self.radar.persist.assert_not_called()
                self.assertTrue(path.exists())


if __name__=='__main__':
    unittest.main()
