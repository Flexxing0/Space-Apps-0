"""Contrato Flask integrado: datos sintéticos sólo en cachés temporales de software."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from app import create_app
from tests.providers.test_bulk import synthetic_payload
from services.providers.bulk import make_query
from services.geography.cities import get_city


class TimeMachineTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.app=create_app({'TESTING':True,'CACHE_DIR':self.root/'power','POWER_REQUEST_DELAY':0})
        self.client=self.app.test_client()
        self.body={'city_id':'mendoza','variable':'T2M','start_year':2000,'end_year':2024,'split_year':2012,'include_regional':False}

    def seed_software_cache(self):
        def respond(url,params,timeout):
            payload=synthetic_payload(params)
            for values in payload['properties']['parameter'].values():
                for date in values:values[date]+=0.1*(int(date[:4])-2000)
            response=Mock();response.json.return_value=payload;return response
        with patch('services.providers.power.requests.get',side_effect=respond):
            response=self.client.post('/api/data',json={'city_id':'mendoza'})
            self.assertEqual(response.status_code,200)

    def test_page_and_existing_pages_are_retained(self):
        for path in ('/','/explorer','/results','/compare','/radar','/fingerprint','/missions','/sources','/time-machine'):
            self.assertEqual(self.client.get(path).status_code,200,path)

    def test_timeline_reuses_cache_and_never_creates_spatial_observations(self):
        self.seed_software_cache()
        paths=list((self.root/'power').glob('*.json'));before={p:p.read_bytes() for p in paths}
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            response=self.client.post('/api/time-machine',json=self.body)
        self.assertEqual(response.status_code,200)
        data=response.get_json()['data']
        self.assertEqual(len(data['timeline']),25)
        self.assertEqual(data['unit'],'C')
        self.assertFalse(data['is_mock']);self.assertEqual(data['scientific_status'],'provisional')
        self.assertEqual(data['spatial_zone']['cells'],[])
        self.assertFalse(data['capabilities']['spatial_resize'])
        self.assertEqual(before,{p:p.read_bytes() for p in paths})

    def test_missing_cache_returns_controlled_error_without_download_or_sample(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            response=self.client.post('/api/time-machine',json=self.body)
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.get_json()['error']['code'],'cache_unavailable')
        self.assertNotIn('timeline',response.get_json())

    def test_invalid_types_free_coordinates_and_spatial_resize_are_rejected(self):
        with patch('requests.sessions.Session.request') as network:
            for change in ({'latitude':-32},{'longitude':-68},{'lat_span':3},{'city_id':None},
                           {'start_year':True},{'split_year':2024},{'split_year':'2012'},{'include_regional':'false'}):
                self.assertEqual(self.client.post('/api/time-machine',json={**self.body,**change}).status_code,400,change)
        network.assert_not_called()

    def test_partial_period_retains_requested_years_and_original_provenance(self):
        self.seed_software_cache()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            response=self.client.post('/api/time-machine',json={**self.body,'start_year':2005,'end_year':2015,'split_year':2010})
        self.assertEqual(response.status_code,200)
        data=response.get_json()['data']
        self.assertEqual([p['year'] for p in data['timeline']],list(range(2005,2016)))
        self.assertEqual(data['provenance']['source_period'],{'start_year':2000,'end_year':2024})

    def test_get_contract_has_typed_filters_and_rejects_coordinates(self):
        self.seed_software_cache()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            result=self.client.get('/api/time-machine?city_id=mendoza&include_regional=false&split_year=2012')
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.get_json()['data']['regional_cities'],[])
            for query in ('latitude=-32','start_year=bad','include_regional=maybe'):
                self.assertEqual(self.client.get('/api/time-machine?'+query).status_code,400)

    def test_regional_missing_cities_are_reported_without_automatic_download(self):
        self.seed_software_cache()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            response=self.client.post('/api/time-machine',json={**self.body,'include_regional':True,'region':'Cuyo'})
        self.assertEqual(response.status_code,200)
        data=response.get_json()['data']
        self.assertEqual(len(data['regional_cities']),1)
        self.assertEqual(len(data['regional_errors']),2)

    def test_constant_distinct_epochs_do_not_publish_the_legacy_placeholder_p_value(self):
        self.seed_software_cache()
        city=get_city('mendoza');query=make_query(city['latitude'],city['longitude'],2000,2024)
        cache=self.app.extensions['earthlens_service'].bulk.cache
        entry=cache.read(query)
        for point in entry['data']['T2M']['series']:
            point['value']=10.0 if int(point['date'][:4])<2012 else 12.0
        cache.write(query,entry['data'],entry['fetched_at'],location=city)
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            result=self.client.post('/api/time-machine',json=self.body)
        self.assertEqual(result.status_code,422)
        self.assertEqual(result.get_json()['error']['code'],'insufficient_data')
