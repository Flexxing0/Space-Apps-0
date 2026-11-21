"""Suite de pruebas para el módulo predictivo de Earth Time Machine (services/prediction/forecast.py + /api/forecast)."""

from __future__ import annotations

import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib import error, request

from app import create_app
from pathlib import Path
import tempfile
from unittest.mock import patch,Mock
from tests.providers.test_bulk import synthetic_payload
from services.prediction.forecast import build_forecast, student_t_cdf, student_t_ppf


class ForecastUnitTest(unittest.TestCase):
    """Pruebas unitarias y de caja blanca para el motor predictivo y probabilidades."""

    def test_student_t_cdf_and_ppf_accuracy(self) -> None:
        self.assertAlmostEqual(student_t_cdf(0.0, 10), 0.5, places=6)
        self.assertAlmostEqual(student_t_ppf(0.975, 23), 2.0686576, places=4)
        self.assertAlmostEqual(student_t_cdf(2.0, 10), 0.963306, places=4)
        self.assertAlmostEqual(student_t_cdf(-1.5, 5), 0.096952, places=4)

    def test_insufficient_series_returns_unavailable(self) -> None:
        short_series = [{"year": 2021 + i, "value": 10.0 + i} for i in range(4)]
        res = build_forecast(short_series, variable="T2M")
        self.assertFalse(res["available"])
        self.assertIn("al menos 5", res["reason"])

    def test_strong_warming_trend_probabilities_and_conclusions(self) -> None:
        # Serie con tendencia clara y ruido moderado
        series = [
            {"year": 2000 + i, "value": 10.0 + 0.12 * i + (0.2 if i % 2 == 0 else -0.2)}
            for i in range(25)
        ]
        res = build_forecast(
            series,
            variable="T2M",
            forecast_start=2025,
            forecast_end=2034,
            custom_threshold=13.0,
            custom_direction="above",
            location_name="Comodoro Rivadavia",
        )
        self.assertTrue(res["available"])
        self.assertEqual(res["window"]["start_year"], 2025)
        self.assertEqual(res["window"]["end_year"], 2034)
        self.assertEqual(len(res["years"]), 10)
        self.assertTrue(res["model"]["significant"])
        self.assertEqual(res["confidence"], "alta")

        # En cada año futuro: IP 95% más ancho que IC 95%, y probabilidades en [0, 1]
        for pt in res["years"]:
            self.assertLessEqual(pt["pi_low"], pt["ci_low"])
            self.assertGreaterEqual(pt["pi_high"], pt["ci_high"])
            for p in pt["probabilities"].values():
                self.assertGreaterEqual(p, 0.0)
                self.assertLessEqual(p, 1.0)

        # Con calentamiento fuerte, anomalías cálidas mucho más probables que en clima estacionario
        high_mod = res["summary"]["high_moderate"]
        self.assertGreater(high_mod["prob_at_least_one"], 0.90)
        self.assertGreater(high_mod["risk_ratio"], 2.0)
        self.assertIn("custom", res["summary"])
        self.assertGreater(len(res["conclusions"]), 4)
        self.assertIn("Comodoro Rivadavia", res["headline"])

    def test_non_significant_series_adds_exploratory_warning(self) -> None:
        # Serie oscilante sin tendencia neta
        series = [
            {"year": 2000 + i, "value": 15.0 + (1.2 if i % 2 == 0 else -1.2)}
            for i in range(20)
        ]
        res = build_forecast(series, variable="RH2M", horizon=10)
        self.assertTrue(res["available"])
        self.assertFalse(res["model"]["significant"])
        self.assertIn(res["confidence"], ("baja", "media"))
        self.assertEqual(res["conclusions"][0]["level"], "warning")
        self.assertIn("no es estadísticamente significativa", res["conclusions"][0]["text"])


class ForecastHttpTest(unittest.TestCase):
    """Software con NASA simulada y cache temporal; nunca observaciones reales."""
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.app=create_app({'TESTING':True,'CACHE_DIR':Path(temporary.name)/'power','POWER_REQUEST_DELAY':0})
        self.client=self.app.test_client()
        def respond(url,params,timeout):
            payload=synthetic_payload(params)
            for values in payload['properties']['parameter'].values():
                for date in values:values[date]+=0.08*(int(date[:4])-2000)+(0.1 if int(date[:4])%2 else -0.1)
            response=Mock();response.json.return_value=payload;return response
        with patch('services.providers.power.requests.get',side_effect=respond):
            self.assertEqual(self.client.post('/api/data',json={'city_id':'mendoza'}).status_code,200)
        self.body={'city_id':'mendoza','variable':'T2M','start_year':2000,'end_year':2024,'forecast_start':2025,'forecast_end':2032}
        self.network=patch('requests.sessions.Session.request',side_effect=AssertionError('No network'))
        self.network.start();self.addCleanup(self.network.stop)

    def test_page_and_forecast_contract_use_cached_verified_city(self):
        # La reestructuración conserva la proyección anual en la interfaz original;
        # la vista nueva presenta pronósticos operativos con un contrato separado.
        self.assertIn(b'tm_forecast.js',self.client.get('/time-machine/legacy').data)
        self.assertIn(b'workspace.js',self.client.get('/time-machine').data)
        result=self.client.post('/api/forecast',json=self.body)
        self.assertEqual(result.status_code,200)
        record=result.get_json()['data']
        self.assertTrue(record['available']);self.assertEqual(len(record['years']),8)
        self.assertEqual(record['record_type'],'model_projection')
        self.assertEqual(record['unit'],'C');self.assertEqual(record['location']['id'],'mendoza')
        self.assertEqual(record['scientific_status'],'provisional');self.assertIsNone(record['confidence'])
        self.assertEqual(record['provenance']['origin'],'cache')
        self.assertNotIn('impact',{c['kind'] for c in record['conclusions']})

    def test_time_machine_includes_projections_separate_from_observations(self):
        result=self.client.post('/api/time-machine',json={**self.body,'include_regional':False})
        self.assertEqual(result.status_code,200)
        data=result.get_json()['data']
        self.assertEqual(len(data['timeline']),25);self.assertTrue(data['forecast']['available'])
        self.assertEqual(data['forecast']['window']['end_year'],2032)

    def test_validation_rejects_injected_series_coordinates_and_nonfinite_values(self):
        for change in ({'series':[]},{'latitude':-32},{'forecast_start':True},{'forecast_end':2055},
                       {'forecast_end':2020},{'custom_threshold':float('nan')},{'custom_direction':'other'},
                       {'forecast_start':None},{'forecast_horizon':'10'}):
            self.assertEqual(self.client.post('/api/forecast',json={**self.body,**change}).status_code,400,change)

    def test_missing_cache_does_not_download_or_create_fallback(self):
        response=self.client.post('/api/forecast',json={**self.body,'city_id':'posadas'})
        self.assertEqual(response.status_code,503)
        self.assertNotIn('years',response.get_json())

    def test_custom_threshold_uses_the_same_actual_units(self):
        result=self.client.post('/api/forecast',json={**self.body,'custom_threshold':2.0,'custom_direction':'below'})
        self.assertEqual(result.status_code,200)
        self.assertIn('custom',result.get_json()['data']['summary'])

if __name__=='__main__':unittest.main()
