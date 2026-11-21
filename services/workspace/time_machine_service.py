"""Time Machine con cachés reales y motor del equipo; sin muestras ni grillas simuladas."""

from copy import deepcopy

from services.api_service import ServiceError
from services.geography.cities import list_cities
from services.providers.bulk import DEFAULT_START_YEAR, DEFAULT_END_YEAR
from services.science.trend_analysis import compute_annual_anomalies, compare_time_periods
from services.prediction.forecast_service import forecast_from_analysis,FORECAST_FIELDS


def get_argentina_cities(region=None):
    return list_cities(region=region)


class TimeMachineService:
    def __init__(self, analysis_service, scientific_service):
        self.analysis = analysis_service
        self.science = scientific_service

    def _city_analysis(self, city_id, variable, start, end):
        city=self.analysis.data_service.get_city(city_id)
        period={'start_year':start,'end_year':end}
        # El histórico precalculado evita escanear todas las cachés para cada
        # ciudad de la animación; el servicio original valida cobertura y vigencia.
        source=({'start_year':DEFAULT_START_YEAR,'end_year':DEFAULT_END_YEAR}
                if DEFAULT_START_YEAR<=start<=end<=DEFAULT_END_YEAR else period)
        try:
            data,meta=self.analysis.data_service.get_data({'city_id':city_id,'variables':[variable],**source},cache_only=True)
        except ServiceError as error:
            if error.code!='cache_unavailable':raise
            source=self.science._power_source_period(city,period)
            data,meta=self.analysis.data_service.get_data({'city_id':city_id,'variables':[variable],**source},cache_only=True)
        data=deepcopy(data);data.update(period)
        row=data['variables'][variable]
        row['series']=[p for p in row['series'] if start<=int(p['date'][:4])<=end]
        result=self.analysis._analyze(row,data,meta)
        result['provenance']['source_period']=source
        bundle=compute_annual_anomalies(result['series'],variable=variable,statistics=result['statistics'])
        return result,bundle

    def build(self,payload):
        allowed={'city_id','variable','start_year','end_year','split_year','include_regional','region'}|FORECAST_FIELDS
        if not isinstance(payload,dict) or set(payload)-allowed:
            raise ServiceError('invalid_request','Usar ciudad del catálogo y período; coordenadas libres y cuadrantes no están habilitados.')
        selection=self.analysis.selection({k:v for k,v in payload.items() if k in {'city_id','variable','start_year','end_year'}})
        start,end=selection['start_year'],selection['end_year']
        if end-start<3:raise ServiceError('invalid_request','Time Machine requiere al menos cuatro años.')
        split=payload.get('split_year')
        if split is not None and (type(split) is not int or not start+2<=split<=end-1):
            raise ServiceError('invalid_request','El corte debe dejar al menos dos años en cada época.')
        include=payload.get('include_regional',True)
        region=payload.get('region')
        if type(include) is not bool or (region is not None and (not isinstance(region,str) or not region.strip())):
            raise ServiceError('invalid_request','include_regional o región inválidos.')
        variable=selection['variables'][0]
        base,bundle=self._city_analysis(selection['city_id'],variable,start,end)
        if len(base['series'])<4:raise ServiceError('insufficient_data','La serie no contiene cuatro años válidos.')
        try:comparison=compare_time_periods(base['series'],variable=variable,split_year=split)
        except ValueError:
            raise ServiceError('insufficient_data','No hay cobertura suficiente para las dos épocas.') from None
        a={p['value'] for p in base['series'] if p['year']<comparison['split_year']}
        b={p['value'] for p in base['series'] if p['year']>=comparison['split_year']}
        if len(a)==len(b)==1 and a!=b:
            # El helper heredado devuelve p=0.0001 en este caso degenerado;
            # no publicarlo como resultado de una prueba estadística real.
            raise ServiceError('insufficient_data','No se estima significancia entre épocas constantes con valores distintos.')
        comparison['scientific_status']='provisional'
        cities=[];errors=[]
        if include:
            for city in self.analysis.data_service.list_cities(region=region):
                try:
                    result,anomalies=(base,bundle) if city['id']==base['location']['id'] else self._city_analysis(city['id'],variable,start,end)
                    stats=result['statistics']
                    cities.append({**city,'mean':anomalies['mean'],
                        **{k:stats[k] for k in ('change_per_decade','total_change','p_value','significant','direction')},
                        'by_year':{str(p['year']):{k:p[k] for k in ('value','anomaly','z_score','is_anomaly','color')} for p in anomalies['timeline']},
                        'provenance':result['provenance'],'scientific_status':'provisional'})
                except ServiceError as error:errors.append({'city_id':city['id'],'code':error.code})
        return {'is_mock':False,'scientific_status':'provisional','variable':variable,
            'variable_name':base.get('variable_name',variable),'unit':base['unit'],'display_unit':base['unit'],
            'source':base['source'],'location':base['location'],
            'period':{'start_year':start,'end_year':end,'split_year':comparison['split_year'],'n_years':len(bundle['timeline'])},
            'statistics':{**base['statistics'],'std_dev':bundle['std_dev']},'completeness':base['completeness'],
            'timeline':bundle['timeline'],'anomalies':bundle['anomalies'],'period_comparison':comparison,
            'spatial_zone':{'enabled':False,'cells':[],'reason':'Requiere límites territoriales y observaciones espaciales reales; no se simulan cuadrantes.'},
            'regional_cities':cities,'regional_errors':errors,'metadata':base['metadata'],'provenance':base['provenance'],
            'method':{**base['method'],'time_machine':{'engine_source':'origin/main ce9a1e2',
                'anomaly_baseline':'Media y desviación de los años válidos del período seleccionado',
                'period_comparison':'compare_time_periods del motor del equipo (Welch bilateral)',
                'validation_status':'pending_methodological_review'}},
            'forecast':forecast_from_analysis(base,payload),
            'capabilities':{'free_coordinates':False,'spatial_resize':False,'forecast':True},
            'conclusion':'Análisis exploratorio provisional. '+base['conclusion'],
            'limitations':[*base['method']['limitations'],'Anomalías relativas a la media del período elegido; no se atribuye causalidad.',
                'Comparación de épocas del motor de main, pendiente de revisión metodológica. No amplía la familia de Radar.']}
