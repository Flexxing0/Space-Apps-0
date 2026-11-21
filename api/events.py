"""Rutas de calendario, eventos y notificaciones privadas."""

import json

from flask import Blueprint, current_app, request, session

from api.accounts import body, protect, register_session_routes, store
from api.responses import success
from services.api_service import ServiceError
from services.providers.cache import utc_now

events_api=Blueprint('events_api',__name__,url_prefix='/api')
register_session_routes(events_api)

def service():return current_app.extensions['earthlens_events']

@events_api.get('/events')
@protect
def events():return success(service().list(session['user_id']))

@events_api.post('/events')
@protect
def create_event():return success(service().save(session['user_id'],body())),201

@events_api.get('/events/<event_id>')
@protect
def get_event(event_id):return success(service().get(session['user_id'],event_id))

@events_api.patch('/events/<event_id>')
@protect
def edit_event(event_id):return success(service().save(session['user_id'],body(),event_id))

@events_api.delete('/events/<event_id>')
@protect
def delete_event(event_id):service().delete(session['user_id'],event_id);return success({'deleted':True})

@events_api.get('/events/<event_id>/history')
@protect
def history(event_id):return success(service().history(session['user_id'],event_id))

@events_api.get('/events/<event_id>/forecast-history')
@protect
def forecast_history(event_id):
    if set(request.args)-{'variable','valid_time'}:raise ServiceError('invalid_request','Filtros desconocidos.')
    return success(service().forecast_history(session['user_id'],event_id,**request.args.to_dict()))

@events_api.post('/events/preview')
@protect
def preview():
    from services.events.events import validate_event
    event=validate_event(body(),service().data)
    result=current_app.extensions['earthlens_planning'].preview(event)
    result.pop('bundle',None)
    return success(result)

@events_api.get('/notifications')
@protect
def notifications():
    with store().connect() as db:rows=db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(session['user_id'],)).fetchall()
    return success([{**dict(r),'body':json.loads(r['body'])} for r in rows])

@events_api.patch('/notifications/<notification_id>')
@protect
def read_notification(notification_id):
    with store().connect() as db:
        if db.execute('UPDATE notifications SET read_at=COALESCE(read_at,?) WHERE user_id=? AND id=?',(utc_now(),session['user_id'],notification_id)).rowcount!=1:
            raise ServiceError('event_not_found','La notificación no existe.')
    return success({'read':True})


@events_api.get('/events/<event_id>/report.pdf')
@protect
def event_report(event_id):
    from flask import Response
    from services.workspace.reports import pdf_report
    event=service().get(session['user_id'],event_id);history=service().history(session['user_id'],event_id)
    sections=[('Evento',event),('Última evaluación guardada',history[0]['assessment'] if history else
        'Sin monitoreo todavía. No hay evaluación científica disponible.'),
        ('Historial',history[:10]),('Límites','No garantiza seguridad. Verificar avisos oficiales SMN y condiciones del lugar. Centroide de ciudad, sin análisis del sitio exacto.')]
    return Response(pdf_report('Plan de actividad · '+event['name'],sections),mimetype='application/pdf',
        headers={'Content-Disposition':'attachment; filename="earthlens-event.pdf"','Cache-Control':'no-store'})
