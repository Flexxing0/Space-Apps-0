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
    from services.events import mailer
    with store().connect() as db:
        _ensure_prefs_table(db)
        row=db.execute('SELECT body, updated_at FROM user_workspace_prefs WHERE user_id=?',(session['user_id'],)).fetchone()
    if not row:
        return success({'saved_cities':[],'trip':None,'email':'','email_alerts_enabled':False,'smtp_configured':mailer.is_configured(),'updated_at':None})
    data=json.loads(row['body'])
    return success({
        'saved_cities':data.get('saved_cities',[]),
        'trip':data.get('trip'),
        'email':data.get('email',''),
        'email_alerts_enabled':bool(data.get('email_alerts_enabled',False)),
        'smtp_configured':mailer.is_configured(),
        'updated_at':row['updated_at'],
    })


@events_api.put('/account/preferences')
@protect
def put_account_preferences():
    from services.events import mailer
    from services.storage.persistence import encode
    from services.workspace.workspace import iso_date
    payload=body()
    if set(payload)-{'saved_cities','trip','email','email_alerts_enabled'}:
        raise ServiceError('invalid_request','Campos de preferencias no admitidos.')
    with store().connect() as db:
        _ensure_prefs_table(db)
        existing_row=db.execute('SELECT body FROM user_workspace_prefs WHERE user_id=?',(session['user_id'],)).fetchone()
    existing=json.loads(existing_row['body']) if existing_row else {}
    data_svc=current_app.extensions['earthlens_service']
    valid_ids={c['id'] for c in data_svc.list_cities()}

    if 'saved_cities' in payload:
        raw_cities=payload['saved_cities']
        if not isinstance(raw_cities,list) or len(raw_cities)>50 or any(not isinstance(x,str) or x not in valid_ids for x in raw_cities):
            raise ServiceError('invalid_request','Lista de ciudades guardadas inválida.')
        dedup_cities=list(dict.fromkeys(raw_cities))
    else:
        dedup_cities=existing.get('saved_cities',[])

    if 'trip' in payload:
        trip=payload['trip']
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
    else:
        clean_trip=existing.get('trip')

    if 'email' in payload:
        raw_email=payload['email']
        if not isinstance(raw_email,str):
            raise ServiceError('invalid_request','Correo inválido.')
        clean_email=raw_email.strip()
        if clean_email and not mailer.valid_email(clean_email):
            raise ServiceError('invalid_request','Ingresá un correo electrónico válido (ej. nombre@correo.com).')
    else:
        clean_email=existing.get('email','')

    if 'email_alerts_enabled' in payload:
        enabled=payload['email_alerts_enabled']
        if type(enabled) is not bool:
            raise ServiceError('invalid_request','Valor inválido para consentimiento de avisos por correo.')
        if enabled and not clean_email:
            raise ServiceError('invalid_request','Ingresá tu correo electrónico para activar los avisos por mail.')
    else:
        enabled=bool(existing.get('email_alerts_enabled',False)) and bool(clean_email)

    now=utc_now()
    record={'saved_cities':dedup_cities,'trip':clean_trip,'email':clean_email,'email_alerts_enabled':enabled}
    with store().connect() as db:
        _ensure_prefs_table(db)
        db.execute('INSERT OR REPLACE INTO user_workspace_prefs(user_id,body,updated_at) VALUES(?,?,?)',
            (session['user_id'],encode(record),now))
    return success({**record,'smtp_configured':mailer.is_configured(),'updated_at':now})


@events_api.patch('/account/profile')
@protect
def update_account_profile():
    import re
    payload=body()
    if set(payload)!={'username'}:
        raise ServiceError('invalid_request','Solo se permite actualizar el nombre de usuario.')
    raw_name=payload.get('username')
    if not isinstance(raw_name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,60}',raw_name.strip()):
        raise ServiceError('invalid_request','Nombre de usuario de 3–60 caracteres (letras, números, punto o guion, sin espacios).')
    clean_name=raw_name.strip().casefold()
    uid=session['user_id']
    with store().connect() as db:
        conflict=db.execute('SELECT id FROM users WHERE username=? AND id!=?',(clean_name,uid)).fetchone()
        if conflict:
            raise ServiceError('account_conflict','Ese nombre de usuario ya está en uso por otra cuenta.')
        db.execute('UPDATE users SET username=? WHERE id=?',(clean_name,uid))
    return success({'user':{'id':uid,'username':clean_name}})


