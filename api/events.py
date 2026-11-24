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


def _ensure_prefs_table(db):
    db.execute(
        'CREATE TABLE IF NOT EXISTS user_workspace_prefs('
        'user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, '
        'body TEXT NOT NULL, updated_at TEXT NOT NULL)'
    )


@events_api.get('/account/preferences')
@protect
def get_account_preferences():
    with store().connect() as db:
        _ensure_prefs_table(db)
        row=db.execute('SELECT body, updated_at FROM user_workspace_prefs WHERE user_id=?',(session['user_id'],)).fetchone()
    if not row:
        return success({'saved_cities':[],'trip':None,'updated_at':None})
    data=json.loads(row['body'])
    return success({'saved_cities':data.get('saved_cities',[]),'trip':data.get('trip'),'updated_at':row['updated_at']})


@events_api.put('/account/preferences')
@protect
def put_account_preferences():
    from services.storage.persistence import encode
    from services.workspace.workspace import iso_date
    payload=body()
    if set(payload)-{'saved_cities','trip'}:
        raise ServiceError('invalid_request','Campos de preferencias no admitidos.')
    data_svc=current_app.extensions['earthlens_service']
    valid_ids={c['id'] for c in data_svc.list_cities()}
    raw_cities=payload.get('saved_cities',[])
    if not isinstance(raw_cities,list) or len(raw_cities)>50 or any(not isinstance(x,str) or x not in valid_ids for x in raw_cities):
        raise ServiceError('invalid_request','Lista de ciudades guardadas inválida.')
    dedup_cities=list(dict.fromkeys(raw_cities))
    trip=payload.get('trip')
    clean_trip=None
    if trip is not None:
        if not isinstance(trip,dict) or set(trip)-{'city_id','start_date','duration_days'}:
            raise ServiceError('invalid_request','Configuración de viaje inválida.')
        cid=trip.get('city_id')
        if not isinstance(cid,str) or cid not in valid_ids:
            raise ServiceError('invalid_request','Ciudad de viaje inválida.')
        start_str=iso_date(trip.get('start_date')).isoformat()
        dur=trip.get('duration_days',5)
        if type(dur) is not int or not 1<=dur<=14:
            raise ServiceError('invalid_request','Duración de viaje entre 1 y 14 días.')
        clean_trip={'city_id':cid,'start_date':start_str,'duration_days':dur}
    now=utc_now()
    record={'saved_cities':dedup_cities,'trip':clean_trip}
    with store().connect() as db:
        _ensure_prefs_table(db)
        db.execute('INSERT OR REPLACE INTO user_workspace_prefs(user_id,body,updated_at) VALUES(?,?,?)',
            (session['user_id'],encode(record),now))
    return success({**record,'updated_at':now})


@events_api.post('/events/<event_id>/evaluate')
@protect
def evaluate_saved_event(event_id):
    import hashlib
    import uuid
    from services.storage.persistence import encode
    from services.events.planning import decision_key
    event=service().get(session['user_id'],event_id)
    result=current_app.extensions['earthlens_planning'].preview(event)
    assessment=result['assessment']
    bundle=result.pop('bundle',None)
    snap_body={'forecast':bundle,'assessment':assessment,'alternatives':result['alternatives']}
    fingerprint=hashlib.sha256(encode({
        'variables':bundle['variables'] if bundle else None,
        'product':bundle['product'] if bundle else None,
        'event_revision':event['revision'],
        'decision':decision_key(assessment)
    }).encode()).hexdigest()
    now=utc_now()
    with store().connect() as db:
        old=db.execute('SELECT id FROM forecast_snapshots WHERE event_id=? AND fingerprint=?',(event['id'],fingerprint)).fetchone()
        if not old:
            snap_id=uuid.uuid4().hex
            db.execute('INSERT INTO forecast_snapshots VALUES(?,?,?,?,?)',(snap_id,event['id'],now,fingerprint,encode(snap_body)))
            db.execute('INSERT INTO assessments VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,event['id'],snap_id,event['revision'],now,encode(assessment)))
            if event.get('notifications'):
                dedupe=hashlib.sha256(encode([event['id'],event['revision'],fingerprint]).encode()).hexdigest()
                title='Seguimiento activado · '+event['name']
                msg=f"{event['name']} ({event['start'][:10]}): {assessment['label']}."
                db.execute('INSERT OR IGNORE INTO notifications VALUES(?,?,?,?,?,?,?,?,?)',
                    (uuid.uuid4().hex,session['user_id'],event['id'],dedupe,now,None,title,msg,
                     encode({'previous_status':None,'assessment':assessment,'alternatives':result['alternatives'],
                             'event':{'id':event['id'],'name':event['name'],'city_id':event['city_id'],'start':event['start'],'end':event['end']},
                             'changes':[],'recommendation':'El monitoreo avisará si cambian las condiciones previstas para tu evento.',
                             'potential_consequences':'Evaluación inicial guardada en tu cuenta.'})))
    return success({'assessment':assessment,'alternatives':result['alternatives']})
