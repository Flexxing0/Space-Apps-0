"""Piloto OSM acotado: geometría real de calles, sin inferir riesgo o transitabilidad."""
import json
from pathlib import Path
import requests
from services.providers.cache import write_json_atomic,utc_now
from services.geography.cities import get_city

def main():
    city=get_city('comodoro-rivadavia')
    query=f'[out:json][timeout:25];way(around:1200,{city["latitude"]},{city["longitude"]})["highway"];out tags geom;'
    response=requests.get('https://overpass-api.de/api/interpreter',params={'data':query},timeout=(10,40))
    if response.status_code!=200:
        print(json.dumps({'status':'blocked','provider':'Overpass','http_status':response.status_code,'features':0,
            'reason':'Sin geometrías verificadas. No se habilita una capa de calles ni un mapa de riesgo.'}))
        return 1
    raw=response.json();features=[]
    for item in raw['elements']:
        if item.get('type')!='way' or len(item.get('geometry',[]))<2:continue
        features.append({'type':'Feature','id':item['id'],'properties':item.get('tags',{}),
            'geometry':{'type':'LineString','coordinates':[[p['lon'],p['lat']] for p in item['geometry']]}})
    if not features:raise ValueError('Sin geometría de caminos')
    document={'type':'FeatureCollection','features':features,'metadata':{'provider':'OpenStreetMap contributors',
        'access':'Overpass API','url':'https://overpass-api.de/api/interpreter','license':'ODbL 1.0',
        'attribution_url':'https://www.openstreetmap.org/copyright','fetched_at':utc_now(),
        'osm_timestamp':raw.get('osm3s',{}).get('timestamp_osm_base'),'query':query,
        'selection':'1200 m alrededor del centroide GeoRef, no cobertura completa del ejido.',
        'resolution':'Geometría vectorial colaborativa de precisión variable; no DEM ni mapa de riesgo.',
        'limitations':['La presencia de una calle no verifica su estado ni transitabilidad.','Superficie ausente permanece desconocida.']}}
    path=Path('data/cache/impact/comodoro-roads.json');write_json_atomic(path,document)
    print(json.dumps({'status':'ok','features':len(features),'with_surface_tag':sum('surface' in f['properties'] for f in features),'cache':str(path)}))
    return 0

if __name__=='__main__':raise SystemExit(main())