@events_api.post('/account/test-email')
@protect
def test_account_email():
    from api.accounts import user as current_user
    from services.events import mailer
    if not mailer.is_configured():
        raise ServiceError('provider_auth_required','El envío de correos SMTP todavía no está configurado en el servidor (.env).')
    with store().connect() as db:
        _ensure_prefs_table(db)
        row=db.execute('SELECT body FROM user_workspace_prefs WHERE user_id=?',(session['user_id'],)).fetchone()
    prefs=json.loads(row['body']) if row else {}
    to_email=prefs.get('email','')
    if not mailer.valid_email(to_email):
        raise ServiceError('invalid_request','Primero guardá un correo electrónico válido en tu cuenta.')
    if not prefs.get('email_alerts_enabled'):
        raise ServiceError('invalid_request','Activá el tilde de avisos por correo antes de enviar una prueba.')
    u=current_user()
    try:
        mailer.send_test_email(to_email,u['username'] if u else 'viajero')
    except Exception:
        raise ServiceError('provider_unavailable','No se pudo enviar el correo. Verificá tu configuración SMTP en .env y la Contraseña de aplicación de Gmail.') from None
    return success({'sent':True,'to':to_email})


@events_api.post('/events/<event_id>/evaluate')
@protect
def evaluate_saved_event(event_id):
    import hashlib
    import uuid
    from services.events import mailer
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
    user_prefs={}
    should_email=False
    title='Seguimiento activado · '+event['name']
    msg=f"{event['name']} ({event['start'][:10]}): {assessment['label']}."
    with store().connect() as db:
        _ensure_prefs_table(db)
        pref_row=db.execute('SELECT body FROM user_workspace_prefs WHERE user_id=?',(session['user_id'],)).fetchone()
        if pref_row:
            user_prefs=json.loads(pref_row['body'])
        old=db.execute('SELECT id FROM forecast_snapshots WHERE event_id=? AND fingerprint=?',(event['id'],fingerprint)).fetchone()
        if not old:
            snap_id=uuid.uuid4().hex
            db.execute('INSERT INTO forecast_snapshots VALUES(?,?,?,?,?)',(snap_id,event['id'],now,fingerprint,encode(snap_body)))
            db.execute('INSERT INTO assessments VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,event['id'],snap_id,event['revision'],now,encode(assessment)))
            if event.get('notifications'):
                dedupe=hashlib.sha256(encode([event['id'],event['revision'],fingerprint]).encode()).hexdigest()
                inserted=db.execute('INSERT OR IGNORE INTO notifications VALUES(?,?,?,?,?,?,?,?,?)',
                    (uuid.uuid4().hex,session['user_id'],event['id'],dedupe,now,None,title,msg,
                     encode({'previous_status':None,'assessment':assessment,'alternatives':result['alternatives'],
                             'event':{'id':event['id'],'name':event['name'],'city_id':event['city_id'],'start':event['start'],'end':event['end']},
                             'changes':[],'recommendation':'El monitoreo avisará si cambian las condiciones previstas para tu evento.',
                             'potential_consequences':'Evaluación inicial guardada en tu cuenta.'}))).rowcount
                should_email=inserted==1
    email_sent=False
    if should_email and user_prefs.get('email_alerts_enabled') and mailer.valid_email(user_prefs.get('email','')) and mailer.is_configured():
        try:
            city_info=current_app.extensions['earthlens_service'].get_city(event['city_id'])
            mailer.send_event_alert(
                user_prefs['email'],event,title,msg,
                recommendation='Seguimiento activo. Si cambia el pronóstico de lluvia, viento o temperatura, recibirás otro correo.',
                city_name=city_info.get('name','')
            )
            email_sent=True
        except Exception:
            email_sent=False
    return success({'assessment':assessment,'alternatives':result['alternatives'],'email_sent':email_sent})
