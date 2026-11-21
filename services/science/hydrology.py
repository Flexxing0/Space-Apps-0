"""SWOT/Hydrocron: geometrías y observaciones irregulares, separadas de ciudades."""

from datetime import datetime,timezone
import json
import math
from pathlib import Path

import requests

from services.science.analysis_results import content_hash
from services.api_service import ServiceError
from services.providers.cache import DEFAULT_CACHE_DIR,JsonCache,utc_now


CATALOG = Path(__file__).resolve().parents[2] / "data" / "water_features.json"
BASE_URL = "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries"
FIELDS = "reach_id,time_str,wse,wse_u,width,width_u,reach_q,reach_q_b,ice_clim_f,ice_dyn_f,collection_shortname,collection_version,sword_version,crid,granuleUR"
FILL = -999999999999.0  # Ejemplo oficial Hydrocron y relleno del producto SWOT.


def parse_time(value):
    if not isinstance(value,str):raise ValueError("La fecha debe ser ISO UTC")
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.tzinfo is None:raise ValueError("La fecha requiere zona horaria")
    return stamp.astimezone(timezone.utc)


def normalize(payload,feature,start,end,*,url,fetched_at):
    if payload.get('status')!='200 OK':raise ValueError('Respuesta Hydrocron no exitosa')
    observations=payload['results']['geojson']['features']
    if not observations or payload['hits']!=len(observations):raise ValueError('Respuesta Hydrocron vacía o incompleta')
    first,last=parse_time(start),parse_time(end)
    series={v:[] for v in ('wse','width')};units={};geometries={}
    for observation in observations:
        p=observation['properties'];stamp=parse_time(p['time_str'])
        if str(p['reach_id'])!=feature['feature_id'] or not first<=stamp<=last:
            raise ValueError('Entidad o fecha Hydrocron incompatible')
        if p['collection_shortname']!=feature['product'] or p['collection_version']!=feature['product_version'] or p['sword_version']!=feature['sword_version']:
            raise ValueError('Versión Hydrocron o SWORD distinta de la entidad verificada')
        geometry=observation['geometry']
        if geometry.get('type')!='LineString' or len(geometry.get('coordinates',[]))<2:raise ValueError('Falta geometría del tramo')
        key=content_hash(geometry);geometries[key]=geometry
        for variable in series:
            unit=p[variable+'_units']
            if not unit or (variable in units and units[variable]!=unit):raise ValueError('Unidades Hydrocron inconsistentes')
            units[variable]=unit
            raw=float(p[variable]);uncertainty=float(p[variable+'_u'])
            if not math.isfinite(raw) or not math.isfinite(uncertainty):raise ValueError('Observación Hydrocron no finita')
            series[variable].append({'date':stamp.isoformat(),'value':None if raw==FILL else raw,'raw_value':raw,
                'uncertainty':None if uncertainty==FILL else uncertainty,'geometry_key':key,
                'quality':{'reach_q':p['reach_q'],'reach_q_b':p['reach_q_b'],'ice_clim_f':p['ice_clim_f'],'ice_dyn_f':p['ice_dyn_f'],'review_required':True},
                'source_attributes':p})
    for rows in series.values():
        rows.sort(key=lambda p:p['date'])
        if len({p['date'] for p in rows})!=len(rows):raise ValueError('Tiempos Hydrocron duplicados; no se combinaron observaciones')
    document={'schema_version':'earthlens.hydrology-series.v1','provider':'swot','access_method':'NASA PO.DAAC Hydrocron',
        'product':feature['product'],'product_version':feature['product_version'],'sword_version':feature['sword_version'],
        'feature':feature,'period':{'start_time':start,'end_time':end},'frequency':'irregular_satellite_passes',
        'geometries':geometries,'variables':{v:{'variable':v,'unit':units[v],'series':rows,
            'coverage':{'observations':len(rows),'numeric_available':sum(p['value'] is not None for p in rows),'missing':sum(p['value'] is None for p in rows)}} for v,rows in series.items()},
        'fetched_at':fetched_at,'provenance':{'source_urls':[url],'quality_policy':'Preserve original flags; no automatic scientific acceptance.'},
        'analysis':{'enabled':False,'reason':'Irregular observations and source quality require separate methodology; no city OLS or Radar membership.'}}
    content_hash(document)
    return document


class HydrologyService:
    def __init__(self,root=None,catalog_path=CATALOG):
        self.root=Path(root or DEFAULT_CACHE_DIR.parent/'science')
        self.catalog_path=Path(catalog_path)

    def features(self):
        if not self.catalog_path.exists():return []
        rows=json.loads(self.catalog_path.read_text(encoding='utf-8'))['features']
        if any(p.get('country_code')!='AR' or not p.get('geography_source') for p in rows):raise ValueError('Catálogo hidrológico no verificado')
        return rows

    def context(self,identifier,start,end):
        feature=next((f for f in self.features() if f['id']==identifier),None)
        if feature is None:raise ServiceError('water_feature_not_found','La entidad no existe en el catálogo argentino verificado.')
        if parse_time(start)>parse_time(end) or parse_time(end)>datetime.now(timezone.utc):raise ValueError('Período hidrológico inválido')
        cache=JsonCache(self.root/'hydrology'/'hydrocron'/feature['product']/feature['product_version']/feature['id'])
        query={'feature_id':feature['feature_id'],'collection':feature['product'],'start_time':start,'end_time':end,'fields':FIELDS,'policy':'source-flags-v1'}
        return feature,cache,query

    def persist(self,document):
        f=document['feature'];_,cache,query=self.context(f['id'],document['period']['start_time'],document['period']['end_time'])
        previous=cache.read(query)
        if previous:
            before=previous['data']['document']
            for v,row in before['variables'].items():
                new={p['date']:p['value'] for p in document['variables'][v]['series']}
                if any(p['value'] is not None and new.get(p['date']) is None for p in row['series']):raise ValueError('Actualización hidrológica degradada')
        cache.write(query,{'document':document,'sha256':content_hash(document)},document['fetched_at'],location=f)

    def fetch(self,identifier,start,end,*,force=False):
        f,cache,query=self.context(identifier,start,end)
        previous=cache.read(query)
        if previous and not force:
            doc=previous['data']['document']
            if content_hash(doc)!=previous['data']['sha256']:raise ValueError('Integridad hidrológica inválida')
            return doc
        response=requests.get(BASE_URL,params={'feature':f['type'],'feature_id':f['feature_id'],'collection_name':f['product'],
            'start_time':start,'end_time':end,'fields':FIELDS,'output':'geojson'},headers={'Accept':'application/json'},timeout=(10,90))
        response.raise_for_status()
        doc=normalize(response.json(),f,start,end,url=response.url,fetched_at=utc_now())
        self.persist(doc)
        return doc
