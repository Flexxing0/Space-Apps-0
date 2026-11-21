"""Contratos multiproveedor y MODIS con respuestas sintéticas sólo de software."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from app import create_app
from services.providers.cache import utc_now
from services.geography.cities import get_city
from services.providers.modis import BANDS, RELIABILITY, VI_QUALITY, ModisProvider, decode_quality
from services.science.scientific import ScientificStore, make_record
from tests.providers.test_bulk import synthetic_payload


def software_record(value=1.0):
    return make_record(provider="test", product="product", product_version="1", cache_version="1",
        variable="variable", unit="test_unit", location=get_city("mendoza"),
        period={"start_year":2024,"end_year":2024}, frequency="test_only",
        resolution={"test_only":True}, series=[{"date":"2024-01-01","value":value}], fetched_at=utc_now(),
        metadata={"software_test_only":True}, provenance={"source_urls":["https://example.invalid/synthetic"]})


class ScientificTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ScientificStore(self.root / "science")

    def test_namespaces_and_round_trip(self):
        record = software_record()
        query = self.store.query("test","product","1","variable",record["location"],record["period"],"test-policy")
        self.store.write(query,record)
        self.assertEqual(self.store.read(query),record)
        original_path=self.store.cache("test","product","1","variable").path_for(query)
        for fields in (("other","product","1","variable"),("test","other","1","variable"),
                       ("test","product","2","variable"),("test","product","1","other")):
            self.assertNotEqual(self.store.cache(*fields).path_for(query),original_path)
        with self.assertRaises(ValueError):
            self.store.cache("test","../escape","1","variable")

    def test_degraded_update_preserves_previous(self):
        record=software_record()
        query=self.store.query("test","product","1","variable",record["location"],record["period"],"test-policy")
        self.store.write(query,record)
        path=self.store.cache("test","product","1","variable").path_for(query)
        previous=path.read_bytes()
        with self.assertRaises(ValueError):
            self.store.write(query,software_record(None))
        self.assertEqual(path.read_bytes(),previous)

    def test_changed_unit_or_wrong_identity_cannot_overwrite_valid_cache(self):
        record=software_record()
        query=self.store.query("test","product","1","variable",record["location"],record["period"],"test-policy")
        self.store.write(query,record)
        for field,value in (("unit","other_unit"),("variable","other_variable")):
            changed=deepcopy(record);changed[field]=value
            with self.assertRaises(ValueError):
                self.store.write(query,changed)
        self.assertEqual(self.store.read(query),record)

    def test_only_real_cached_usable_records_enable_catalog(self):
        self.assertEqual(self.store.inventory(),[])
        record=software_record(None)
        query=self.store.query("test","product","1","variable",record["location"],record["period"],"test-policy")
        self.store.write(query,record)
        self.assertEqual(self.store.inventory(),[])
        record=software_record()
        self.store.write(query,record)
        self.assertEqual(self.store.inventory()[0]["variable"],"variable")
        path=self.store.cache("test","product","1","variable").path_for(query)
        value=json.loads(path.read_text());value["data"]["record"]["series"][0]["value"]=999
        path.write_text(json.dumps(value))
        self.assertEqual(self.store.inventory(),[])

    def test_legacy_power_compatibility_and_additive_api(self):
        app=create_app({"TESTING":True,"CACHE_DIR":self.root/"power","POWER_REQUEST_DELAY":0})
        client=app.test_client()
        def respond(url,params,timeout):
            response=Mock();response.json.return_value=synthetic_payload(params);return response
        with patch("services.providers.power.requests.get",side_effect=respond) as network:
            legacy=client.post('/api/data',json={"city_id":"mendoza","start_year":2024,"end_year":2024})
            self.assertEqual(legacy.status_code,200)
            path=next((self.root/"power").glob('*.json'));before=path.read_bytes()
            catalog=client.get('/api/science/variables').get_json()['data']
            self.assertEqual(len(catalog),6)
            native=client.post('/api/science/data',json={"provider":"power","city_id":"mendoza","variables":["T2M"],"start_year":2024,"end_year":2024})
            self.assertEqual(native.status_code,200)
            record=native.get_json()['data'][0]
            self.assertEqual(record['unit'],'C')
            self.assertIsNone(record['product_version'])
            self.assertEqual(len(record['series']),12)
            self.assertEqual(record['series'][0]['date'],'2024-01-01')
            self.assertFalse(record['analysis']['enabled'])
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(network.call_count,1)

    def test_new_api_blocks_coordinates_bad_types_and_unverified_sources(self):
        client=create_app({"TESTING":True,"CACHE_DIR":self.root/"power"}).test_client()
        body={"provider":"modis","city_id":"mendoza","variables":["NDVI"]}
        with patch('requests.get',side_effect=AssertionError('Network forbidden')) as network:
            self.assertEqual(client.post('/api/science/data',json=body).status_code,503)
            for change in ({"latitude":-30},{"start_year":True},{"end_year":9999},{"force":"false"},{"variables":"NDVI"}):
                self.assertEqual(client.post('/api/science/data',json={**body,**change}).status_code,400)
            self.assertEqual(client.post('/api/science/data',json={**body,"city_id":"unknown"}).status_code,404)
            network.assert_not_called()

    def test_provider_failures_use_public_http_errors(self):
        app=create_app({"TESTING":True,"CACHE_DIR":self.root/"power"})
        service=app.extensions['earthlens_science']
        body={"provider":"modis","city_id":"mendoza","variables":["NDVI"]}
        failures=((requests.Timeout('private detail'),504,'provider_timeout'),
                  (requests.ConnectionError('private detail'),503,'provider_unavailable'),
                  (KeyError('private detail'),502,'provider_invalid_response'))
        with patch.object(service,'variables',return_value=[{'provider':'modis','variable':'NDVI'}]):
            for failure,status,code in failures:
                with self.subTest(code=code),patch.object(service,'fetch',side_effect=failure):
                    response=app.test_client().post('/api/science/data',json=body)
                    self.assertEqual(response.status_code,status)
                    self.assertEqual(response.get_json()['error']['code'],code)
                    self.assertNotIn('private detail',response.get_data(as_text=True))

    def test_shorter_period_uses_verified_native_cache_without_network_or_mutation(self):
        app=create_app({'TESTING':True,'CACHE_DIR':self.root/'power'})
        service=app.extensions['earthlens_science']
        original=software_record()
        original.update(provider='gldas',product='GLDAS_NOAH025_M',product_version='2.1',cache_version='2.1-giovanni-csv-v1',
                        variable='SoilMoi0_10cm_inst',period={'start_year':2023,'end_year':2024})
        original['series']=[{'date':'2023-01-01','value':1},{'date':'2024-01-01','value':None},{'date':'2024-02-01','value':2}]
        original['coverage']={'expected_count':3,'valid_count':2,'missing_count':1}
        query=service.store.query('gldas',original['product'],original['cache_version'],original['variable'],original['location'],original['period'],'software-test-only')
        service.store.write(query,original)
        paths=list(service.store.root.glob('**/*.json'));before={p:p.read_bytes() for p in paths}
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            result=app.test_client().post('/api/science/data',json={'provider':'gldas','city_id':'mendoza','variables':['SoilMoi0_10cm_inst'],'start_year':2024,'end_year':2024})
        self.assertEqual(result.status_code,200)
        record=result.get_json()['data'][0]
        self.assertEqual(record['series'],original['series'][1:])
        self.assertEqual(record['coverage'],{'expected_count':2,'valid_count':1,'missing_count':1})
        self.assertEqual(record['fetched_at'],original['fetched_at'])
        self.assertEqual(record['provenance']['cache_selection']['source_period'],original['period'])
        self.assertEqual(before,{p:p.read_bytes() for p in paths})

    def test_power_shorter_period_reuses_full_legacy_cache_without_remote_call(self):
        app=create_app({'TESTING':True,'CACHE_DIR':self.root/'power','POWER_REQUEST_DELAY':0})
        client=app.test_client()
        def respond(url,params,timeout):
            response=Mock();response.json.return_value=synthetic_payload(params);return response
        with patch('services.providers.power.requests.get',side_effect=respond):
            self.assertEqual(client.post('/api/data',json={'city_id':'mendoza','start_year':2023,'end_year':2024}).status_code,200)
        path=next((self.root/'power').glob('*.json'));before=path.read_bytes()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network')):
            result=client.post('/api/science/data',json={'provider':'power','city_id':'mendoza','variables':['T2M'],'start_year':2024,'end_year':2024})
        self.assertEqual(result.status_code,200)
        self.assertEqual(len(result.get_json()['data'][0]['series']),12)
        self.assertEqual(path.read_bytes(),before)


class ModisTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.store=ScientificStore(Path(temporary.name))
        self.provider=ModisProvider(self.store,request_delay=0)
        self.day_count=12
        self.incomplete=False

    def respond(self,url,**kwargs):
        from urllib.parse import urlparse,parse_qs
        path=urlparse(url).path;params=parse_qs(urlparse(url).query)
        metadata=[{"band":band,"units":code+" ratio - No units","scale_factor":"0.0001","add_offset":"0",
                   "fill_value":"-3000","valid_range":"-2000 to 10000"} for code,band in BANDS.items()]
        metadata += [{"band":RELIABILITY},{"band":VI_QUALITY}]
        dates=[{"calendar_date":f"2024-01-{day:02d}","modis_date":f"A2024{day:03d}"} for day in range(1,self.day_count+1)]
        if path.endswith('/products'):
            value={"products":[{"product":"MOD13Q1","frequency":"16-Day","resolution_meters":250}]}
        elif path.endswith('/bands'):
            value={"bands":metadata}
        elif path.endswith('/dates'):
            value={"dates":dates}
        else:
            start,end=int(params['startDate'][0][-3:]),int(params['endDate'][0][-3:])
            self.assertLessEqual(end-start+1,10)
            rows=[]
            for stamp in dates[start-1:end]:
                for band,raw in ((BANDS['NDVI'],5000),(BANDS['EVI'],2500),(RELIABILITY,0),(VI_QUALITY,2048)):
                    if self.incomplete and stamp['calendar_date']=='2024-01-01' and band==VI_QUALITY:
                        continue
                    rows.append({**stamp,"band":band,"data":[raw],"tile":"synthetic","proc_date":"test-only"})
            value={"nrows":1,"ncols":1,"cellsize":231.656,"xllcorner":"test","yllcorner":"test","subset":rows}
        response=Mock();response.json.return_value=value;return response

    def test_scaling_quality_chunking_and_idempotence(self):
        with patch('services.providers.modis.requests.get',side_effect=self.respond) as network:
            records=self.provider.fetch(get_city('mendoza'),['NDVI','EVI'],{'start_year':2024,'end_year':2024})
            self.assertEqual([r['series'][0]['value'] for r in records],[0.5,0.25])
            self.assertEqual(records[0]['coverage']['expected_count'],12)
            self.assertIsNone(records[0]['product_version'])
            self.assertEqual(records[0]['series'][0]['raw_value'],5000)
            self.assertEqual(network.call_count,9) # products, bands, dates, 6 bloques
            again=self.provider.fetch(get_city('mendoza'),['NDVI'],{'start_year':2024,'end_year':2024})
            self.assertEqual(again[0],records[0]);self.assertEqual(network.call_count,9)

    def test_missing_qa_never_publishes_series(self):
        self.incomplete=True
        with patch('services.providers.modis.requests.get',side_effect=self.respond):
            with self.assertRaises(ValueError):
                self.provider.fetch(get_city('mendoza'),['NDVI'],{'start_year':2024,'end_year':2024})
        self.assertEqual(self.store.inventory(),[])

    def test_quality_flags_are_not_converted_to_good_observations(self):
        self.assertTrue(decode_quality(0,2048)['accepted'])
        for reliability,quality in ((1,2048),(3,2048),(0,2049),(0,2048|256),(0,2048|1024),(0,2048|16384),(0,2048|32768),(0,-1)):
            self.assertFalse(decode_quality(reliability,quality)['accepted'])

    def test_transient_gateway_error_splits_batch_without_unbounded_retries(self):
        self.day_count=2
        failed=False
        def respond(url,**kwargs):
            nonlocal failed
            if '/subset?' in url and not failed:
                failed=True
                response=requests.Response();response.status_code=502
                raise requests.HTTPError(response=response)
            return self.respond(url,**kwargs)
        with patch('services.providers.modis.requests.get',side_effect=respond) as network:
            records=self.provider.fetch(get_city('mendoza'),['NDVI'],{'start_year':2024,'end_year':2024})
        self.assertEqual(records[0]['coverage']['valid_count'],2)
        self.assertEqual(network.call_count,6) # catálogo, bandas, fechas, fallo y dos fechas separadas

    def test_failed_single_date_never_publishes_observations(self):
        self.day_count=1
        def respond(url,**kwargs):
            if '/subset?' in url:
                response=requests.Response();response.status_code=502
                raise requests.HTTPError(response=response)
            return self.respond(url,**kwargs)
        with patch('services.providers.modis.requests.get',side_effect=respond) as network:
            with self.assertRaises(requests.HTTPError):
                self.provider.fetch(get_city('mendoza'),['NDVI'],{'start_year':2024,'end_year':2024})
        self.assertEqual(network.call_count,4)
        self.assertEqual(self.store.inventory(),[])


if __name__=='__main__':
    unittest.main()
