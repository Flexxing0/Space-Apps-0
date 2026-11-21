"""Comparación de series sintéticas de software; sin inferencia científica."""

from copy import deepcopy
from unittest.mock import Mock
import unittest

from services.api_service import ServiceError
from services.science.scientific_compare import compare
from app import create_app
import tempfile
from pathlib import Path


class CompareScientificTests(unittest.TestCase):
    def setUp(self):
        self.service=Mock()
        self.service.variables.return_value=[{'provider':'power','variable':'PRECTOTCORR'},{'provider':'gpm','variable':'precipitation'}]
        self.body={'selections':[{'provider':'power','city_id':'mendoza','variable':'PRECTOTCORR'},
                                {'provider':'gpm','city_id':'mendoza','variable':'precipitation'}],
                   'start_year':2024,'end_year':2024,'target_unit':'mm/day'}
        self.a={'provider':'power','product':'POWER','product_version':None,'variable':'PRECTOTCORR','unit':'mm/day','frequency':'monthly',
                'location':{'id':'mendoza'},'metadata':{'software_test_only':True},'series':[{'date':'2024-01-01','value':1},{'date':'2024-02-01','value':None}]}
        self.b={**deepcopy(self.a),'provider':'gpm','product':'GPM_3IMERGM','product_version':'07','variable':'precipitation','unit':'mm/hr'}
        self.service.fetch.side_effect=[[self.a],[self.b]]

    def test_precipitation_conversion_is_explicit_reversible_and_preserves_nulls(self):
        before=deepcopy(self.b)
        result=compare(self.service,self.body)
        self.assertEqual(result['plots'][1]['factor'],24)
        self.assertEqual(result['plots'][1]['series'][0]['value'],24)
        self.assertIsNone(result['plots'][1]['series'][1]['value'])
        self.assertEqual(self.b,before)
        self.assertEqual(result['sources'][1]['unit'],'mm/hr')
        self.assertFalse(result['comparison']['statistical_test_performed'])

    def test_different_variables_or_implicit_rate_conversion_are_rejected_before_fetch(self):
        for change in ('unit','variable'):
            body=deepcopy(self.body)
            if change=='unit':body.pop('target_unit')
            else:body['selections'][1]['variable']='SOIL'
            with self.subTest(change=change),self.assertRaises(ServiceError):compare(self.service,body)
        self.service.fetch.assert_not_called()

    def test_http_contract_returns_original_sources_and_controlled_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            app=create_app({'TESTING':True,'CACHE_DIR':Path(directory)/'power'})
            app.extensions['earthlens_science']=self.service
            client=app.test_client()
            response=client.post('/api/science/compare',json=self.body)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.get_json()['data']['sources'][1]['unit'],'mm/hr')
            self.assertEqual(response.get_json()['meta']['scope'],'descriptive_only')
            for change in ({'selections':[]},{'start_year':True},{'latitude':-32},{'target_unit':None}):
                self.assertEqual(client.post('/api/science/compare',json={**self.body,**change}).status_code,400)

    def test_native_frequency_or_product_changes_cannot_be_silently_compared(self):
        self.b['frequency']='16-day composite'
        with self.assertRaises(ServiceError) as error:compare(self.service,self.body)
        self.assertEqual(error.exception.code,'incompatible_analysis')
