"""NetCDF y CMR sintéticos para software; nunca observaciones científicas reales."""

from datetime import datetime
from io import BytesIO
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import unquote, urlparse

from services.geography.cities import get_city
from services.api_service import ServiceError
from services.providers.gldas import VARIABLES
from services.providers.gldas_points import GldasPointClient, decode_netcdf
from services.science.scientific import ScientificStore

try:
    from scipy.io import netcdf_file
except ImportError:
    netcdf_file=None


@unittest.skipUnless(netcdf_file,'SciPy is required; available in Docker')
class GldasPointTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.store=ScientificStore(Path(temporary.name))
        self.client=GldasPointClient(self.store,request_delay=0)
        self.city=get_city('mendoza')
        self.fill=False;self.wrong_coordinates=False;self.missing_month=False;self.failed=False
        self.monthly_calls=0

    def netcdf(self,month,axes=False):
        data=BytesIO()
        source=netcdf_file(data,'w')
        latitudes=[-59.875+.25*i for i in range(600)]
        longitudes=[-179.875+.25*i for i in range(1440)]
        i=min(range(600),key=lambda n:abs(latitudes[n]-self.city['latitude']))
        j=min(range(1440),key=lambda n:abs(longitudes[n]-self.city['longitude']))
        for axis,values in (('lat',latitudes if axes else [latitudes[i]+(1 if self.wrong_coordinates else 0)]),('lon',longitudes if axes else [longitudes[j]])):
            source.createDimension(axis,len(values));v=source.createVariable(axis,'f',(axis,));v[:]=values
            v.units='degrees_north' if axis=='lat' else 'degrees_east'
        if not axes:
            source.createDimension('time',1)
            v=source.createVariable('time','d',('time',));v[:]=[(datetime(2024,month,1)-datetime(2024,1,1)).days]
            v.units='days since 2024-01-01 00:00:00';v.calendar='standard'
            for name,description in VARIABLES.items():
                v=source.createVariable(name,'f',('time','lat','lon'));v[:]=[[[-9999.0 if self.fill and month==2 else 22.5]]]
                v.units=description['unit'];v._FillValue=-9999.0;v.long_name='SOFTWARE TEST ONLY'
        source.history='SOFTWARE TEST ONLY';source.flush()
        payload=data.getvalue();source.close()
        return payload

    def respond(self,url,**kwargs):
        response=Mock();response.status_code=200;response.url=url
        if url.endswith('/collections.json'):
            response.json.return_value={'feed':{'entry':[{'short_name':'GLDAS_NOAH025_M','version_id':'2.1','id':'test-collection'}]}}
        elif url.endswith('/granules.json'):
            response.json.return_value={'feed':{'entry':[{'id':f'test-granule-{m}',
                'producer_granule_id':f'GLDAS_NOAH025_M.A2024{m:02d}.021.nc4',
                'time_start':f'2024-{m:02d}-01T00:00:00Z','time_end':f'2024-{m:02d}-28T23:59:59Z',
                'links':[{'href':f'https://opendap.earthdata.nasa.gov/collections/test/granules/GLDAS_NOAH025_M.A2024{m:02d}.021.nc4'}]}
                for m in range(1,12 if self.missing_month else 13)]}}
        else:
            query=unquote(urlparse(url).query)
            axes=query=='lat,lon'
            if not axes:
                self.monthly_calls+=1
                for code in VARIABLES:
                    self.assertIn(code+'[0][',query)
                self.assertIn('lat[',query);self.assertIn('lon[',query)
            if self.failed and not axes:
                response.status_code=503;response.text='simulated outage; no observations'
            else:
                month=int(re.search(r'A2024(\d{2})',url)[1])
                response.iter_content.return_value=[self.netcdf(month,axes=axes)]
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        return response

    def fetch(self,force=False):
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'synthetic-secret'}),patch('requests.get',side_effect=self.respond):
            return self.client.fetch(get_city('mendoza'),list(VARIABLES),{'start_year':2024,'end_year':2024},force=force)

    def test_multivariable_point_months_provenance_and_tokenless_cache(self):
        records=self.fetch()
        self.assertEqual(self.monthly_calls,12)
        self.assertEqual(len(records),5)
        for record in records:
            self.assertEqual(record['coverage'],{'expected_count':12,'valid_count':12,'missing_count':0})
            self.assertEqual(record['product_version'],'2.1')
            self.assertEqual(record['unit'],VARIABLES[record['variable']]['unit'])
            self.assertEqual(record['metadata']['effective_coordinates'],{'latitude':-32.875,'longitude':-68.875})
            self.assertNotIn('synthetic-secret',str(record))
        with patch.dict(os.environ,{},clear=True),patch('requests.get',side_effect=AssertionError('Network forbidden')):
            cached=self.client.fetch(get_city('mendoza'),list(VARIABLES),{'start_year':2024,'end_year':2024})
        self.assertEqual(cached,records)

    def test_fill_is_preserved_as_missing_and_never_zero(self):
        self.fill=True
        records=self.fetch()
        self.assertEqual(records[0]['series'][1]['raw_value'],-9999)
        self.assertIsNone(records[0]['series'][1]['value'])
        self.assertEqual(records[0]['coverage']['missing_count'],1)

    def test_missing_month_does_not_publish_series(self):
        self.missing_month=True
        with self.assertRaises(ValueError):self.fetch()
        self.assertEqual(self.store.inventory(),[])
        self.assertEqual(self.monthly_calls,0)

    def test_wrong_effective_coordinates_do_not_publish_series(self):
        self.wrong_coordinates=True
        with self.assertRaises(ValueError):self.fetch()
        self.assertEqual(self.store.inventory(),[])

    def test_failed_or_degraded_refresh_preserves_valid_series(self):
        self.fetch()
        paths=list((self.store.root/'series').glob('*/*/*/*/*.json'))
        before={p:p.read_bytes() for p in paths}
        for failure in ('provider','degraded'):
            self.failed=failure=='provider';self.fill=failure=='degraded'
            with self.assertRaises(Exception):self.fetch(force=True)
            self.assertEqual({p:p.read_bytes() for p in paths},before)

    def test_html_is_not_parsed_as_scientific_data(self):
        with self.assertRaises(ValueError):decode_netcdf(b'<html>login</html>')

    def test_upstream_403_is_not_reported_as_an_invalid_token(self):
        response=Mock();response.status_code=403
        response.text='<html><p>Failed to read DMR++ Bearer synthetic-secret</p></html>'
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with patch('requests.get',return_value=response):
            with self.assertRaises(ServiceError) as failure:
                self.client._subset('https://opendap.earthdata.nasa.gov/collections/test/granules/software-test','lat,lon','synthetic-secret',False,coordinates_only=True)
        self.assertEqual(failure.exception.code,'provider_error')
        self.assertNotIn('synthetic-secret',(self.store.root/'discovery/gldas-last-request-error.json').read_text())
        self.assertEqual(self.store.inventory(),[])


if __name__=='__main__':unittest.main()
