"""Eventos privados y preferencias explícitas; no almacena credenciales externas."""
from datetime import datetime, timedelta, timezone
import math
import re
import uuid

from services.api_service import ServiceError
from services.providers.cache import utc_now
from services.storage.persistence import encode

ACTIVITIES={'hiking','excursion','camping','sport','urban','coastal','cycling','outdoor','indoor','custom'}
PREFERENCES={'min_temperature','max_temperature','max_probability','max_precipitation','max_wind','max_gust',
    'min_visibility','max_humidity','min_apparent_temperature','max_apparent_temperature','require_official_alerts'}

def stamp(value):
    if not isinstance(value,str):raise ServiceError('invalid_request','Usar fecha y hora ISO con zona horaria.')
    try:
        d=datetime.fromisoformat(value)
        if d.tzinfo is None or d.utcoffset()!=timedelta(hours=-3):raise ValueError()
        return d
    except ValueError:raise ServiceError('invalid_request','La hora del evento debe incluir zona argentina -03:00.') from None


def validate_event(payload,data_service):
    fields={'name','description','activity','city_id','location_label','start','end','participants','outdoor','transport',
        'flexible_days','flexible_hours','preferences','notifications','status'}
    if not isinstance(payload,dict) or set(payload)-fields:
        raise ServiceError('invalid_request','Campos de evento no admitidos. Las coordenadas y recorridos libres aún no están habilitados.')
    for field,limit in [('name',120),('description',2000),('location_label',200)]:
        value=payload.get(field,'' if field!='name' else None)
        if not isinstance(value,str) or len(value)>limit or (field=='name' and not value.strip()):
            raise ServiceError('invalid_request','Nombre, descripción o ubicación inválidos.')
    if not isinstance(payload.get('activity'),str) or payload['activity'] not in ACTIVITIES:raise ServiceError('invalid_request','Actividad desconocida.')
    city=data_service.get_city(payload.get('city_id'))
    first,last=stamp(payload.get('start')),stamp(payload.get('end'))
    if first>=last or last-first>timedelta(days=7):raise ServiceError('invalid_request','Duración inválida; máximo siete días.')
    participants=payload.get('participants',1);flex=payload.get('flexible_days',0);hours=payload.get('flexible_hours',0)
    if type(participants) is not int or not 1<=participants<=100000 or type(flex) is not int or not 0<=flex<=7 or type(hours) is not int or not 0<=hours<=6:
        raise ServiceError('invalid_request','Participantes o flexibilidad inválidos.')
    for key in ('outdoor','notifications'):
        if type(payload.get(key,True)) is not bool:raise ServiceError('invalid_request','Usar booleanos para exterior y notificaciones.')
    if not isinstance(payload.get('transport','walk'),str) or payload.get('transport','walk') not in {'walk','bike','car','bus','other'}:raise ServiceError('invalid_request','Transporte desconocido.')
    prefs=payload.get('preferences',{})
    if not isinstance(prefs,dict) or set(prefs)-PREFERENCES:raise ServiceError('invalid_request','Preferencias desconocidas.')
    for key,value in prefs.items():
        if key=='require_official_alerts':
            if type(value) is not bool:raise ServiceError('invalid_request','Usar booleano para la verificación de alertas.')
        elif isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not -150<=value<=100000:
            raise ServiceError('invalid_request','Umbral meteorológico inválido.')
        elif key in {'max_probability','max_humidity'} and not 0<=value<=100:
            raise ServiceError('invalid_request','Porcentajes entre 0 y 100.')
        elif key in {'max_precipitation','max_wind','max_gust','min_visibility'} and value<0:
            raise ServiceError('invalid_request','Umbral físico negativo no permitido.')
    if prefs.get('min_temperature',-150)>prefs.get('max_temperature',150):raise ServiceError('invalid_request','El mínimo supera al máximo.')
    status=payload.get('status','active')
    if not isinstance(status,str) or status not in {'active','cancelled'}:raise ServiceError('invalid_request','Estado desconocido.')
    return {**payload,'city_id':city['id'],'description':payload.get('description',''),'location_label':payload.get('location_label',''),
        'location':{'latitude':city['latitude'],'longitude':city['longitude'],'evidence':'GeoRef city centroid','precision':'city_centroid_not_event_site'},
        'duration_minutes':int((last-first).total_seconds()/60),'participants':participants,'outdoor':payload.get('outdoor',True),
        'transport':payload.get('transport','walk'),'flexible_days':flex,'flexible_hours':hours,'preferences':prefs,'notifications':payload.get('notifications',True),
        'status':status,'start':first.isoformat(),'end':last.isoformat()}


