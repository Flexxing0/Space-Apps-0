"""API aditiva de series nativas; no altera los endpoints ni la familia POWER."""

from flask import Blueprint, current_app, request
from werkzeug.exceptions import UnsupportedMediaType
import requests
from datetime import datetime, timezone

from api.responses import success
from api.routes import query_parameters
from services.api_service import ServiceError
from services.providers.bulk import validate_period


scientific_api = Blueprint("scientific_api", __name__, url_prefix="/api/science")


@scientific_api.get("/variables")
def variables():
    query_parameters()
    rows = current_app.extensions["earthlens_science"].variables()
    return success(rows, meta={"count": len(rows), "availability": "verified_cached_data", "radar_family_changed": False})


@scientific_api.post("/data")
def data():
    query_parameters()
    if not request.is_json:
        raise UnsupportedMediaType()
    payload = request.get_json()
    allowed = {"provider", "city_id", "variables", "start_year", "end_year", "force"}
    if not isinstance(payload, dict) or set(payload) - allowed or not {"provider", "city_id", "variables"} <= set(payload):
        raise ServiceError("invalid_request", "Usar provider, city_id, variables y un período opcional; no se admiten coordenadas libres.")
    if not isinstance(payload["provider"], str) or payload["provider"] not in {"power", "modis", "gldas", "gpm"}:
        raise ServiceError("invalid_request", "Proveedor no registrado.")
    if not isinstance(payload["variables"], list) or not payload["variables"] or any(not isinstance(v, str) for v in payload["variables"]):
        raise ServiceError("invalid_request", "variables debe ser una lista de códigos.")
    try:
        validate_period(payload.get("start_year", 2000), payload.get("end_year", 2024))
        if payload.get("end_year", 2024) > datetime.now(timezone.utc).year or type(payload.get("force", False)) is not bool:
            raise ValueError()
        service = current_app.extensions["earthlens_science"]
        service.data_service.get_city(payload["city_id"])
    except ValueError:
        raise ServiceError("invalid_request", "Tipos, fechas o force inválidos.") from None
    available = {(row["provider"], row["variable"]) for row in service.variables()}
    if any((payload["provider"], variable) not in available for variable in payload["variables"]):
        raise ServiceError("provider_not_verified", "La variable no tiene datos reales verificados disponibles en este servidor.")
    try:
        records = service.fetch(**payload)
    except requests.Timeout:
        raise ServiceError("provider_timeout", "El proveedor científico excedió el tiempo de espera.") from None
    except requests.RequestException:
        raise ServiceError("provider_unavailable", "El proveedor científico no está disponible.") from None
    except (ValueError, KeyError, TypeError):
        raise ServiceError("provider_invalid_response", "La respuesta científica no satisface el contrato de datos.") from None
    return success(records, meta={"count": len(records), "native_frequency": True, "analysis_enabled": False})


@scientific_api.post('/compare')
def compare():
    from services.science.scientific_compare import compare as compare_series
    query_parameters()
    if not request.is_json:raise UnsupportedMediaType()
    try:
        result=compare_series(current_app.extensions['earthlens_science'],request.get_json())
    except requests.Timeout:
        raise ServiceError('provider_timeout','El proveedor excedió el tiempo de espera.') from None
    except requests.RequestException:
        raise ServiceError('provider_unavailable','El proveedor no está disponible.') from None
    except (ValueError,KeyError,TypeError):
        raise ServiceError('provider_invalid_response','La respuesta no satisface el contrato científico.') from None
    return success(result,meta={'scope':'descriptive_only'})


@scientific_api.get('/water-features')
def water_features():
    query_parameters()
    features=current_app.extensions['earthlens_hydrology'].features()
    return success(features,meta={'count':len(features),'location_type':'water_feature'})


@scientific_api.post('/water-data')
def water_data():
    query_parameters()
    if not request.is_json:raise UnsupportedMediaType()
    payload=request.get_json()
    if not isinstance(payload,dict) or set(payload)-{'feature_id','start_time','end_time','force'} or not {'feature_id','start_time','end_time'}<=set(payload):
        raise ServiceError('invalid_request','Usar feature_id del catálogo hidrológico y fechas UTC; no se admiten coordenadas libres.')
    if not isinstance(payload['feature_id'],str) or type(payload.get('force',False)) is not bool:
        raise ServiceError('invalid_request','Identificador o force inválido.')
    service=current_app.extensions['earthlens_hydrology']
    try:service.context(payload['feature_id'],payload['start_time'],payload['end_time'])
    except ValueError:raise ServiceError('invalid_request','Fechas hidrológicas inválidas.') from None
    try:
        result=service.fetch(payload['feature_id'],payload['start_time'],payload['end_time'],force=payload.get('force',False))
    except requests.Timeout:raise ServiceError('provider_timeout','Hydrocron excedió el tiempo de espera.') from None
    except requests.RequestException:raise ServiceError('provider_unavailable','Hydrocron no está disponible.') from None
    except (ValueError,KeyError,TypeError):raise ServiceError('provider_invalid_response','Hydrocron devolvió datos incompatibles.') from None
    return success(result,meta={'location_type':'water_feature','analysis_enabled':False})
