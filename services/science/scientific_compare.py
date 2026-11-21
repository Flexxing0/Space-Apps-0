"""Comparación descriptiva de series nativas; no agrega inferencia estadística."""

from datetime import datetime,timezone

from services.api_service import ServiceError
from services.providers.bulk import validate_period


def compare(service,payload):
    if not isinstance(payload,dict) or set(payload)-{'selections','start_year','end_year','target_unit'}:
        raise ServiceError('invalid_request','Usar dos selections, período y target_unit opcional.')
    selections=payload.get('selections')
    if not isinstance(selections,list) or len(selections)!=2:
        raise ServiceError('invalid_request','La comparación requiere exactamente dos selecciones.')
    start,end=payload.get('start_year',2000),payload.get('end_year',2024)
    try:
        validate_period(start,end)
        if end>datetime.now(timezone.utc).year:raise ValueError()
    except ValueError:raise ServiceError('invalid_request','Período inválido.') from None
    available={(v['provider'],v['variable']) for v in service.variables()}
    for selection in selections:
        if not isinstance(selection,dict) or set(selection)!={'provider','city_id','variable'} or any(not isinstance(v,str) for v in selection.values()):
            raise ServiceError('invalid_request','Cada selección requiere provider, city_id y variable; no se admiten coordenadas libres.')
        service.data_service.get_city(selection['city_id'])
        if (selection['provider'],selection['variable']) not in available:
            raise ServiceError('provider_not_verified','La variable no tiene observaciones verificadas en esta instalación.')
    same_variable=selections[0]['provider']==selections[1]['provider'] and selections[0]['variable']==selections[1]['variable']
    precipitation={(s['provider'],s['variable']) for s in selections}=={('power','PRECTOTCORR'),('gpm','precipitation')}
    if not same_variable and not precipitation:
        raise ServiceError('incompatible_analysis','Seleccionar la misma variable/producto o la comparación de precipitación POWER–GPM.')
    if precipitation and payload.get('target_unit')!='mm/day':
        raise ServiceError('invalid_request','La comparación POWER–GPM requiere target_unit="mm/day" para convertir unidades explícitamente.')
    sources=[service.fetch(provider=s['provider'],city_id=s['city_id'],variables=[s['variable']],start_year=start,end_year=end)[0] for s in selections]
    a,b=sources
    warnings=[]
    if a['frequency']!=b['frequency']:
        raise ServiceError('incompatible_analysis','Las frecuencias temporales son distintas; no se realizó remuestreo.')
    if same_variable and (a['product'],a['product_version'])!=(b['product'],b['product_version']):
        raise ServiceError('incompatible_analysis','Productos o versiones científicas diferentes.')
    if any(r['product_version'] is None for r in sources):warnings.append('La versión científica no está declarada en alguna fuente; comparación descriptiva con esa limitación.')
    if precipitation:warnings.append('POWER e IMERG usan grillas y métodos diferentes; no son productos intercambiables ni prueban causalidad.')
    target=payload.get('target_unit',a['unit'])
    plots=[]
    for record in sources:
        unit=record['unit']
        if target==unit:factor=1
        elif target=='mm/day' and record['provider']=='gpm' and unit=='mm/hr':factor=24
        else:raise ServiceError('incompatible_analysis','Conversión de unidades no admitida; no se modificaron observaciones.')
        if record['metadata'].get('precision_note'):warnings.append(record['metadata']['precision_note'])
        plots.append({'city':record['location'],'variable':record['variable'],'source_unit':unit,'display_unit':target,'factor':factor,
                      'series':[{'date':p['date'],'value':None if p['value'] is None else p['value']*factor} for p in record['series']]})
    common=sorted(set(p['date'] for p in a['series'] if p['value'] is not None)&set(p['date'] for p in b['series'] if p['value'] is not None))
    return {'sources':sources,'plots':plots,'comparison':{'scope':'descriptive_only','statistical_test_performed':False,
            'display_unit':target,'common_available_dates':common,'warnings':list(dict.fromkeys(warnings))}}
