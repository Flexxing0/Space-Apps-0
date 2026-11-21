"""Hydrocron simulado para software; sin observaciones reales de respaldo."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.providers.cache import utc_now
from services.science.hydrology import HydrologyService,normalize,FILL
from app import create_app
import requests


class HydrologyTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.feature={'id':'software-test','type':'Reach','feature_id':'synthetic-reach','country_code':'AR',
            'product':'SWOT_L2_HR_RiverSP_D','product_version':'D','sword_version':'17b','geography_source':{'software_test_only':True}}
        path=self.root/'features.json';path.write_text(json.dumps({'features':[self.feature]}))
        self.service=HydrologyService(self.root/'science',catalog_path=path)
        properties={'reach_id':'synthetic-reach','time_str':'2024-01-06T00:00:00Z','wse':'8.5','width':'100',
            'wse_u':'0.1','width_u':'2','wse_units':'m','width_units':'m','reach_q':'1','reach_q_b':'2','ice_clim_f':'0','ice_dyn_f':'-999',
            'collection_shortname':'SWOT_L2_HR_RiverSP_D','collection_version':'D','sword_version':'17b'}
        self.payload={'status':'200 OK','hits':1,'results':{'geojson':{'features':[{'properties':properties,
            'geometry':{'type':'LineString','coordinates':[[-65.3,-43.3],[-65.31,-43.31]]}}]}}}
        self.start='2024-01-01T00:00:00Z';self.end='2024-12-31T23:59:59Z'

    def normalize(self,payload=None):
        return normalize(payload or self.payload,self.feature,self.start,self.end,url='https://example.invalid/software-test',fetched_at=utc_now())

    def test_geometry_irregular_time_quality_and_units_are_preserved(self):
        doc=self.normalize();self.service.persist(doc)
        with patch('requests.get',side_effect=AssertionError('No network')):
            cached=self.service.fetch('software-test',self.start,self.end)
        self.assertEqual(cached,doc)
        self.assertEqual(doc['frequency'],'irregular_satellite_passes')
        self.assertEqual(doc['variables']['wse']['series'][0]['quality']['reach_q'],'1')
        self.assertTrue(doc['variables']['wse']['series'][0]['quality']['review_required'])
        self.assertFalse(doc['analysis']['enabled'])
        self.assertEqual(doc['variables']['width']['unit'],'m')

    def test_fill_and_degraded_refresh_preserve_valid_previous_data(self):
        doc=self.normalize();self.service.persist(doc)
        paths=list((self.root/'science').glob('**/*.json'));before={p:p.read_bytes() for p in paths}
        changed=deepcopy(self.payload);changed['results']['geojson']['features'][0]['properties']['wse']=str(FILL)
        missing=self.normalize(changed)
        self.assertIsNone(missing['variables']['wse']['series'][0]['value'])
        with self.assertRaises(ValueError):self.service.persist(missing)
        self.assertEqual(before,{p:p.read_bytes() for p in paths})

    def test_wrong_entity_or_version_never_becomes_a_series(self):
        for key,value in (('reach_id','another-reach'),('collection_version','2.0'),('sword_version','16')):
            changed=deepcopy(self.payload);changed['results']['geojson']['features'][0]['properties'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.normalize(changed)

    def test_unknown_feature_cannot_trigger_network(self):
        with patch('requests.get') as network:
            with self.assertRaises(Exception):self.service.fetch('unknown',self.start,self.end)
        network.assert_not_called()

    def client(self):
        app=create_app({'TESTING':True,'CACHE_DIR':self.root/'power'})
        app.extensions['earthlens_hydrology']=self.service
        return app.test_client()

    def test_http_cached_data_and_catalog_keep_hydrological_identity(self):
        self.service.persist(self.normalize())
        client=self.client()
        with patch('requests.get',side_effect=AssertionError('No network')):
            features=client.get('/api/science/water-features')
            response=client.post('/api/science/water-data',json={'feature_id':'software-test','start_time':self.start,'end_time':self.end})
        self.assertEqual(features.status_code,200)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_json()['meta']['location_type'],'water_feature')
        self.assertFalse(response.get_json()['data']['analysis']['enabled'])

    def test_http_rejects_coordinates_unknown_features_and_invalid_periods(self):
        client=self.client()
        body={'feature_id':'software-test','start_time':self.start,'end_time':self.end}
        with patch('requests.get') as network:
            for change in ({'latitude':-43},{'force':'false'},{'start_time':None},{'start_time':'2025-01-01'},
                           {'start_time':self.end,'end_time':self.start}):
                self.assertEqual(client.post('/api/science/water-data',json={**body,**change}).status_code,400)
            self.assertEqual(client.post('/api/science/water-data',json={**body,'feature_id':'unknown'}).status_code,404)
        network.assert_not_called()

    def test_http_timeouts_and_corrupt_responses_do_not_expose_details(self):
        client=self.client();body={'feature_id':'software-test','start_time':self.start,'end_time':self.end}
        for failure,status in ((requests.Timeout('private-secret'),504),(requests.ConnectionError('private-secret'),503),(ValueError('private-secret'),502)):
            with self.subTest(status=status),patch.object(self.service,'fetch',side_effect=failure):
                result=client.post('/api/science/water-data',json=body)
                self.assertEqual(result.status_code,status)
                self.assertNotIn('private-secret',result.get_data(as_text=True))
