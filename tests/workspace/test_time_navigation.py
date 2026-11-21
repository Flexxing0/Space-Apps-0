"""Resolución temporal con datos sintéticos de software; no son observaciones."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from app import create_app
from tests.providers.test_bulk import synthetic_payload


class TimeNavigationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.app=create_app({'TESTING':True,'CACHE_DIR':self.root/'cache'/'power','DATABASE_PATH':self.root/'events.sqlite3','POWER_REQUEST_DELAY':0})
        self.client=self.app.test_client();self.navigation=self.app.extensions['earthlens_navigation']
        self.now=datetime(2026,11,15,12,tzinfo=timezone.utc);self.navigation.clock=lambda:self.now
        self.weather=self.app.extensions['earthlens_weather']
        self.weather.series=Mock(return_value={'provider':'SOFTWARE_TEST_ONLY','product':'synthetic_forecast',
            'kind':'forecast','variable':'temperature_2m','unit':'°C','frequency':'hourly',
            'location':self.app.extensions['earthlens_service'].get_city('mendoza'),
            'series':[{'date':(self.now.replace(hour=0)+timedelta(hours=i)).isoformat(),'value':float(i)} for i in range(16*24)],
            'fetched_at':self.now.isoformat(),'issued_at':None,'spatial_resolution':{'test_only':True},'limitations':[]})

    def frame(self,**kwargs):
        params={'city_id':'mendoza','date':'2026-11-16T12:00','variable':'T2M','provider':'power','scale':'daily',**kwargs}
        return self.client.get('/api/workspace/frame',query_string=params)

    def seed(self):
        def respond(url,*,params,timeout):return Mock(json=Mock(return_value=synthetic_payload(params)))
        with patch('services.providers.power.requests.get',side_effect=respond):
            self.app.extensions['earthlens_service'].get_data({'city_id':'mendoza','start_year':2000,'end_year':2024})

    def test_root_is_the_tool_with_initially_closed_panels(self):
        html=self.client.get('/').get_data(as_text=True)
        self.assertIn('id="scrubber"',html);self.assertIn('id="map"',html)
        self.assertIn('id="inspector" aria-label="Información contextual" hidden',html)
        self.assertNotIn('home-location-map',html)

    def test_future_selection_resolves_provider_without_changing_variable(self):
        response=self.frame();self.assertEqual(response.status_code,200,response.json)
        data=response.json['data'];self.assertEqual(data['selection']['variable'],'T2M')
        self.assertEqual(data['kind'],'forecast');self.assertEqual(data['focus']['value'],36)
        self.assertEqual(self.weather.series.call_args.kwargs['variable'],'temperature_2m')

    def test_each_future_day_has_its_own_value(self):
        tomorrow=self.frame().json['data'];week=self.frame(date='2026-11-22T12:00').json['data']
        self.assertEqual(tomorrow['focus']['value'],36);self.assertEqual(week['focus']['value'],180)
        self.assertNotEqual(tomorrow['focus']['sample_date'],week['focus']['sample_date'])

    def test_historical_month_reuses_cache_and_keeps_units(self):
        self.seed()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            response=self.frame(date='2017-03-29',scale='monthly',variable='PRECTOTCORR')
        self.assertEqual(response.status_code,200,response.json)
        data=response.json['data'];self.assertEqual(data['kind'],'historical_gridded_product')
        self.assertEqual(data['focus']['sample_date'],'2017-03-01');self.assertEqual(data['focus']['unit'],'mm/day')
        self.weather.series.assert_not_called()

    def test_daily_history_uses_its_real_product_not_monthly_values(self):
        row=deepcopy(self.weather.series.return_value);row.update(kind='reanalysis',product='synthetic_daily_test',frequency='daily',unit='C',series=[{'date':'2017-03-29','value':2.0}])
        self.weather.series.return_value=row
        data=self.frame(date='2017-03-29',scale='daily').json['data']
        self.assertEqual(data['focus']['value'],2);self.assertEqual(self.weather.series.call_args.kwargs['kind'],'power-daily')

    def test_unsupported_future_variable_never_repeats_history(self):
        for provider,variable in [('gldas','SoilMoi0_10cm_inst'),('power','T2M_MAX')]:
            with self.subTest(provider=provider):
                data=self.frame(provider=provider,variable=variable).json['data']
                self.assertEqual(data['status'],'unavailable');self.assertIsNone(data['record']);self.assertIsNone(data['focus'])
        self.weather.series.assert_not_called()

    def test_far_future_is_reference_not_fake_daily_prediction(self):
        self.seed();data=self.frame(date='2030-01-15').json['data']
        self.assertEqual(data['kind'],'climatology_reference');self.assertIsNone(data['record'])
        self.assertEqual(data['climatology']['count'],25);self.assertIn('2030-01-15',data['selection']['date'])
        self.weather.series.assert_not_called()

    def test_recent_gap_and_unavailable_probability_history_are_explicit(self):
        self.assertEqual(self.frame(date='2026-11-13').json['data']['status'],'unavailable')
        self.assertEqual(self.frame(date='2017-03-29',variable='precipitation_probability').json['data']['status'],'unavailable')
        self.weather.series.assert_not_called()

    def test_provider_failure_does_not_masquerade_as_climatology(self):
        from services.api_service import ServiceError
        self.weather.series.side_effect=ServiceError('provider_timeout','Timeout público de prueba')
        response=self.frame();self.assertEqual(response.status_code,504)
        self.assertEqual(response.json['error']['code'],'provider_timeout')

    def test_null_forecast_or_date_outside_power_coverage_never_uses_previous_value(self):
        self.weather.series.return_value['series'][36]['value']=None
        data=self.frame().json['data'];self.assertEqual(data['kind'],'unavailable');self.assertIsNone(data['focus']['value'])
        self.weather.series.reset_mock()
        data=self.frame(date='1950-01-01',scale='monthly').json['data']
        self.assertEqual(data['kind'],'unavailable');self.weather.series.assert_not_called()

    def test_invalid_selection_and_geography_are_rejected_before_network(self):
        for params,code in [({'date':'not-a-date'},400),({'city_id':'paris'},404),({'scale':'minute'},400),
                ({'latitude':-45},400),({'start':'2024-01-01'},400),({'provider':'unregistered'},400)]:
            with self.subTest(params=params):self.assertEqual(self.frame(**params).status_code,code)
        self.weather.series.assert_not_called()
