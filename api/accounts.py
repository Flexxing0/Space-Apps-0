"""Autenticación por sesión, CSRF y autorización de cada recurso privado."""
from datetime import datetime, timezone
from functools import wraps
import hashlib
import hmac
import re
import secrets
import uuid

from flask import current_app, request, session
from werkzeug.exceptions import UnsupportedMediaType
from werkzeug.security import check_password_hash, generate_password_hash
from api.responses import success
from services.api_service import ServiceError
from services.providers.cache import utc_now

def store():return current_app.extensions['earthlens_store']
def body():
    if not request.is_json:raise UnsupportedMediaType()
    value=request.get_json()
    if not isinstance(value,dict):raise ServiceError('invalid_request','El cuerpo debe ser un objeto JSON.')
    return value

def user():
    uid=session.get('user_id')
    if not uid:return None
    with store().connect() as db:row=db.execute('SELECT id,username FROM users WHERE id=?',(uid,)).fetchone()
    return dict(row) if row else None

def protect(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if not user():raise ServiceError('authentication_required','Iniciá sesión para acceder a tus datos.')
        if request.method not in {'GET','HEAD'}:csrf()
        return fn(*args,**kwargs)
    return wrapped

def csrf():
    expected=session.get('csrf_token');received=request.headers.get('X-CSRF-Token','')
    if not isinstance(expected,str) or not received.isascii() or not hmac.compare_digest(expected,received):
        raise ServiceError('csrf_invalid','La sesión cambió; recargá la página antes de guardar.')

def get_session():
    if 'csrf_token' not in session:session['csrf_token']=secrets.token_urlsafe(32)
    return success({'user':user(),'csrf_token':session['csrf_token']})

def authenticate(action):
    csrf()
    if action=='logout':session.clear();return success({'logged_out':True})
    if action not in {'login','register'}:raise ServiceError('invalid_request','Acción desconocida.')
    payload=body();name=payload.get('username');password=payload.get('password')
    allowed={'username','password','email','email_alerts_enabled'} if action=='register' else {'username','password'}
    if not {'username','password'}<=set(payload) or set(payload)-allowed or not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,60}',name) or not isinstance(password,str) or not 6<=len(password)<=200:
        raise ServiceError('invalid_request','Usuario de 3–60 caracteres y contraseña de 6–200 caracteres.')
    clean_email='';email_enabled=False
    if action=='register' and 'email' in payload:
        from services.events import mailer
        raw_email=payload.get('email')
        if not isinstance(raw_email,str):raise ServiceError('invalid_request','Correo electrónico inválido.')
        clean_email=raw_email.strip()
        if clean_email and not mailer.valid_email(clean_email):
            raise ServiceError('invalid_request','Ingresá un correo electrónico válido (ej. nombre@correo.com).')
        raw_enabled=payload.get('email_alerts_enabled',bool(clean_email))
        if type(raw_enabled) is not bool:raise ServiceError('invalid_request','Valor inválido para avisos por correo.')
        email_enabled=raw_enabled and bool(clean_email)
    identity=hashlib.sha256((request.remote_addr or 'local').encode()+name.casefold().encode()).hexdigest()
    with store().connect() as db:
        attempt=db.execute('SELECT * FROM login_attempts WHERE identity=?',(identity,)).fetchone()
        if attempt and attempt['failures']>=10 and (datetime.now(timezone.utc)-datetime.fromisoformat(attempt['last_at'])).total_seconds()<900:
            raise ServiceError('rate_limited','Demasiados intentos; esperá quince minutos.')
        row=db.execute('SELECT * FROM users WHERE username=?',(name.casefold(),)).fetchone()
        failure=False
        if action=='register':
            if row:raise ServiceError('account_conflict','Ese nombre de usuario no está disponible.')
            identifier=uuid.uuid4().hex
            now=utc_now()
            db.execute('INSERT INTO users VALUES(?,?,?,?)',(identifier,name.casefold(),generate_password_hash(password),now))
            if clean_email:
                from services.storage.persistence import encode
                db.execute(
                    'CREATE TABLE IF NOT EXISTS user_workspace_prefs('
                    'user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, '
                    'body TEXT NOT NULL, updated_at TEXT NOT NULL)'
                )
                db.execute('INSERT OR REPLACE INTO user_workspace_prefs(user_id,body,updated_at) VALUES(?,?,?)',
                    (identifier,encode({'saved_cities':[],'trip':None,'email':clean_email,'email_alerts_enabled':email_enabled}),now))
        else:
            # También calcula un hash ante usuario inexistente para reducir diferencias de tiempo.
            valid=check_password_hash(row['password_hash'] if row else generate_password_hash('dummy-password-unknown'),password)
            if not row or not valid:
                failures=attempt['failures']+1 if attempt and (datetime.now(timezone.utc)-datetime.fromisoformat(attempt['last_at'])).total_seconds()<900 else 1
                db.execute('INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)',(identity,failures,utc_now()));failure=True
            else:identifier=row['id']
        if not failure:db.execute('DELETE FROM login_attempts WHERE identity=?',(identity,))
    if failure:raise ServiceError('authentication_required','Credenciales inválidas.')
    session.clear();session['user_id']=identifier;session['csrf_token']=secrets.token_urlsafe(32)
    return success({'user':{'id':identifier,'username':name.casefold()},'csrf_token':session['csrf_token']})

def register_session_routes(blueprint):
    blueprint.get('/session')(get_session)
    blueprint.post('/session/<action>')(authenticate)
