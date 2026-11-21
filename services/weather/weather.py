"""Meteorología horaria/diaria, independiente de las series mensuales NASA.

Open-Meteo gratuito se utiliza sólo en el modo educativo no comercial.
La fecha de obtención jamás se hace pasar por la emisión de un modelo.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import math
import os
from threading import RLock

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from services.api_service import ServiceError
from services.providers.cache import JsonCache, utc_now, parse_timestamp
from services.workspace.workspace import iso_date

HOURLY={'temperature_2m':'°C','relative_humidity_2m':'%','apparent_temperature':'°C',
    'precipitation':'mm','precipitation_probability':'%','cloud_cover':'%',
    'wind_speed_10m':'m/s','wind_gusts_10m':'m/s','wind_direction_10m':'°','visibility':'m'}
DAILY={'T2M':'C','T2M_MAX':'C','T2M_MIN':'C','PRECTOTCORR':'mm/day','RH2M':'%','WS2M':'m/s'}


def numeric(value):
    if value is None:return None
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
        raise ValueError('Valor no numérico o no finito')
    return value


class WeatherService:
    def __init__(self, data_service, directory, *, commercial=False, session=None):
        self.data=data_service;self.cache=JsonCache(directory);self.commercial=commercial
        self.lock=RLock();self.session=session or requests.Session()
        if session is None:
            self.session.mount('https://',HTTPAdapter(max_retries=Retry(total=2,backoff_factor=1,
                status_forcelist=[429,502,503,504],allowed_methods=['GET'],respect_retry_after_header=True)))

    def bundle(self, city_id, kind='forecast', start=None, end=None, *, force=False):
        city=self.data.get_city(city_id)
        if kind not in {'forecast','reanalysis','power-daily'}:
            raise ServiceError('invalid_request','Producto meteorológico desconocido.')
        today=datetime.now(timezone.utc).date()
        first=iso_date(start or today.isoformat());last=iso_date(end or (today+timedelta(days=6)).isoformat())
        if first>last or (last-first).days>366:
            raise ServiceError('invalid_request','Consultar como máximo 367 días por petición.')
        if kind=='forecast' and (first<today or last>today+timedelta(days=15)):
            raise ServiceError('insufficient_data','La fecha queda fuera del horizonte operativo de 16 días. Consultar climatología, sin interpretarla como pronóstico.')
        if kind!='forecast' and last>=today-timedelta(days=5):
            raise ServiceError('insufficient_data','Los históricos requieren al menos cinco días de latencia; no son observaciones actuales.')
        variables=list(DAILY if kind=='power-daily' else HOURLY)
        if kind=='reanalysis':variables=[v for v in variables if v not in {'precipitation_probability','visibility'}]
        # Una extracción multivariable diaria por ciudad reutilizable para todos los eventos.
        fetch_start=today if kind=='forecast' else first
        fetch_end=today+timedelta(days=15) if kind=='forecast' else last
        query={'provider':'nasa-power' if kind=='power-daily' else 'open-meteo','product':kind,'version':1,
            'city_id':city_id,'latitude':city['latitude'],'longitude':city['longitude'],
            'variables':variables,'start':fetch_start.isoformat(),'end':fetch_end.isoformat(),
            'access':'commercial' if self.commercial else 'noncommercial'}
        with self.lock:
            previous=self.cache.read(query)
            if previous and not force and (kind!='forecast' or (datetime.now(timezone.utc)-parse_timestamp(previous['fetched_at'])).total_seconds()<3600):
                result=deepcopy(previous['data'])
            else:
                try:result=self._retrieve(city,kind,variables,fetch_start,fetch_end)
                except requests.Timeout:
                    raise ServiceError('provider_timeout','El proveedor meteorológico excedió el tiempo de espera.') from None
                except requests.RequestException:
                    raise ServiceError('provider_unavailable','El proveedor meteorológico no está disponible. La caché anterior se conserva.') from None
                except (ValueError,KeyError,TypeError):
                    raise ServiceError('provider_invalid_response','Respuesta meteorológica incompleta o inválida. No se sustituyó la caché.') from None
                if previous:
                    for code,row in previous['data']['variables'].items():
                        new={p['date']:p['value'] for p in result['variables'][code]['series']}
                        if any(p['value'] is not None and new.get(p['date']) is None for p in row['series']):
                            raise ServiceError('provider_invalid_response','La actualización pierde datos disponibles; se conserva la caché anterior.')
                self.cache.write(query,result,result['fetched_at'],location=city)
        result=deepcopy(result)
        for row in result['variables'].values():
            row['series']=[p for p in row['series'] if first.isoformat()<=p['date'][:10]<=last.isoformat()]
        result['requested_period']={'start':first.isoformat(),'end':last.isoformat()}
        return result

    def series(self, city_id, kind='forecast', variable='temperature_2m', start=None, end=None):
        allowed=DAILY if kind=='power-daily' else HOURLY
        if not isinstance(variable,str) or variable not in allowed or (kind=='reanalysis' and variable in {'precipitation_probability','visibility'}):
            raise ServiceError('invalid_request','Variable no disponible en este producto.')
        bundle=self.bundle(city_id,kind,start,end)
        row=bundle.pop('variables')[variable];points=row['series']
        return {**bundle,**row,'variable':variable,'quality':{'valid':sum(p['value'] is not None for p in points),
            'missing':sum(p['value'] is None for p in points)}}

    def _retrieve(self, city, kind, variables, first, last):
        if kind=='power-daily':
            url='https://power.larc.nasa.gov/api/temporal/daily/point'
            params={'latitude':city['latitude'],'longitude':city['longitude'],'parameters':','.join(variables),
                'community':'AG','start':first.strftime('%Y%m%d'),'end':last.strftime('%Y%m%d'),
                'format':'JSON','time-standard':'UTC'}
        else:
            if self.commercial and not os.environ.get('OPEN_METEO_API_KEY'):
                raise ServiceError('provider_auth_required','El modo comercial requiere OPEN_METEO_API_KEY y suscripción al proveedor.')
            host=('customer-api' if kind=='forecast' else 'customer-archive-api') if self.commercial else ('api' if kind=='forecast' else 'archive-api')
            url=f'https://{host}.open-meteo.com/v1/'+('forecast' if kind=='forecast' else 'archive')
            params={'latitude':city['latitude'],'longitude':city['longitude'],'hourly':','.join(variables),
                'timezone':'UTC','wind_speed_unit':'ms','start_date':first.isoformat(),'end_date':last.isoformat()}
            if kind=='reanalysis':params['models']='era5'
            if self.commercial:params['apikey']=os.environ['OPEN_METEO_API_KEY']
        response=self.session.get(url,params=params,timeout=(10,60));response.raise_for_status();raw=response.json()
        fetched=utc_now();rows={}
        if kind=='power-daily':
            params_raw=raw['properties']['parameter'];fill=raw['header'].get('fill_value',-999)
            expected=[(first+timedelta(days=i)).strftime('%Y%m%d') for i in range((last-first).days+1)]
            for code in variables:
                values=params_raw[code]
                if set(values)!=set(expected):raise ValueError('Días ausentes')
                rows[code]={'unit':raw['parameters'][code]['units'],'series':[{'date':datetime.strptime(d,'%Y%m%d').date().isoformat(),
                    'value':None if values[d]==fill else numeric(values[d])} for d in expected]}
            metadata={'header':raw['header'],'parameters':raw['parameters'],'geometry':raw.get('geometry')}
        else:
            timestamps=raw['hourly']['time'];expected_hours=((last-first).days+1)*24
            if len(timestamps)!=expected_hours or len(set(timestamps))!=len(timestamps) or timestamps!=sorted(timestamps):raise ValueError('Horas ausentes')
            expected=[datetime.combine(first,datetime.min.time())+timedelta(hours=i) for i in range(expected_hours)]
            if timestamps!=[d.isoformat(timespec='minutes') for d in expected]:raise ValueError('Grilla horaria inválida')
            for code in variables:
                values=raw['hourly'][code]
                if len(values)!=len(timestamps) or raw['hourly_units'][code]!=HOURLY[code]:raise ValueError('Unidad o longitud inesperada')
                rows[code]={'unit':raw['hourly_units'][code],'series':[{'date':stamp+':00+00:00','value':numeric(value)} for stamp,value in zip(timestamps,values)]}
            metadata={k:v for k,v in raw.items() if k not in {'hourly','hourly_units'}}
        if any(not isinstance(row['unit'],str) or not row['unit'].strip() for row in rows.values()):raise ValueError('Unidad ausente')
        if any(not any(p['value'] is not None for p in row['series']) for row in rows.values()):raise ValueError('Serie totalmente nula')
        return {'provider':'NASA POWER' if kind=='power-daily' else 'Open-Meteo',
            'product':'POWER_DAILY_AG' if kind=='power-daily' else 'best_match' if kind=='forecast' else 'ERA5',
            'kind':'forecast' if kind=='forecast' else 'reanalysis','frequency':'daily' if kind=='power-daily' else 'hourly',
            'location':city,'variables':rows,'fetched_at':fetched,'issued_at':None,
            'issuance_status':'not_provided_by_endpoint','forecast_horizon_days':16 if kind=='forecast' else None,
            'spatial_resolution':{'latitude_degrees':.5,'longitude_degrees':.625} if kind=='power-daily' else
                {'latitude_degrees':.25,'longitude_degrees':.25} if kind=='reanalysis' else {'description':'Modelos globales seleccionados por Open-Meteo; resolución variable, no inferida del centroide.'},
            'uncertainty':{'intervals':None,'status':'not_provided'},'metadata':metadata,
            'provenance':{'source_urls':[url],'requested_coordinates':{'latitude':city['latitude'],'longitude':city['longitude']},'timezone':'UTC'},
            'license':{'description':'NASA: citar POWER y fuentes de cabecera.' if kind=='power-daily' else
                'Datos CC BY 4.0; servicio con suscripción comercial.' if self.commercial else 'Datos CC BY 4.0; acceso gratuito sólo no comercial.',
                'url':'https://power.larc.nasa.gov/' if kind=='power-daily' else 'https://open-meteo.com/en/terms'},
            'limitations':['Producto de grilla; no es una estación meteorológica local.',
                'La obtención no es la emisión. Este endpoint no informa una emisión única ni intervalos de incertidumbre.',
                'No incluye alertas oficiales SMN; su estado debe verificarse por separado.']}


def official_alerts():
    return {'provider':'Servicio Meteorológico Nacional','status':'unavailable','alerts':None,
        'reason':'Contrato y acceso automatizado pendientes de verificación. No equivale a ausencia de alertas.',
        'url':'https://www.smn.gob.ar/alertas'}
