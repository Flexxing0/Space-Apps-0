"""Comprobación optativa de períodos parciales con observaciones reales y red bloqueada."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from app import create_app
from services.science.scientific_compare import compare


def main():
    paths=list(Path('data/cache/power').glob('*.json'))+[Path('data/cache/radar/latest.json'),Path('services/science/trend_analysis.py')]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    service=create_app().extensions['earthlens_science']
    checks=[]
    with patch('requests.sessions.Session.request',side_effect=AssertionError('Network forbidden during cache verification')):
        for city in ('mendoza','comodoro-rivadavia','posadas'):
            gldas=service.fetch(provider='gldas',city_id=city,variables=['SoilMoi0_10cm_inst','Evap_tavg'],start_year=2005,end_year=2010)
            assert all(len(r['series'])==72 and r['coverage']['valid_count']==72 for r in gldas)
            assert all(r['provenance']['cache_selection']['source_period']=={'start_year':2000,'end_year':2024} for r in gldas)
            comparison=compare(service,{'selections':[{'provider':'power','city_id':city,'variable':'PRECTOTCORR'},
                {'provider':'gpm','city_id':city,'variable':'precipitation'}],
                'start_year':2005,'end_year':2010,'target_unit':'mm/day'})
            assert all(len(p['series'])==72 for p in comparison['plots'])
            assert [p['factor'] for p in comparison['plots']]==[1,24]
            checks.append({'city_id':city,'period':'2005–2010','gldas_series':2,'comparison_series':2,'records_per_series':72})
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    print(json.dumps({'status':'ok','network_blocked':True,'protected_hashes_unchanged':True,'checks':checks},ensure_ascii=True))


if __name__=='__main__':main()
