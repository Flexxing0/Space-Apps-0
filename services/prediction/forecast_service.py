"""Adapta el modelo de main a históricos reales por ciudad, sin series HTTP arbitrarias."""

import math
from services.api_service import ServiceError
from services.prediction.forecast import build_forecast, MAX_HORIZON_YEARS

FORECAST_FIELDS={'forecast_start','forecast_end','forecast_horizon','custom_threshold','custom_direction'}


def forecast_from_analysis(base,payload):
    last=base['series'][-1]['year']
    for field in ('forecast_start','forecast_end','forecast_horizon'):
        value=payload.get(field)
        if field in payload and type(value) is not int:
            raise ServiceError('invalid_request','Los años y el horizonte deben ser enteros.')
    start=payload.get('forecast_start',last+1)
    horizon=payload.get('forecast_horizon',10)
    end=payload.get('forecast_end',min(start+horizon-1,last+MAX_HORIZON_YEARS))
    if not (1<=horizon<=MAX_HORIZON_YEARS and last<start<=end<=last+MAX_HORIZON_YEARS):
        raise ServiceError('invalid_request','Usar un intervalo posterior al histórico, hasta 30 años de horizonte.')
    threshold=payload.get('custom_threshold')
    if threshold is not None and (isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not math.isfinite(threshold)):
        raise ServiceError('invalid_request','El umbral debe ser un número finito.')
    direction=payload.get('custom_direction','above')
    if direction not in ('above','below'):raise ServiceError('invalid_request','custom_direction debe ser above o below.')
    result=build_forecast(base['series'],variable=base['variable'],forecast_start=start,forecast_end=end,
                          custom_threshold=threshold,custom_direction=direction,location_name=base['location']['name'])
    result.update(scientific_status='provisional',record_type='model_projection',unit=base['unit'],
                  location=base['location'],metadata=base['metadata'],provenance=base['provenance'])
    if result.get('available'):
        # Una etiqueta heurística del modelo no equivale a validación científica.
        result['model']['confidence_heuristic']=result.get('confidence')
        result['confidence']=None
        result['validation_status']='pending_methodological_review'
        result['assumptions']=['Persistencia de tendencia lineal y variabilidad histórica',
            'Independencia interanual para la probabilidad de al menos un evento',
            'Intervalos mostrados recortados a los límites físicos definidos por el modelo']
        result['conclusions']=[c for c in result['conclusions'] if c.get('kind') not in {'impact','caveat'}]
        result['disclaimer']+=' Resultado exploratorio sin validación predictiva; no son observaciones futuras de NASA ni inferencias causales.'
    return result


class ForecastService:
    def __init__(self,time_machine):self.time_machine=time_machine

    def build(self,payload):
        allowed={'city_id','variable','start_year','end_year'}|FORECAST_FIELDS
        if not isinstance(payload,dict) or set(payload)-allowed:
            raise ServiceError('invalid_request','Usar ciudad, variable y período del catálogo; no se admiten series ni coordenadas libres.')
        selection=self.time_machine.analysis.selection({k:v for k,v in payload.items() if k not in FORECAST_FIELDS})
        base,_=self.time_machine._city_analysis(selection['city_id'],selection['variables'][0],selection['start_year'],selection['end_year'])
        result=forecast_from_analysis(base,payload)
        if not result.get('available'):raise ServiceError('insufficient_data','Se requieren al menos cinco años válidos para extrapolar.')
        return result
