"""Lecturas para la interfaz unificada. Nunca descarga ni modifica históricos."""

from datetime import date
from statistics import mean, pstdev

from services.api_service import ServiceError
from services.providers.bulk import make_query, validate_power_data


def iso_date(value):
    if not isinstance(value, str):
        raise ServiceError('invalid_request', 'Usar fechas ISO YYYY-MM-DD.')
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value: raise ValueError()
        return parsed
    except ValueError:
        raise ServiceError('invalid_request', 'Fecha ISO inválida.') from None


class WorkspaceService:
    def __init__(self, data_service, science, analysis):
        self.data = data_service
        self.science = science
        self.analysis = analysis

    def series(self, city_id, variable='T2M', provider='power', start='2000-01-01', end='2024-12-31'):
        first, last = iso_date(start), iso_date(end)
        if first > last or last.year - first.year > 100:
            raise ServiceError('invalid_request', 'Intervalo inválido; máximo 100 años.')
        city = self.data.get_city(city_id)
        if provider == 'power':
            if variable not in {v['code'] for v in self.data.list_variables()}:
                raise ServiceError('invalid_request', 'Variable POWER desconocida.')
            if first.year>2024:raise ServiceError('cache_unavailable','El histórico mensual local termina en 2024; no se completan años posteriores.')
            requested={'start_year':first.year,'end_year':min(last.year,2024)}
            period={'start_year':2000,'end_year':2024} if 2000<=first.year<=min(last.year,2024)<=2024 else requested
            query = make_query(city['latitude'], city['longitude'], **period)
            entry = self.data.bulk.cache.read(query)
            if entry is None:
                period=self.science._power_source_period(city,requested)
                query=make_query(city['latitude'],city['longitude'],**period)
                entry=self.data.bulk.cache.read(query)
            if entry is None:
                raise ServiceError('cache_unavailable', 'No hay histórico mensual cacheado para este intervalo.')
            validate_power_data(entry['data'], query)
            row = entry['data'][variable]
            points = [{'date':p['date']+'-01', 'value':p['value']} for p in row['series']]
            record = {'provider':'NASA POWER','product':'POWER_MONTHLY_AG','variable':variable,
                'unit':row['unit'],'frequency':'monthly','series':points,'fetched_at':entry['fetched_at'],
                'spatial_resolution':{'latitude_degrees':0.5,'longitude_degrees':0.625},
                'metadata':row['metadata'],'provenance':{'source_urls':['https://power.larc.nasa.gov/'], 'source_period':period}}
        else:
            if provider not in {'gldas','gpm','modis'}:
                raise ServiceError('invalid_request', 'Proveedor no admitido.')
            # Sólo lecturas: una selección del mapa nunca inicia una descarga autenticada.
            records = self.science._cached_selection(provider, city, [variable],
                {'start_year':first.year,'end_year':last.year}, None)
            if not records: raise ServiceError('cache_unavailable', 'No hay una extracción compatible en caché.')
            record = records[0]
        if record['frequency']=='monthly':
            # Un mes está fechado en su primer día, pero representa el mes completo.
            selected=[p for p in record['series'] if first.strftime('%Y-%m')<=p['date'][:7]<=last.strftime('%Y-%m')]
        else:selected = [p for p in record['series'] if first <= date.fromisoformat(p['date']) <= last]
        return {**record, 'location':city,'series':selected,'requested_period':{'start':start,'end':end},
            'kind':'historical_gridded_product', 'quality':{'valid':sum(p['value'] is not None for p in selected),
            'missing':sum(p['value'] is None for p in selected)},
            'limitations':['No son mediciones de una estación local. Los huecos permanecen vacíos.',
                'Un valor mensual representa el mes, no el tiempo de un día concreto.']}

    def profile(self, city_id):
        city = self.data.get_city(city_id)
        variables = {}
        for meta in self.data.list_variables():
            code=meta['code']
            try:
                record=self.series(city_id, code)
                months=[]
                for month in range(1,13):
                    values=[p['value'] for p in record['series'] if int(p['date'][5:7])==month and p['value'] is not None]
                    months.append({'month':month,'mean':mean(values) if values else None,
                        'std_dev':pstdev(values) if values else None,'count':len(values),
                        'minimum_monthly_value':min(values) if values else None,
                        'maximum_monthly_value':max(values) if values else None})
                variables[code]={'name':meta['name'],'unit':record['unit'],'months':months,
                    'provenance':record['provenance'],'fetched_at':record['fetched_at']}
            except ServiceError as error:
                variables[code]={'status':'unavailable','code':error.code}
        native=[]
        for provider,codes in [('gldas',['SoilMoi0_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst','SoilMoi100_200cm_inst','Evap_tavg']),('gpm',['precipitation'])]:
            for code in codes:
                try:
                    r=self.series(city_id,code,provider)
                    native.append({'provider':provider,'variable':code,'unit':r['unit'],'frequency':r['frequency'],
                        'coverage':r['quality'],'provenance':r['provenance']})
                except ServiceError:continue
        general={'population':None,'altitude':None,'image':None,
            'missing_reason':'Sin fuente y licencia verificadas para los campos vacíos.'}
        import json
        root=self.data.bulk.cache.directory.parent/'city_context'
        try:
            elevation=json.loads((root/'elevation.json').read_text(encoding='utf-8'))
            point=elevation['values'][city_id]
            if point['latitude']==city['latitude'] and point['longitude']==city['longitude'] and elevation['unit']=='m':
                general['altitude']={**point,**{k:elevation.get(k) for k in ('unit','product','spatial_resolution_m','provider','source_url','fetched_at')},
                    'citation':'https://doi.org/10.5270/ESA-c5d3d65','limitation':'Elevación del píxel del centroide, no promedio ni cota oficial de toda la ciudad.'}
        except (OSError,ValueError,KeyError,TypeError):pass
        try:
            image=json.loads((root/'photos'/f'{city_id}.json').read_text(encoding='utf-8'))
            if image['city_id']==city_id and image['status']=='available':general['image']=image
        except (OSError,ValueError,KeyError,TypeError):pass
        return {'city':city,'reference_period':{'start_year':2000,'end_year':2024},
            'climatology':variables,'method':'Media aritmética de cada mes entre años disponibles; desviación poblacional descriptiva.',
            'native_variables':native,
            'fingerprint_url':'/api/fingerprint/'+city_id,'incidents':incidents(city_id),
            'general':general,
            'limitations':['Los extremos mostrados son extremos de valores mensuales, no récords diarios.',
                'POWER WS2M no incluye dirección: no se infieren vientos predominantes.',
                'Perfil por variable en su unidad; no se calcula un índice de salud ambiental.']}

    def connections(self,city_id):
        """Asociaciones descriptivas; pares coincidentes, sin p-valores ni causalidad."""
        from math import sqrt
        rows=[]
        pairs=[('power','PRECTOTCORR','gldas','SoilMoi0_10cm_inst'),('power','T2M','gldas','Evap_tavg')]
        for pa,va,pb,vb in pairs:
            try:
                a=self.series(city_id,va,pa);b=self.series(city_id,vb,pb)
                other={p['date'][:7]:p['value'] for p in b['series']}
                points=[{'date':p['date'],'x':p['value'],'y':other[p['date'][:7]]} for p in a['series'] if p['value'] is not None and other.get(p['date'][:7]) is not None]
                if len(points)<3:continue
                mx=mean(p['x'] for p in points);my=mean(p['y'] for p in points)
                denominator=sqrt(sum((p['x']-mx)**2 for p in points)*sum((p['y']-my)**2 for p in points))
                r=sum((p['x']-mx)*(p['y']-my) for p in points)/denominator if denominator else None
                rows.append({'x':{'provider':pa,'variable':va,'unit':a['unit']},'y':{'provider':pb,'variable':vb,'unit':b['unit']},
                    'pairs':points,'n':len(points),'pearson_r_descriptive':r,'inferential_test':None,
                    'provenance':[a['provenance'],b['provenance']]})
            except ServiceError:continue
        return {'city_id':city_id,'pairs':rows,'status':'exploratory',
            'limitations':['Correlación no demuestra causalidad. No se elimina estacionalidad ni autocorrelación.',
                'Productos distintos, celdas y métodos distintos. Sin prueba de significancia ni incorporación a Radar.']}

    def twins(self,city_id):
        """Distancia RMS entre climatologías mensuales estandarizadas por rasgo."""
        from math import sqrt
        self.data.get_city(city_id);vectors={};codes=['T2M','PRECTOTCORR','RH2M','WS2M']
        for city in self.data.list_cities():
            try:
                vector=[]
                for code in codes:
                    row=self.series(city['id'],code)
                    for month in range(1,13):
                        vals=[p['value'] for p in row['series'] if int(p['date'][5:7])==month and p['value'] is not None]
                        if len(vals)!=25:raise ValueError('Cobertura distinta')
                        vector.append(mean(vals))
                vectors[city['id']]=vector
            except (ServiceError,ValueError):continue
        if city_id not in vectors or len(vectors)<3:raise ServiceError('insufficient_data','No hay climatologías completas comparables.')
        scales=[pstdev(v[i] for v in vectors.values()) for i in range(48)]
        distances=[]
        for other,values in vectors.items():
            if other==city_id:continue
            terms=[((a-b)/scale)**2 for a,b,scale in zip(vectors[city_id],values,scales) if scale>0]
            distances.append({'city_id':other,'distance':sqrt(sum(terms)/len(terms)) if terms else 0,'features_used':len(terms)})
        return {'city_id':city_id,'reference_cities':sorted(vectors),'period':{'start_year':2000,'end_year':2024},
            'variables':codes,'rows':sorted(distances,key=lambda r:(r['distance'],r['city_id'])),
            'method':'48 rasgos: 12 medias mensuales × 4 variables POWER. Dividir diferencias por desvío poblacional del rasgo entre ciudades; distancia RMS. Igual peso por rasgo; omitir rasgos constantes.',
            'limitations':['Similitud descriptiva condicionada al catálogo y referencia. No indica seguridad ni salud ambiental.','No compara tendencias ni constituye inferencia estadística.']}

    def climatology_fingerprint(self,city_id):
        """Ejes Z independientes. Ninguna suma, ponderación o puntuación ambiental."""
        self.data.get_city(city_id)
        specs=[('power','T2M'),('power','PRECTOTCORR'),('power','RH2M'),('power','WS2M'),
            ('gldas','SoilMoi0_10cm_inst'),('gldas','Evap_tavg')]
        axes=[]
        for provider,variable in specs:
            references=[];selected=None
            for city in self.data.list_cities():
                try:
                    row=self.series(city['id'],variable,provider)
                    if len(row['series'])!=300 or any(p['value'] is None for p in row['series']):continue
                    value=mean(p['value'] for p in row['series'])
                    references.append({'city_id':city['id'],'mean':value})
                    if city['id']==city_id:selected=(value,row)
                except ServiceError:continue
            if not selected or len(references)<3:continue
            avg=mean(r['mean'] for r in references);sd=pstdev(r['mean'] for r in references)
            if sd==0:continue
            value,row=selected
            axes.append({'variable':variable,'provider':provider,'unit':row['unit'],'raw_mean':value,
                'z_score':(value-avg)/sd,'reference_mean':avg,'reference_std_dev':sd,
                'reference_city_ids':[r['city_id'] for r in references],'source_period':row['provenance'].get('source_period',row.get('period')),
                'product':row['product'],'product_version':row.get('product_version'),'provenance':row['provenance'],'fetched_at':row['fetched_at']})
        return {'kind':'climatological_profile_not_trend','city_id':city_id,'axes':axes,
            'period':{'start_year':2000,'end_year':2024},'method':'Media de 300 meses por eje. Z=(media de ciudad − media del catálogo)/desvío poblacional entre ciudades. Sólo ciudades con 300 meses válidos; no se combinan los ejes.',
            'limitations':['Mayor Z significa mayor magnitud de la variable, no una condición mejor o peor.',
                'Referencia dependiente del catálogo; no índice de salud, riesgo o seguridad.',
                'El Fingerprint de tendencias original conserva sus seis indicadores y metodología.']}


def incidents(city_id=None):
    rows=[{'id':'comodoro-inundacion-2017','city_id':'comodoro-rivadavia',
        'name':'Temporal e inundaciones de marzo–abril de 2017',
        'start':'2017-03-29','end':'2017-04-08','type':'flood',
        'description':'Inundaciones y procesos de erosión durante lluvias persistentes.',
        'documented_impacts':'Daños en infraestructura y propiedades; transporte de sedimentos en cursos efímeros.',
        'sources':[{'name':'IGN — El Ojo del Cóndor 14', 'url':'https://www.ign.gob.ar/odc-14-Paredes'},
            {'name':'SEGEMAR — informe geodinámico', 'url':'https://archivointemin.segemar.gov.ar/handle/308849217/5102'}],
        'reviewed_at':'2026-11-15','related_variable':'PRECTOTCORR',
        'investigate_url':'/time-machine?city_id=comodoro-rivadavia&date=2017-03-29&end=2017-04-08&variable=PRECTOTCORR&scale=daily',
        'status':'documented_incident','geometry':None}]
    return [r for r in rows if city_id is None or r['city_id']==city_id]
