"""Resuelve una selección temporal sin unir productos ni fabricar predicciones."""
from calendar import monthrange
from datetime import date as calendar_date, datetime, timedelta, timezone
from statistics import mean
import json

from services.api_service import ServiceError
from services.weather.weather import HOURLY
from services.workspace.workspace import iso_date

TO_WEATHER={'T2M':'temperature_2m','PRECTOTCORR':'precipitation',
    'RH2M':'relative_humidity_2m','WS2M':'wind_speed_10m'}
TO_POWER={value:key for key,value in TO_WEATHER.items()}
PROVIDERS={'power','power-daily','era5','forecast','gldas','gpm','modis'}
POWER_VARIABLES={'T2M','T2M_MAX','T2M_MIN','PRECTOTCORR','RH2M','WS2M'}


def selected_time(value):
    if not isinstance(value,str):raise ServiceError('invalid_request','Seleccionar una fecha ISO.')
    try:
        if len(value)==10:return datetime.combine(iso_date(value),datetime.min.time(),timezone.utc).replace(hour=12)
        point=datetime.fromisoformat(value.replace('Z','+00:00'))
        # El control HTML datetime-local está rotulado explícitamente UTC.
        return point.replace(tzinfo=timezone.utc) if point.tzinfo is None else point.astimezone(timezone.utc)
    except ValueError:raise ServiceError('invalid_request','Fecha y hora ISO inválidas.') from None


