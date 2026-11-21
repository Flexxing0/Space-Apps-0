from flask import Blueprint, current_app, request
from api.responses import success
from services.api_service import ServiceError
from services.weather.weather import official_alerts

weather_api=Blueprint('weather_api',__name__,url_prefix='/api')

@weather_api.get('/weather')
def weather():
    if set(request.args)-{'city_id','kind','variable','start','end'} or any(len(request.args.getlist(k))!=1 for k in request.args):
        raise ServiceError('invalid_request','Parámetros desconocidos o repetidos.')
    if 'city_id' not in request.args:raise ServiceError('invalid_request','Seleccionar city_id.')
    return success(current_app.extensions['earthlens_weather'].series(**request.args.to_dict()))

@weather_api.get('/weather/alerts')
def alerts():return success(official_alerts())

@weather_api.get('/impact')
def impact():
    from services.science.impact import impact_status
    city=current_app.extensions['earthlens_service'].get_city(request.args.get('city_id'))
    return success(impact_status(city))

@weather_api.get('/prediction/capabilities')
def predictions():
    from services.prediction.prediction import capabilities
    return success(capabilities())
