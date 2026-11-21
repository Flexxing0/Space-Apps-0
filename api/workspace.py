"""Contrato de la interfaz geotemporal; conserva las APIs científicas anteriores."""
from flask import Blueprint, current_app, request, Response
from api.responses import success
from services.api_service import ServiceError
from services.workspace.workspace import incidents

workspace_api=Blueprint('workspace_api',__name__,url_prefix='/api/workspace')

@workspace_api.get('/frame')
def temporal_frame():
    allowed={'city_id','date','variable','provider','scale','start','end','mode'}
    if set(request.args)-allowed or any(len(request.args.getlist(k))!=1 for k in request.args) or not {'city_id','date'}<=set(request.args):
        raise ServiceError('invalid_request','Seleccionar ciudad y fecha; no se admiten coordenadas libres.')
    return success(current_app.extensions['earthlens_navigation'].frame(**request.args.to_dict()))

@workspace_api.get('/series')
def series():
    allowed={'city_id','variable','provider','start','end'}
    if set(request.args)-allowed or any(len(request.args.getlist(k))!=1 for k in request.args):
        raise ServiceError('invalid_request','Parámetros desconocidos o repetidos.')
    if 'city_id' not in request.args:raise ServiceError('invalid_request','Seleccionar city_id.')
    return success(current_app.extensions['earthlens_workspace'].series(**request.args.to_dict()))

@workspace_api.get('/profiles/<city_id>')
def profile(city_id):
    return success(current_app.extensions['earthlens_workspace'].profile(city_id))

@workspace_api.get('/climatology')
def climatology():
    from services.workspace.workspace import iso_date
    day=iso_date(request.args.get('date'))
    profile=current_app.extensions['earthlens_workspace'].profile(request.args.get('city_id'))
    return success({'kind':'climatology_reference','date_context':day.isoformat(),'month':day.month,
        'reference_period':profile['reference_period'],'method':profile['method'],
        'variables':{k:{'unit':v['unit'],**v['months'][day.month-1]} for k,v in profile['climatology'].items() if 'months' in v},
        'limitations':['Condiciones mensuales habituales de 2000–2024. No es pronóstico para ese día.',
            'Desvío descriptivo entre años, no intervalo de predicción.']})

@workspace_api.get('/profiles/<city_id>/connections')
def connections(city_id):return success(current_app.extensions['earthlens_workspace'].connections(city_id))

@workspace_api.get('/profiles/<city_id>/twins')
def twins(city_id):return success(current_app.extensions['earthlens_workspace'].twins(city_id))

@workspace_api.get('/profiles/<city_id>/climatology-fingerprint')
def climatological_profile(city_id):return success(current_app.extensions['earthlens_workspace'].climatology_fingerprint(city_id))

@workspace_api.get('/trends')
def trends():
    from datetime import date
    from services.workspace.workspace import iso_date
    args=request.args.to_dict()
    if set(args)-{'city_id','variable','start','end'}:raise ServiceError('invalid_request','Parámetros de tendencias desconocidos.')
    start=iso_date(args.get('start','2000-01-01'));end=iso_date(args.get('end','2024-12-31'))
    if start>end or end.year-start.year<2:raise ServiceError('insufficient_data','Se requieren al menos tres años para el motor.')
    machine=current_app.extensions['earthlens_time_machine']
    variable=args.get('variable','T2M')
    machine.analysis.selection({'city_id':args.get('city_id'),'variable':variable,'start_year':start.year,'end_year':end.year})
    if start.month!=1 or start.day!=1 or end.month!=12 or end.day!=31:
        raise ServiceError('invalid_request','El análisis anual requiere años completos; ajustar fechas al 1 de enero y 31 de diciembre.')
    base,_=machine._city_analysis(args.get('city_id'),variable,start.year,end.year)
    return success(base)

@workspace_api.get('/incidents')
def historical_incidents():
    city=request.args.get('city_id')
    if city:current_app.extensions['earthlens_service'].get_city(city)
    return success(incidents(city),meta={'absence':'Sin entradas no significa ausencia de acontecimientos reales.'})


@workspace_api.get('/report.pdf')
def scientific_report():
    from services.workspace.reports import pdf_report
    selection=request.args.to_dict()
    if set(selection)-{'city_id','city_b','variable','provider','start','end'} or 'city_id' not in selection:
        raise ServiceError('invalid_request','Seleccionar ciudad, proveedor, variable y período.')
    city_b=selection.pop('city_b',None)
    provider=selection.get('provider','power')
    if provider in {'forecast','era5','power-daily'}:
        selection['kind']={'forecast':'forecast','era5':'reanalysis','power-daily':'power-daily'}[selection.pop('provider')]
        row=current_app.extensions['earthlens_weather'].series(**selection)
    else:row=current_app.extensions['earthlens_workspace'].series(**selection)
    sections=[
        ('Producto y procedencia', {k:row.get(k) for k in ['provider','product','variable','unit','frequency','fetched_at','issued_at','provenance','spatial_resolution']}),
        ('Período',row['requested_period']),('Cobertura',row.get('quality',row.get('coverage',{}))),
        ('Acontecimientos documentados',incidents(row['location']['id'])),
        ('Método y límites',row.get('limitations',[])+['Informe descriptivo de la serie. No se atribuye causalidad.'])]
    comparison_points=None
    if city_b:
        other_selection={**selection,'city_id':city_b}
        other=(current_app.extensions['earthlens_weather'].series(**other_selection) if provider in {'forecast','era5','power-daily'}
            else current_app.extensions['earthlens_workspace'].series(**other_selection))
        if other['unit']!=row['unit'] or other['product']!=row['product'] or other['frequency']!=row['frequency']:
            raise ServiceError('incompatible_analysis','La comparación requiere producto, frecuencia y unidades iguales.')
        comparison_points=other['series']
        sections.append(('Segunda ciudad y procedencia',{k:other.get(k) for k in ['location','provider','product','unit','provenance','quality','requested_period']}))
    if provider=='power' and row['requested_period']['start'].endswith('-01-01') and row['requested_period']['end'].endswith('-12-31'):
        first=int(row['requested_period']['start'][:4]);last=int(row['requested_period']['end'][:4])
        if last-first>=3:
            try:
                machine=current_app.extensions['earthlens_time_machine']
                analysis,_=machine._city_analysis(row['location']['id'],row['variable'],first,last)
                comparison=machine.build({'city_id':row['location']['id'],'variable':row['variable'],
                    'start_year':first,'end_year':last,'include_regional':False})['period_comparison']
                sections.extend([('Tendencias del motor existente (provisionales)',analysis['statistics']),
                    ('Comparación de épocas (provisional)',comparison),('Método estadístico y limitaciones',analysis['method'])])
                if city_b:
                    other_analysis,_=machine._city_analysis(city_b,row['variable'],first,last)
                    if analysis['unit']==other_analysis['unit'] and [p['year'] for p in analysis['series']]==[p['year'] for p in other_analysis['series']]:
                        from services.science.trend_analysis import compare_two_locations
                        sections.append(('Comparación de ciudades del motor (provisional)',compare_two_locations(
                            analysis,other_analysis,analysis['location']['name'],other_analysis['location']['name'])))
            except ServiceError as error:sections.append(('Análisis estadístico no disponible',error.message))
    content=pdf_report('Informe ambiental · '+row['location']['name'],sections,
        points=row['series'],unit=row['unit'],comparison_points=comparison_points)
    return Response(content,mimetype='application/pdf',headers={'Content-Disposition':'attachment; filename="earthlens-scientific.pdf"'})