class EventService:
    def __init__(self,store,data_service):self.store=store;self.data=data_service

    @staticmethod
    def decode(row):
        import json
        return {**json.loads(row['body']),'id':row['id'],'status':row['status'],'revision':row['revision'],'updated_at':row['updated_at']}

    def list(self,user_id):
        with self.store.connect() as db:
            return [self.decode(r) for r in db.execute('SELECT * FROM events WHERE user_id=? ORDER BY start',(user_id,))]

    def get(self,user_id,event_id):
        with self.store.connect() as db:row=db.execute('SELECT * FROM events WHERE user_id=? AND id=?',(user_id,event_id)).fetchone()
        if row is None:raise ServiceError('event_not_found','El evento no existe.')
        return self.decode(row)

    def save(self,user_id,payload,event_id=None):
        if event_id:
            old=self.get(user_id,event_id)
            base={k:v for k,v in old.items() if k not in {'id','revision','updated_at','location','duration_minutes'}}
            payload={**base,**payload}
        body=validate_event(payload,self.data);identifier=event_id or uuid.uuid4().hex;now=utc_now()
        with self.store.connect() as db:
            if event_id:
                count=db.execute('UPDATE events SET body=?,status=?,start=?,end=?,revision=revision+1,updated_at=? WHERE user_id=? AND id=?',
                    (encode(body),body['status'],body['start'],body['end'],now,user_id,event_id)).rowcount
                if count!=1:raise ServiceError('event_not_found','El evento no existe.')
            else:db.execute('INSERT INTO events(id,user_id,body,status,start,end,updated_at) VALUES(?,?,?,?,?,?,?)',
                (identifier,user_id,encode(body),body['status'],body['start'],body['end'],now))
        return self.get(user_id,identifier)

    def delete(self,user_id,event_id):
        with self.store.connect() as db:
            if db.execute('DELETE FROM events WHERE user_id=? AND id=?',(user_id,event_id)).rowcount!=1:
                raise ServiceError('event_not_found','El evento no existe.')

    def history(self,user_id,event_id):
        import json
        self.get(user_id,event_id)
        with self.store.connect() as db:
            return [{'id':r['id'],'created_at':r['created_at'],'event_revision':r['event_revision'],
                'assessment':json.loads(r['body']),'snapshot_id':r['snapshot_id']} for r in db.execute(
                    'SELECT * FROM assessments WHERE event_id=? ORDER BY created_at DESC LIMIT 100',(event_id,))]

    def forecast_history(self,user_id,event_id,variable='temperature_2m',valid_time=None):
        import json
        from services.weather.weather import HOURLY
        if variable not in HOURLY:raise ServiceError('invalid_request','Variable de pronóstico desconocida.')
        event=self.get(user_id,event_id);first,last=stamp(event['start']),stamp(event['end'])
        if valid_time is None:target=first.astimezone(timezone.utc).replace(minute=0,second=0,microsecond=0)
        else:
            try:
                target=datetime.fromisoformat(valid_time)
                if target.tzinfo is None or target.minute or target.second or not (target<last and target+timedelta(hours=1)>first):raise ValueError()
            except (TypeError,ValueError):raise ServiceError('invalid_request','Seleccionar una hora ISO que intersecte el evento.') from None
        rows=[]
        with self.store.connect() as db:
            for snapshot in db.execute('SELECT * FROM forecast_snapshots WHERE event_id=? ORDER BY fetched_at LIMIT 100',(event_id,)):
                body=json.loads(snapshot['body']);forecast=body.get('forecast')
                if not forecast:continue
                row=forecast['variables'].get(variable)
                if not row:continue
                values=[p for p in row['series'] if datetime.fromisoformat(p['date'])==target]
                rows.append({'snapshot_id':snapshot['id'],'fetched_at':forecast['fetched_at'],
                    'issued_at':forecast.get('issued_at'),'provider':forecast['provider'],'product':forecast['product'],
                    'value':values[0]['value'] if values else None,'assessment_status':body['assessment']['status']})
        return {'event_id':event_id,'variable':variable,'unit':HOURLY[variable],'valid_time':target.isoformat(),
            'versions':rows,'limitations':['Eje temporal: obtenciones, no emisiones no informadas.',
                'El historial de un evento reprogramado puede no cubrir la nueva hora. No se imputa.',
                'No es una evaluación de exactitud contra observaciones posteriores.']}
