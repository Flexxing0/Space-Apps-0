"""Órdenes MODIS simuladas de software; sin emails ni observaciones reales."""

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import Mock,patch

from scripts.data.order_modis import ModisOrders
from services.geography.cities import get_city
from services.providers.modis import BANDS,RELIABILITY,VI_QUALITY


class ModisOrderTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.service=ModisOrders(Path(temporary.name))
        self.city=get_city('mendoza')
        self.dates=[{'modis_date':'A2024001','calendar_date':'2024-01-01'}]

    def test_poll_discovers_original_combined_csv_from_child_index(self):
        city=self.city;path=self.service.path(city,2024,2024);path.parent.mkdir(parents=True)
        base='https://modis.ornl.gov/subsetdata/software-test-order/'
        doc={'state':'submitted','result_url':base.rstrip('/'),'uid':'software','city_id':city['id']}
        path.write_text(json.dumps(doc),encoding='utf-8')
        parent=Mock(status_code=200,text='<a href="'+base+'csv/">CSV</a><a href="filtered_scaled_NDVI.csv">derived</a>')
        child=Mock(status_code=200,text='<a href="../MOD13Q1.csv">Original</a><a href="../statistics_NDVI.csv">Statistics</a>')
        scientific=Mock(status_code=200,text='synthetic_software_test_only',content=b'synthetic_software_test_only')
        with patch('scripts.data.order_modis.requests.get',side_effect=[parent,child,scientific]) as network,patch.object(self.service,'import_csv'):
            result=self.service.poll(path)
        self.assertEqual(result['state'],'ready')
        self.assertEqual(network.call_args.args[0],base+'MOD13Q1.csv')

    def test_submission_uses_contact_only_in_request_and_does_not_repeat(self):
        response=Mock();response.status_code=200;response.json.return_value={'order_id':'15Nov2026_15:00:00_software-test-order','email':'software@example.invalid'}
        with patch.object(self.service.provider,'_json',return_value={'response':{'dates':self.dates}}),patch('scripts.data.order_modis.requests.get',return_value=response) as network:
            result=self.service.submit('mendoza',2024,2024,'software@example.invalid')
            again=self.service.submit('mendoza',2024,2024,'software@example.invalid')
        self.assertEqual(network.call_count,1)
        self.assertEqual(len(network.call_args.kwargs['params']['uid']),8)
        self.assertEqual(result['state'],'submitted');self.assertEqual(again,result)
        self.assertNotIn('software@example.invalid',self.service.path(self.city,2024,2024).read_text())

    def test_rejected_contact_is_redacted_and_uncertain_order_is_not_resent(self):
        response=Mock();response.status_code=400;response.text='Rejected software@example.invalid software%40example.invalid'
        with patch.object(self.service.provider,'_json',return_value={'response':{'dates':self.dates}}),patch('scripts.data.order_modis.requests.get',return_value=response):
            result=self.service.submit('mendoza',2024,2024,'software@example.invalid')
        self.assertEqual(result['state'],'rejected')
        text=self.service.path(self.city,2024,2024).read_text()
        self.assertNotIn('software@example.invalid',text);self.assertNotIn('software%40example.invalid',text)
        response=Mock();response.status_code=200;response.json.return_value={'order_id':None}
        with patch.object(self.service.provider,'_json',return_value={'response':{'dates':self.dates}}),patch('scripts.data.order_modis.requests.get',return_value=response) as network:
            result=self.service.submit('mendoza',2024,2024,'software@example.invalid',retry_rejected=True)
            self.assertEqual(result['state'],'submission_uncertain')
            self.service.submit('mendoza',2024,2024,'software@example.invalid',retry_rejected=True)
            self.assertEqual(network.call_count,1)

    def test_csv_proves_collection_and_preserves_quality(self):
        metadata=[{'band':b,'units':v+' ratio - No units','scale_factor':'0.0001','add_offset':'0','fill_value':'-3000','valid_range':'-2000 to 10000'} for v,b in BANDS.items()]
        metadata += [{'band':RELIABILITY},{'band':VI_QUALITY}]
        def source(resource):return {'response':{'products':[{'product':'MOD13Q1','resolution_meters':250}]}} if resource=='/products' else {'response':{'bands':metadata}}
        rows=[]
        for band,value in ((BANDS['NDVI'],5000),(BANDS['EVI'],2500),(RELIABILITY,0),(VI_QUALITY,2048)):
            rows.append(f'MOD13Q1.A2024001.h12v12.061.2024001000000.{band},MOD13Q1,A2024001,Lat{self.city["latitude"]}Lon{self.city["longitude"]}Samp1Line1,2024001000000,{value}')
        doc={'city_id':'mendoza','dates':self.dates,'start_year':2024,'end_year':2024,'uid':'software-test-only'}
        with patch.object(self.service.provider,'_json',side_effect=source):
            records=self.service.import_csv(doc,'\n'.join(rows),'https://example.invalid/software-test','2026-11-15T00:00:00+00:00')
        self.assertEqual(records[0]['product_version'],'061')
        self.assertTrue(records[0]['metadata']['collection_version_verified'])
        self.assertEqual(records[0]['series'][0]['value'],0.5)
        self.assertEqual(records[0]['coverage']['valid_count'],1)
        with self.assertRaises(ValueError):
            self.service.import_csv(doc,'\n'.join(rows).replace('.061.','.006.'),'https://example.invalid/software-test','2026-11-15T00:00:00+00:00')
        self.assertEqual(len(self.service.store.inventory()),2)

    def test_registering_delivery_link_and_polling_do_not_submit_another_order(self):
        response=Mock();response.status_code=200;response.json.return_value={'order_id':None}
        with patch.object(self.service.provider,'_json',return_value={'response':{'dates':self.dates}}),patch('scripts.data.order_modis.requests.get',return_value=response):
            doc=self.service.submit('mendoza',2024,2024,'software@example.invalid')
        url=f'https://modis.ornl.gov/subsetdata/15Nov2026_00:00:00_MOD13Q1_{doc["uid"]}'
        with self.assertRaises(ValueError):self.service.register_result('mendoza',2024,2024,url.replace('modis.ornl.gov','example.invalid'))
        self.service.register_result('mendoza',2024,2024,url)
        index=Mock();index.status_code=200;index.text='<a href="original-point.csv">CSV</a><a href="https://example.invalid/other.csv">external</a>'
        csv=Mock();csv.status_code=200;csv.text='software-test-csv';csv.content=b'software-test-csv'
        with patch('scripts.data.order_modis.requests.get',side_effect=[index,csv]) as network,patch.object(self.service,'import_csv') as importer:
            result=self.service.poll(self.service.path(self.city,2024,2024))
        self.assertEqual(result['state'],'ready')
        self.assertEqual(network.call_args_list[-1].args[0],url+'/original-point.csv')
        self.assertEqual(importer.call_args.args[1],'software-test-csv')
        self.assertNotIn('software@example.invalid',json.dumps(result))
