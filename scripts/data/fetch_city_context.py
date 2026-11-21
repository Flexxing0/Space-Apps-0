"""Contexto verificable: elevación de centroides y fotografías con atribución.

Las fotografías son ilustraciones geolocalizadas; no son observaciones ambientales.
Acceso bajo demanda explícita; no se consulta al cargar un perfil.
"""
import argparse
import html
import json
import math
import os
from pathlib import Path
import re
import time

import requests
from services.providers.cache import write_json_atomic,utc_now,DEFAULT_CACHE_DIR
from services.geography.cities import get_city,list_cities,normalize_label

ROOT=DEFAULT_CACHE_DIR.parent/'city_context'

def elevations(cities,*,force=False):
    path=ROOT/'elevation.json'
    if path.exists() and not force:return json.loads(path.read_text(encoding='utf-8'))
    commercial=os.environ.get('EARTHLENS_WEATHER_COMMERCIAL','false').lower()=='true'
    if commercial and not os.environ.get('OPEN_METEO_API_KEY'):raise ValueError('Configurar acceso comercial Open-Meteo')
    url='https://'+('customer-api' if commercial else 'api')+'.open-meteo.com/v1/elevation'
    params={'latitude':','.join(str(c['latitude']) for c in cities),'longitude':','.join(str(c['longitude']) for c in cities)}
    if commercial:params['apikey']=os.environ['OPEN_METEO_API_KEY']
    response=requests.get(url,params=params,timeout=(10,30));response.raise_for_status();values=response.json()['elevation']
    if len(values)!=len(cities) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):raise ValueError('Respuesta de elevación incompleta')
    document={'provider':'Open-Meteo','product':'Copernicus DEM GLO-90','unit':'m','spatial_resolution_m':90,
        'fetched_at':utc_now(),'source_url':'https://open-meteo.com/en/docs/elevation-api',
        'license_url':'https://open-meteo.com/en/terms','citation':'https://doi.org/10.5270/ESA-c5d3d65',
        'values':{c['id']:{'value':v,'latitude':c['latitude'],'longitude':c['longitude']} for c,v in zip(cities,values)}}
    write_json_atomic(path,document);return document

def strip_markup(value):return html.unescape(re.sub('<[^>]+>',' ',str(value))).strip()

def photo(city,*,force=False):
    path=ROOT/'photos'/f'{city["id"]}.json'
    if path.exists() and not force:return json.loads(path.read_text(encoding='utf-8'))
    params={'action':'query','generator':'geosearch','ggscoord':f'{city["latitude"]}|{city["longitude"]}',
        'ggsradius':5000,'ggslimit':20,'ggsnamespace':6,'prop':'imageinfo|coordinates',
        'iiprop':'url|extmetadata','iiurlwidth':800,'format':'json'}
    response=requests.get('https://commons.wikimedia.org/w/api.php',params=params,
        headers={'User-Agent':'EarthLens/0.2 (NASA Space Apps educational prototype)'},timeout=(10,30))
    response.raise_for_status();candidates=[]
    for page in response.json().get('query',{}).get('pages',{}).values():
        info=page.get('imageinfo',[{}])[0];meta=info.get('extmetadata',{})
        title=page['title'];license=strip_markup(meta.get('LicenseShortName',{}).get('value',''))
        description=strip_markup(meta.get('ImageDescription',{}).get('value',''))
        author=strip_markup(meta.get('Artist',{}).get('value',''))
        if not title.lower().endswith(('.jpg','.jpeg')) or not author or not page.get('coordinates'):continue
        if not (license.startswith('CC BY ') or license.startswith('CC BY-SA ') or license in {'CC0','Public domain'}):continue
        name=normalize_label(city['name']);caption=normalize_label(description or title)
        tokens=[w for w in name.split() if len(w)>2]
        if not all(word in caption for word in tokens):continue
        image_url=info.get('thumburl') or info.get('url','')
        source=info.get('descriptionurl','')
        from urllib.parse import urlparse
        if urlparse(image_url).scheme!='https' or urlparse(source).scheme!='https' or urlparse(image_url).hostname not in {'upload.wikimedia.org','thumb.wikimedia.org'} or urlparse(source).hostname!='commons.wikimedia.org':continue
        candidates.append({'city_id':city['id'],'status':'available','title':title,'caption':description[:500],
            'author':author[:500],'license':license,'license_url':meta.get('LicenseUrl',{}).get('value'),
            'image_url':image_url,'source_url':source,'coordinates':page['coordinates'][0],
            'fetched_at':utc_now(),'limitations':['Fotografía ilustrativa con fecha propia; no demuestra condiciones ambientales actuales.']})
    if not candidates:return {'city_id':city['id'],'status':'no_verified_licensed_photo'}
    # Preferencia editorial por vistas generales; nunca altera datos científicos.
    candidates.sort(key=lambda r:(not any(w in normalize_label(r['caption']+' '+r['title']) for w in ['panoram','vista','city','ciudad']),r['title']))
    result=candidates[0];write_json_atomic(path,result);return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--elevation',action='store_true');parser.add_argument('--photos',action='store_true')
    selection=parser.add_mutually_exclusive_group(required=True);selection.add_argument('--city');selection.add_argument('--all',action='store_true')
    parser.add_argument('--force',action='store_true');args=parser.parse_args(argv)
    cities=list_cities() if args.all else [get_city(args.city)]
    if not all(cities) or not (args.elevation or args.photos):parser.error('Elegir ciudad válida y --elevation/--photos')
    if args.elevation:
        # Un documento completo del catálogo evita perder valores de otras ciudades.
        try:document=elevations(list_cities(),force=args.force)
        except (requests.RequestException,ValueError,KeyError) as error:
            print(json.dumps({'status':'error','error_type':type(error).__name__,'cache_preserved':True}))
            return 1
        print(json.dumps({'elevation_points':len(document['values'])}))
    states={}
    if args.photos:
        for city in cities:
            try:result=photo(city,force=args.force);state=result['status']
            except (requests.RequestException,ValueError,KeyError):state='access_failed'
            states[state]=states.get(state,0)+1;print(json.dumps({'city_id':city['id'],'photo_status':state}),flush=True);time.sleep(1)
        print(json.dumps({'photos':states}))
    return 0

if __name__=='__main__':raise SystemExit(main())
