"""Órdenes ORNL MOD13Q1; contacto sólo en memoria, reanudación sin duplicar pedidos."""

import argparse
import csv
from io import StringIO
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import quote,quote_plus,urljoin,urlparse,unquote
from html.parser import HTMLParser

import requests

from services.science.analysis_results import content_hash
from services.providers.bulk import validate_period
from services.providers.cache import DEFAULT_CACHE_DIR,utc_now,write_json_atomic
from services.geography.cities import get_city,list_cities
from services.providers.modis import ModisProvider,PRODUCT,BANDS,RELIABILITY,VI_QUALITY,QA_POLICY,BASE_URL
from services.science.scientific import ScientificStore


class ResultLinks(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[]

    def handle_starttag(self,tag,attrs):
        if tag=='a':
            href=dict(attrs).get('href','')
            if urlparse(href).path.lower().endswith('.csv'):self.links.append(href)


class ModisOrders:
    def __init__(self,root=None):
        self.root=Path(root or DEFAULT_CACHE_DIR.parent/'science')
        self.store=ScientificStore(self.root)
        self.provider=ModisProvider(self.store)

    def path(self,city,start,end):
        return self.root/'orders'/'modis'/f'{city["id"]}-{start}-{end}.json'

    def submit(self,identifier,start,end,email,*,retry_rejected=False):
        validate_period(start,end)
        city=get_city(identifier)
        if city is None:raise ValueError('Ciudad argentina no disponible')
        if not isinstance(email,str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Configurar EARTHLENS_ORNL_EMAIL con el contacto autorizado')
        path=self.path(city,start,end)
        previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        if previous and not (retry_rejected and previous['state']=='rejected'):return previous
        response=self.provider._json(f'/{PRODUCT}/dates',{'latitude':city['latitude'],'longitude':city['longitude']})
        dates=[r for r in response['response']['dates'] if start<=int(r['calendar_date'][:4])<=end]
        if not dates:raise ValueError('El catálogo ORNL no tiene fechas para el período')
        dates.sort(key=lambda r:r['calendar_date'])
        # ORNL valida uid con maxLength=8 (respuesta real HTTP 400).
        uid=content_hash({'city':city['id'],'start':start,'end':end,'product':PRODUCT})[:8]
        doc={'uid':uid,'city_id':city['id'],'product':PRODUCT,'start_year':start,'end_year':end,
             'dates':dates,'state':'submission_uncertain','submitted_at':utc_now(),'contact_stored':False}
        if previous:doc['previous_attempts']=[*previous.get('previous_attempts',[]),{k:previous.get(k) for k in ('state','http_status','submitted_at','diagnostic')}]
        # Persistir antes del envío: una interrupción no provoca reenvíos ni correos duplicados.
        write_json_atomic(path,doc)
        params={'latitude':city['latitude'],'longitude':city['longitude'],'startDate':dates[0]['modis_date'],
                'endDate':dates[-1]['modis_date'],'kmAboveBelow':0,'kmLeftRight':0,'email':email,'uid':uid}
        try:
            response=requests.get(BASE_URL+f'/{PRODUCT}/subsetOrder',params=params,headers={'Accept':'application/json'},timeout=(10,90))
            doc['http_status']=response.status_code
            if response.status_code not in {200,201,202}:
                diagnostic=response.text
                for contact in (email,quote(email,safe=''),quote_plus(email)):
                    diagnostic=diagnostic.replace(contact,'[contact-omitted]')
                doc['diagnostic']=diagnostic[:2200]
                doc['state']='rejected';write_json_atomic(path,doc);return doc
            value=response.json()
            # No guardar URL de solicitud ni campos de contacto de la respuesta.
            text=json.dumps(value)
            for contact in (email,quote(email,safe=''),quote_plus(email)):
                text=text.replace(contact,'[contact-omitted]')
            value=json.loads(text)
            order_id=next((value[k] for k in ('order_id','orderId','orderID','orderid') if isinstance(value,dict) and isinstance(value.get(k),str)),None)
            if not order_id:
                match=re.search(r'/subsetdata/([A-Za-z0-9_.:-]+)',text)
                order_id=match[1] if match else None
            if order_id and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]+',order_id):
                doc.update(state='submitted',order_id=order_id,result_url='https://modis.ornl.gov/subsetdata/'+order_id)
            else:
                doc['response_keys']=list(value) if isinstance(value,dict) else []
                doc['safe_order_id']=order_id
            write_json_atomic(path,doc)
            return doc
        except (requests.RequestException,ValueError) as error:
            doc['error_type']=type(error).__name__;write_json_atomic(path,doc);return doc

    def poll(self,path):
        doc=json.loads(Path(path).read_text(encoding='utf-8'))
        if doc['state']=='ready':return doc
        if not doc.get('result_url'):return doc
        # Descubrir el archivo publicado en el índice; no asumir su nombre.
        index=requests.get(doc['result_url']+'/',timeout=(10,60))
        doc['last_poll_at']=utc_now();doc['result_http_status']=index.status_code
        if index.status_code!=200:
            write_json_atomic(path,doc);return doc
        parser=ResultLinks();parser.feed(index.text)
        base=doc['result_url']+'/'
        links=sorted({urljoin(base,href) for href in parser.links})
        links=[url for url in links if url.startswith(base) and not urlparse(url).query and not urlparse(url).fragment]
        # Las órdenes actuales enlazan un índice csv/ con varios derivados. Sólo
        # el CSV combinado original permite verificar gránulos, colección y QA.
        originals=[url for url in links if urlparse(url).path.rsplit('/',1)[-1]==PRODUCT+'.csv']
        if not originals and ('href="'+base+'csv/"' in index.text or 'href="csv/"' in index.text):
            child=requests.get(base+'csv/',timeout=(10,60))
            if child.status_code==200:
                child_parser=ResultLinks();child_parser.feed(child.text)
                candidates={urljoin(base+'csv/',href) for href in child_parser.links}
                originals=sorted(url for url in candidates if url==base+PRODUCT+'.csv')
        if originals:links=originals
        if len(links)!=1:
            doc['result_discovery']='CSV link absent or ambiguous';write_json_atomic(path,doc);return doc
        url=links[0]
        response=requests.get(url,timeout=(10,60))
        if response.status_code!=200 or response.text.lstrip().startswith('<'):
            doc['last_poll_at']=utc_now();doc['result_http_status']=response.status_code;write_json_atomic(path,doc);return doc
        if len(response.content)>15_000_000:raise ValueError('Resultado ORNL mayor al subconjunto puntual esperado')
        rawpath=self.root/'raw'/'modis-orders'/(doc['uid']+'.csv')
        rawpath.parent.mkdir(parents=True,exist_ok=True)
        # La respuesta científica se valida antes de publicarla.
        self.import_csv(doc,response.text,url,utc_now())
        rawpath.write_text(response.text,encoding='utf-8')
        doc.pop('result_discovery',None)
        doc.update(state='ready',retrieved_at=utc_now(),raw_csv=str(rawpath));write_json_atomic(path,doc)
        return doc

    def register_result(self,identifier,start,end,url):
        city=get_city(identifier)
        if city is None:raise ValueError('Ciudad argentina no disponible')
        path=self.path(city,start,end);doc=json.loads(path.read_text(encoding='utf-8'))
        parsed=urlparse(url);order_id=unquote(parsed.path).rstrip('/').split('/')[-1]
        if (parsed.scheme!='https' or parsed.netloc!='modis.ornl.gov' or parsed.query or parsed.fragment
                or not parsed.path.startswith('/subsetdata/') or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]+',order_id)
                or not order_id.endswith('_'+PRODUCT+'_'+doc['uid'])):
            raise ValueError('Usar el enlace oficial de la orden correspondiente a esta ciudad/período')
        if doc['state']=='ready':return doc
        doc.update(state='submitted',order_id=order_id,result_url='https://modis.ornl.gov/subsetdata/'+order_id)
        write_json_atomic(path,doc);return doc

    def import_csv(self,doc,text,url,fetched_at):
        city=get_city(doc['city_id']);expected={d['modis_date']:d for d in doc['dates']}
        rows={};collections=set();descriptor=None
        for row in csv.reader(StringIO(text)):
            if not row:continue
            if len(row) not in (6,7) or row[1]!=PRODUCT or row[2] not in expected:
                raise ValueError('CSV ORNL no corresponde a un píxel, producto o fechas esperados')
            # CSV oficial: cinco campos de identidad y un valor por píxel.
            # La banda forma parte del nombre original, no es una columna extra.
            band=row[0].split('.',5)[-1]
            if band not in {*BANDS.values(),RELIABILITY,VI_QUALITY}:continue
            if len(row)==7 and row[5]!=band:raise ValueError('Banda CSV incompatible con el gránulo original')
            match=re.fullmatch(r'MOD13Q1\.(A\d{7})\.(h\d{2}v\d{2})\.(\d{3})\.([^\.]+)\..+',row[0])
            pixel=re.fullmatch(r'Lat(-?\d+(?:\.\d+)?)Lon(-?\d+(?:\.\d+)?)Samp1Line1',row[3])
            if not match or match[1]!=row[2] or not pixel or abs(float(pixel[1])-city['latitude'])>1e-5 or abs(float(pixel[2])-city['longitude'])>1e-5:
                raise ValueError('Falta identificación por gránulo o geometría puntual ORNL')
            collections.add(match[3]);descriptor=row[3]
            day=expected[row[2]]['calendar_date'];key=(day,band)
            if key in rows:raise ValueError('Observación ORNL duplicada')
            rows[key]={'calendar_date':day,'modis_date':row[2],'band':band,'tile':match[2],'proc_date':row[4],'data':[int(row[-1])],'source_granule':row[0]}
        if len(collections)!=1:raise ValueError('Colección ausente o mezclada; no se fusionaron series')
        collection=next(iter(collections));revision=collection+'-ornl-order-v1'
        if collection!='061':raise ValueError('Colección distinta de 061; verificar metadatos y política QA antes de habilitarla')
        product=next(r for r in self.provider._json('/products')['response']['products'] if r['product']==PRODUCT)
        metadata={r['band']:r for r in self.provider._json(f'/{PRODUCT}/bands')['response']['bands']}
        grid={'cellsize':None,'nrows':1,'ncols':1,'pixel_descriptor':descriptor,'origin_reported':False}
        period={'start_year':doc['start_year'],'end_year':doc['end_year']}
        records=[]
        for code,band in BANDS.items():
            record=self.provider._record(code,band,metadata,doc['dates'],rows,grid,city,period,product,revision,[url],[fetched_at])
            record['product_version']=collection
            record['metadata']['collection_version_verified']=True
            record['metadata']['collection_version_note']='Collection identifier read from every original CSV granule name.'
            record['metadata']['order_uid']=doc['uid']
            record['metadata']['source_granules']=[rows[(d['calendar_date'],band)]['source_granule'] for d in doc['dates']]
            records.append(record)
        for record in records:self.store.write(self.store.query('modis',PRODUCT,revision,record['variable'],city,period,QA_POLICY),record)
        return records


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    selection=parser.add_mutually_exclusive_group();selection.add_argument('--city');selection.add_argument('--all',action='store_true')
    parser.add_argument('--start-year',type=int,default=2000);parser.add_argument('--end-year',type=int,default=2024)
    parser.add_argument('--poll',action='store_true');parser.add_argument('--retry-rejected',action='store_true')
    parser.add_argument('--result-url',help='Registrar enlace oficial recibido para --city sin reenviar la orden');args=parser.parse_args(argv)
    service=ModisOrders()
    if args.result_url:
        if not args.city:parser.error('--result-url requiere --city')
        result=service.register_result(args.city,args.start_year,args.end_year,args.result_url)
        print(json.dumps({k:result.get(k) for k in ('city_id','state','order_id')}));return 0
    if args.poll:
        paths=list((service.root/'orders'/'modis').glob('*.json'))
        states={};failed=0
        for path in paths:
            try:
                result=service.poll(path);states[result['state']]=states.get(result['state'],0)+1
                print(json.dumps({k:result.get(k) for k in ('city_id','state','order_id','http_status','result_http_status','result_discovery')}),flush=True)
            except Exception as error:
                failed+=1;print(json.dumps({'state':'error','error_type':type(error).__name__}),flush=True)
        print(json.dumps({'summary':{'orders':len(paths),'states':states,'failed':failed}}),flush=True)
        return int(failed>0)
    if not args.city and not args.all:parser.error('Seleccionar --city o --all; no se envían órdenes al importar')
    identifiers=[args.city] if args.city else [c['id'] for c in list_cities()]
    for identifier in identifiers:
        result=service.submit(identifier,args.start_year,args.end_year,os.environ.get('EARTHLENS_ORNL_EMAIL'),retry_rejected=args.retry_rejected)
        print(json.dumps({k:result.get(k) for k in ('city_id','state','order_id','http_status','error_type')}),flush=True)
        time.sleep(1)
    return 0


if __name__=='__main__':raise SystemExit(main())