class TimeNavigationService:
    def __init__(self,workspace,weather,clock=None):
        self.workspace=workspace;self.weather=weather
        self.clock=clock or (lambda:datetime.now(timezone.utc))

    def frame(self,city_id,date,variable='T2M',provider='power',scale='daily',start=None,end=None,mode='date'):
        city=self.workspace.data.get_city(city_id)
        cursor=selected_time(date);day=cursor.date();today=self.clock().date()
        if provider not in PROVIDERS or scale not in {'hourly','daily','monthly','yearly'} or mode not in {'date','range','compare','anomaly','periods','trend'}:
            raise ServiceError('invalid_request','Fuente, escala o modo desconocidos.')
        if not isinstance(variable,str) or not variable:raise ServiceError('invalid_request','Seleccionar una variable.')
        first=iso_date(start) if start else None;last=iso_date(end) if end else None
        if (first is None)!=(last is None) or (first and (first>last or last.year-first.year>100)):
            raise ServiceError('invalid_request','Rango de análisis inválido.')
        packet={'selection':{'city_id':city_id,'date':cursor.isoformat(),'variable':variable,'provider':provider,'scale':scale},
            'location':city,'status':'available','kind':None,'record':None,'focus':None,'climatology':None,
            'message':'','effective_query':None,'timesfm_enabled':False}
        native_science=provider in {'gldas','gpm','modis'}
        weather_variable=TO_WEATHER.get(variable,variable if variable in HOURLY else None)
        power_variable=TO_POWER.get(variable,variable)
        range_contains_cursor=first is not None and first<=day<=last

        def unavailable(message):
            return {**packet,'status':'unavailable','kind':'unavailable','message':message}

        if day>=today:
            if native_science or weather_variable is None:
                return unavailable('Esta variable no tiene pronóstico operativo verificado. La fecha permanece seleccionada; no se repite el último histórico.')
            if day>today+timedelta(days=15):
                if power_variable not in TO_WEATHER:
                    return unavailable('Fuera del horizonte operativo; esta variable no tiene climatología verificada disponible.')
                historical=self.workspace.series(city_id,power_variable,'power','2000-01-01','2024-12-31')
                values=[p['value'] for p in historical['series'] if int(p['date'][5:7])==day.month and p['value'] is not None]
                if not values:return unavailable('Sin referencia climatológica para este mes.')
                packet.update(kind='climatology_reference',message='Climatología mensual 2000–2024. No es pronóstico para ese día.',
                    climatology={'month':day.month,'mean':mean(values),'count':len(values),'unit':historical['unit'],
                        'reference_period':{'start_year':2000,'end_year':2024},'provenance':historical['provenance']},
                    focus={'value':mean(values),'unit':historical['unit'],'sample_date':None,'meaning':'Media del mes entre años históricos; no observación futura.'})
                return packet
            query={'city_id':city_id,'kind':'forecast','variable':weather_variable,
                'start':today.isoformat(),'end':(today+timedelta(days=15)).isoformat()}
            row=self.weather.series(**query)
            packet['effective_query']={**query,'provider':'forecast'}
            packet['message']='Pronóstico horario · Open-Meteo. Emisión única e intervalos de incertidumbre no informados por el endpoint.'
            if variable=='WS2M':packet['message']+=' Viento a 10 m; el histórico WS2M corresponde a 2 m. No se consideran series homogéneas.'
            if variable=='PRECTOTCORR':packet['message']+=' Precipitación horaria en mm; el histórico mensual POWER permanece en mm/day.'
        elif native_science or (power_variable in POWER_VARIABLES and day.year<today.year
                and scale in {'monthly','yearly'} and provider not in {'era5','power-daily'}):
            if not native_science and day.year<1981:
                return unavailable('El producto POWER no cubre años anteriores a 1981. No se generan históricos de respaldo.')
            begin=first if range_contains_cursor else day.replace(month=1,day=1)
            finish=last if range_contains_cursor else day.replace(month=12,day=31)
            if not native_science:
                begin=max(begin,calendar_date(1981,1,1))
                finish=min(finish,calendar_date(today.year-1,12,31))
            begin,finish=begin.isoformat(),finish.isoformat()
            code=variable if native_science else power_variable
            source=provider if native_science else 'power'
            year_period=(f'{day.year}-01-01',f'{day.year}-12-31')
            try:
                row=self.workspace.series(city_id,code,source,begin,finish)
            except ServiceError as error:
                if error.code!='cache_unavailable' or (begin,finish)==year_period:raise
                begin,finish=year_period
                row=self.workspace.series(city_id,code,source,begin,finish)
            if not native_science and row['provenance']['source_period']['end_year']<day.year:
                begin,finish=year_period
                row=self.workspace.series(city_id,code,source,begin,finish)
            packet['effective_query']={'city_id':city_id,'provider':source,'variable':code,'start':begin,'end':finish}
            packet['message']='Histórico de grilla.'
            if row['frequency']=='monthly':
                packet['message']+=' La muestra mensual representa un mes completo, no un día.'
        else:
            if day>=today-timedelta(days=5):
                return unavailable('Sin histórico verificado para los últimos cinco días. No se rellenan con un pronóstico ni con el último valor disponible.')
            if power_variable not in POWER_VARIABLES and weather_variable not in HOURLY:
                return unavailable('No hay histórico verificado para esta variable.')
            begin=day.replace(day=1);finish=min(day.replace(day=monthrange(day.year,day.month)[1]),today-timedelta(days=6))
            hourly=scale=='hourly' or provider=='era5' or power_variable not in POWER_VARIABLES
            code=weather_variable if hourly else power_variable
            first_year=1940 if hourly else 1981
            if day.year<first_year:
                product='ERA5' if hourly else 'POWER'
                return unavailable(f'{product} no cubre años anteriores a {first_year}. No se generan históricos de respaldo.')
            if hourly and code in {None,'precipitation_probability','visibility'}:
                return unavailable('El histórico horario ERA5 integrado no incluye esa variable. No se fabrica una probabilidad histórica.')
            if mode=='range' and range_contains_cursor and (last-first).days<=366 and last<today-timedelta(days=5):
                begin,finish=max(first,calendar_date(first_year,1,1)),last
            query={'city_id':city_id,'kind':'reanalysis' if hourly else 'power-daily','variable':code,'start':begin.isoformat(),'end':finish.isoformat()}
            if mode!='range':
                for path in self.weather.cache.directory.glob('*.json'):
                    try:
                        cached=json.loads(path.read_text(encoding='utf-8'))['query']
                        if (cached['product']==query['kind'] and cached['city_id']==city_id
                                and cached['start']<=day.isoformat()<=cached['end'] and code in cached['variables']):
                            query.update(start=cached['start'],end=cached['end']);break
                    except (ValueError,KeyError,TypeError,OSError):continue
            row=self.weather.series(**query);packet['effective_query']={**query,'provider':'era5' if hourly else 'power-daily'}
            packet['message']='Datos históricos obtenidos del producto indicado; no se concatenan con el histórico mensual.'
        packet['record']=row;packet['kind']=row.get('kind','historical_gridded_product')
        if row['frequency']=='monthly':points=[p for p in row['series'] if p['date'][:7]==day.strftime('%Y-%m')]
        elif row['frequency']=='daily':points=[p for p in row['series'] if p['date'][:10]==day.isoformat()]
        elif row['frequency']=='hourly':points=[p for p in row['series'] if selected_time(p['date']).replace(minute=0,second=0,microsecond=0)==cursor.replace(minute=0,second=0,microsecond=0)]
        else:points=[p for p in row['series'] if p['date'][:10]==day.isoformat()]
        point=points[0] if points else None
        packet['focus']={'value':point['value'] if point else None,'unit':row['unit'],'sample_date':point['date'] if point else None,
            'meaning':'Muestra nativa del producto; no se arrastra el valor anterior a fechas sin registro.'}
        if point is None or point['value'] is None:
            packet.update(status='unavailable',kind='unavailable')
            packet['message']+=' Sin valor válido para la fecha seleccionada. El gráfico sólo muestra el contexto disponible.'
        return packet
