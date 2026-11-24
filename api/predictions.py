"""Lecturas acotadas de la proyección local de predicciones."""

import re

from flask import Blueprint, current_app, request

from api.responses import success
from services.api_service import ServiceError
from services.prediction.contracts import FREQUENCIES, IDENTIFIER
from services.workspace.workspace import iso_date


predictions_api = Blueprint('predictions_api', __name__, url_prefix='/api')


@predictions_api.get('/predictions')
def saved_predictions():
    required = {'city_id', 'variable', 'start', 'end'}
    allowed = required | {'frequency', 'provider', 'version_id'}
    if (set(request.args) - allowed or not required <= set(request.args)
            or any(len(request.args.getlist(key)) != 1 for key in request.args)):
        raise ServiceError('invalid_request', 'Seleccionar ciudad, variable y rango, sin parámetros repetidos.')
    selection = request.args.to_dict()
    selection.setdefault('provider', 'bigquery-timesfm')
    selection.setdefault('frequency', 'daily')
    first, last = iso_date(selection['start']), iso_date(selection['end'])
    frequency = selection['frequency']
    version = selection.get('version_id')
    if (frequency not in FREQUENCIES or not IDENTIFIER.fullmatch(selection['variable'])
            or not IDENTIFIER.fullmatch(selection['provider'])
            or (version is not None and not re.fullmatch(r'[0-9a-f]{64}', version))
            or not 0 <= (last-first).days < (31 if frequency == 'hourly' else 366)):
        raise ServiceError('invalid_request', 'Variable, proveedor, frecuencia, versión o rango inválidos.')
    city = current_app.extensions['earthlens_service'].get_city(selection['city_id'])
    reader = current_app.extensions['earthlens_prediction_reader']
    result = reader.lookup(**selection)
    reason = None
    if result is None:
        reason = 'no_saved_version'
    elif not result['points']:
        reason = 'no_points_in_range'
    elif all(point['value'] is None for point in result['points']):
        reason = 'no_valid_values'
    return success({'status': 'unavailable' if reason else 'available', 'reason': reason,
                    'selection': selection, 'location': city, 'result': result})
