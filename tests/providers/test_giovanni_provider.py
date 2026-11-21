"""CSV Giovanni sintéticos exclusivos de pruebas de software."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from services.geography.cities import get_city
from services.providers.giovanni import GiovanniMonthlyClient,parse_monthly_csv
from services.science.scientific import ScientificStore


def software_csv(missing=False):
    header='''prod_name,GLDAS_NOAH025_M.2.1
doi,software-test-only
param_short_name,SoilMoi0_10cm_inst
param_name,SOFTWARE TEST ONLY
unit,kg m-2
undef,-9999
lat,-32.875
lon,-68.875
lat_resolution,0.25
lon_resolution,0.25

Timestamp (UTC),Data
'''
    return header+''.join(f'2024-{m:02d}-01 00:00,{"-9999" if missing and m==2 else "10.125"}\n' for m in range(1,13))


class GiovanniProviderTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.store=ScientificStore(Path(temporary.name))
        self.client=GiovanniMonthlyClient(self.store,'gldas',request_delay=0)
        self.city=get_city('mendoza');self.period={'start_year':2024,'end_year':2024}

    def parse(self,text):
        return parse_monthly_csv(text,product='GLDAS_NOAH025_M',version='2.1',variable='SoilMoi0_10cm_inst',city=self.city,period=self.period)

    def test_parse_units_fill_and_native_dates_without_imputation(self):
        metadata,rows=self.parse(software_csv(missing=True))
        self.assertEqual(metadata['unit'],'kg m-2')
        self.assertEqual(len(rows),12)
        self.assertEqual(rows[0]['value'],10.125)
        self.assertIsNone(rows[1]['value'])
        self.assertEqual(rows[1]['raw_value'],-9999)

    def test_wrong_product_missing_month_wrong_cell_and_nonfinite_are_rejected(self):
        text=software_csv()
        for bad in (text.replace('GLDAS_NOAH025_M.2.1','GLDAS_NOAH025_M.2.0'),
                    text.replace('2024-02-01 00:00,10.125\n',''),text.replace('lat,-32.875','lat,-30.875'),
                    text.replace('2024-02-01 00:00,10.125','2024-02-01 00:00,nan')):
            with self.subTest(),self.assertRaises(ValueError):self.parse(bad)

    def test_gpm_grid_path_and_rate_units_remain_independent_of_power(self):
        text=software_csv().replace('GLDAS_NOAH025_M.2.1','GPM_3IMERGM.07').replace('SoilMoi0_10cm_inst','/Grid/precipitation').replace('unit,kg m-2','unit,mm/hr')
        metadata,rows=parse_monthly_csv(text,product='GPM_3IMERGM',version='07',variable='precipitation',city=self.city,period=self.period)
        self.assertEqual(metadata['param_short_name'],'/Grid/precipitation')
        self.assertEqual(metadata['unit'],'mm/hr')
        self.assertEqual(rows[0]['value'],10.125)

    def responses(self,missing=False):
        catalog=Mock();catalog.json.return_value={'configured_variables':['GLDAS_NOAH025_M_2_1_SoilMoi0_10cm_inst']}
        data=Mock();data.text=software_csv(missing);data.content=data.text.encode()
        return [catalog,data]

    def test_access_has_distinct_cache_revision_and_survives_without_token(self):
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'synthetic-secret'}),patch('requests.get',side_effect=self.responses()) as network:
            records=self.client.fetch(self.city,['SoilMoi0_10cm_inst'],self.period)
        self.assertEqual(network.call_count,2)
        self.assertEqual(records[0]['product_version'],'2.1')
        self.assertIn('giovanni',records[0]['cache_version'])
        self.assertIn('rounded',records[0]['metadata']['precision_note'])
        self.assertNotIn('synthetic-secret',str(records))
        with patch.dict(os.environ,{},clear=True),patch('requests.get',side_effect=AssertionError('No network')):
            self.assertEqual(self.client.fetch(self.city,['SoilMoi0_10cm_inst'],self.period),records)

    def test_degraded_update_cannot_replace_valid_normalized_data(self):
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'synthetic-secret'}),patch('requests.get',side_effect=self.responses()):
            self.client.fetch(self.city,['SoilMoi0_10cm_inst'],self.period)
        before={p:p.read_bytes() for p in (self.store.root/'series').glob('*/*/*/*/*.json')}
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'synthetic-secret'}),patch('requests.get',side_effect=self.responses(missing=True)[1:]):
            with self.assertRaises(ValueError):self.client.fetch(self.city,['SoilMoi0_10cm_inst'],self.period,force=True)
        self.assertEqual(before,{p:p.read_bytes() for p in before})
