"""Inventario local reproducible: valida cachés sin red ni escritura de observaciones."""

from collections import Counter
import json
from pathlib import Path

from services.science.analysis_results import content_hash
from services.providers.bulk import validate_power_data
from services.providers.cache import DEFAULT_CACHE_DIR, JsonCache
from services.science.scientific import ScientificStore


def audit():
    root=DEFAULT_CACHE_DIR.parent
    power=JsonCache(DEFAULT_CACHE_DIR)
    store=ScientificStore(root/'science')
    groups={};invalid=[]

    def add(key,city,series,records,valid,units):
        row=groups.setdefault(key,{'cities':set(),'series':0,'records':0,'valid':0,'units':set()})
        row['cities'].add(city);row['series']+=series;row['records']+=records;row['valid']+=valid;row['units'].update(units)

    for path in power.directory.glob('*.json'):
        try:
            raw=json.loads(path.read_text(encoding='utf-8'));entry=power.read(raw['query'])
            if entry is None:raise ValueError('Invalid cache envelope')
            quality=validate_power_data(entry['data'],raw['query'])
            query=raw['query'];key=('power','POWER_MONTHLY_AG',None,'legacy',query['start_year'],query['end_year'])
            add(key,(query['latitude'],query['longitude']),len(quality),sum(q['expected_count'] for q in quality.values()),
                sum(q['valid_count'] for q in quality.values()),{r['unit'] for r in entry['data'].values()})
        except (KeyError,ValueError,TypeError,OSError):invalid.append(str(path))
    for path in (store.root/'series').glob('*/*/*/*/*.json'):
        try:
            raw=json.loads(path.read_text(encoding='utf-8'));record=store.read(raw['query'])
            if record is None:raise ValueError('Invalid scientific cache')
            if record['provider']=='power':continue # proyección; no contar dos veces POWER.
            key=(record['provider'],record['product'],record['product_version'],record['cache_version'],record['period']['start_year'],record['period']['end_year'])
            c=record['coverage'];add(key,record['location']['id'],1,c['expected_count'],c['valid_count'],{record['unit']})
        except (KeyError,ValueError,TypeError,OSError):invalid.append(str(path))
    rows=[]
    for key,row in groups.items():
        rows.append(dict(zip(('provider','product','product_version','cache_version','start_year','end_year'),key),
            cities=len(row['cities']),series=row['series'],records=row['records'],valid=row['valid'],
            missing=row['records']-row['valid'],units=sorted(row['units'])))
    hydrology=[]
    for path in (store.root/'hydrology').glob('**/*.json'):
        try:
            entry=json.loads(path.read_text(encoding='utf-8'));doc=entry['data']['document']
            if content_hash(doc)!=entry['data']['sha256']:raise ValueError('Invalid hydrology digest')
            hydrology.append({'feature_id':doc['feature']['id'],'product':doc['product'],'product_version':doc['product_version'],
                'period':doc['period'],'frequency':doc['frequency'],'variables':{code:row['coverage'] for code,row in doc['variables'].items()},
                'quality_review_required':True,'analysis_enabled':doc['analysis']['enabled']})
        except (KeyError,ValueError,TypeError,OSError):invalid.append(str(path))
    orders=Counter()
    for path in (store.root/'orders'/'modis').glob('*.json'):
        try:orders[json.loads(path.read_text(encoding='utf-8'))['state']]+=1
        except (KeyError,ValueError,OSError):invalid.append(str(path))
    return {'series_groups':rows,'hydrology':hydrology,'modis_orders':dict(orders),'invalid_cache_files':invalid,
        'counting_note':'Groups preserve access method, product version and period. Overlapping pilot/history/access variants must not be added as independent observations. POWER projections are excluded.'}


def main():
    result=audit();print(json.dumps(result,ensure_ascii=True,indent=2))
    return int(bool(result['invalid_cache_files']))


if __name__=='__main__':raise SystemExit(main())
