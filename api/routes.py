"""Rutas del Blueprint; delegan catálogo, validación y datos a los servicios."""

from flask import Blueprint, current_app, request
from werkzeug.exceptions import UnsupportedMediaType

from api.responses import success
from services.api_service import ServiceError


api = Blueprint("api", __name__, url_prefix="/api")


@api.post('/forecast')
def forecast():
    query_parameters()
    if not request.is_json:raise UnsupportedMediaType()
    result=current_app.extensions['earthlens_forecast'].build(request.get_json())
    return success(result,meta={'scientific_status':'provisional','record_type':'model_projection','origin':'cache'})


@api.post('/time-machine')
@api.get('/time-machine')
def time_machine():
    if request.method=='GET':
        payload=query_parameters(('city_id','variable','start_year','end_year','split_year','include_regional','region'))
        payload.setdefault('city_id','comodoro-rivadavia')
        try:
            for field in ('start_year','end_year','split_year'):
                if field in payload:payload[field]=int(payload[field])
            if 'include_regional' in payload:
                payload['include_regional']={'true':True,'false':False,'1':True,'0':False}[payload['include_regional'].lower()]
        except (ValueError,KeyError):
            raise ServiceError('invalid_request','Años o include_regional inválidos.') from None
    else:
        query_parameters()
        if not request.is_json:raise UnsupportedMediaType()
        payload=request.get_json()
    result=current_app.extensions['earthlens_time_machine'].build(payload)
    return success(result,meta={'scientific_status':'provisional','origin':'cache','spatial_resize_enabled':False})


def service():
    return current_app.extensions["earthlens_service"]


def query_parameters(allowed=()):
    if set(request.args) - set(allowed):
        raise ServiceError("invalid_request", "La solicitud contiene filtros no admitidos.")
    result = {}
    for name in request.args:
        values = request.args.getlist(name)
        if len(values) != 1 or not values[0].strip():
            raise ServiceError("invalid_request", "Cada filtro debe contener un único texto no vacío.", details={"field": name})
        result[name] = values[0]
    return result


@api.get("/health")
def health():
    query_parameters()
    return success({"service": "EarthLens", "status": "up", "country_code": "AR"})


@api.get("/variables")
def variables():
    query_parameters()
    data = service().list_variables()
    return success(data, meta={"count": len(data)})


@api.get("/cities")
def cities():
    filters = query_parameters(("province", "region"))
    data = service().list_cities(**filters)
    return success(data, meta={"count": len(data), "filters": filters})


@api.get("/cities/<city_id>")
def city(city_id):
    query_parameters()
    return success(service().get_city(city_id))


@api.get("/regions")
def regions():
    query_parameters()
    data = service().list_regions()
    return success(data, meta={"count": len(data)})


@api.post("/data")
def data():
    query_parameters()
    if not request.is_json:
        raise UnsupportedMediaType()
    result, meta = service().get_data(request.get_json())
    return success(result, meta=meta)


def analysis_service():
    return current_app.extensions["earthlens_analysis"]


@api.post("/analyze")
def analyze():
    query_parameters()
    if not request.is_json:
        raise UnsupportedMediaType()
    result, meta = analysis_service().analyze(request.get_json())
    return success(result, meta=meta)


@api.get("/summary")
def summary():
    payload = query_parameters(("city_id", "start_year", "end_year"))
    for key in ("start_year", "end_year"):
        if key in payload:
            try:
                payload[key] = int(payload[key])
            except ValueError:
                raise ServiceError("invalid_request", "Los años deben ser enteros.") from None
    result, meta = analysis_service().summary(payload)
    return success(result, meta=meta)


@api.post("/compare")
def compare():
    query_parameters()
    if not request.is_json:
        raise UnsupportedMediaType()
    result, meta = analysis_service().compare(request.get_json())
    return success(result, meta=meta)


@api.get("/missions")
def missions():
    from services.science.guided_missions import list_missions, list_hypotheses
    query_parameters()
    result = list_missions()
    return success(result, meta={"count": len(result), "hypotheses": list_hypotheses()})


@api.get("/missions/<mission_id>")
def mission(mission_id):
    from services.science.mission_service import mission_detail
    from flask import abort
    query_parameters()
    result = mission_detail(mission_id, service())
    if result is None:
        abort(404)
    return success(result)


@api.get("/catalog")
def guided_catalog():
    from services.science.mission_service import catalog
    query_parameters()
    return success(catalog())


@api.get("/variables/recommend")
def recommend_variables():
    from services.science.mission_service import recommendations
    filters = query_parameters(("phenomenon",))
    return success(recommendations(filters.get("phenomenon")))


@api.get("/fingerprint/<city_id>")
def fingerprint(city_id):
    parameters = query_parameters(("start_year", "end_year"))
    period = {}
    for key, value in parameters.items():
        try:
            period[key] = int(value)
        except ValueError:
            raise ServiceError("invalid_request", "Los años deben ser enteros.") from None
    profile = current_app.extensions["earthlens_fingerprint"].profile(city_id, **period)
    return success(profile, meta={"methodology_validated": False})


@api.get("/radar")
def radar():
    filters = query_parameters(("province", "region", "variable", "direction", "evidence_status"))
    study = current_app.extensions["earthlens_radar"].query(**filters)
    return success(study, meta={"count": study["view"]["count"], "methodology_validated": False})
