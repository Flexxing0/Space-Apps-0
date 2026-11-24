"""Trabajo independiente e idempotente. No depende de una pestaña o servidor Flask."""
from datetime import datetime,timedelta,timezone
import hashlib
import json
import uuid

from services.providers.cache import utc_now
from services.events.events import EventService, stamp
from services.storage.persistence import encode
from services.events.planning import decision_key

class MonitoringService:
    def __init__(self,events,planning):self.events=events;self.store=events.store;self.planning=planning

    def run(self,*,force=False,near_hours=1,far_hours=24):
        owner=uuid.uuid4().hex;now=datetime.now(timezone.utc);summary={'examined':0,'updated':0,'unchanged':0,'failed':0,'notifications':0,'skipped':0}
        with self.store.connect() as db:
            lease=db.execute('SELECT * FROM monitoring_leases WHERE name=?',('events',)).fetchone()
            if lease and datetime.fromisoformat(lease['expires_at'])>now:
                return {'status':'already_running','summary':summary}
            db.execute('INSERT OR REPLACE INTO monitoring_leases VALUES(?,?,?)',('events',owner,(now+timedelta(minutes=30)).isoformat()))
            db.execute('INSERT INTO monitoring_runs VALUES(?,?,?,?,?)',(owner,now.isoformat(),None,'running',encode(summary)))
            rows=db.execute("SELECT * FROM events WHERE status='active'").fetchall()
        try:
            for row in rows:
                event=self.events.decode(row)
                if stamp(event['end'])<now or stamp(event['start'])>now+timedelta(days=15):summary['skipped']+=1;continue
                summary['examined']+=1
                with self.store.connect() as db:
                    prior=db.execute('SELECT * FROM assessments WHERE event_id=? ORDER BY created_at DESC LIMIT 1',(event['id'],)).fetchone()
                    interval=near_hours if stamp(event['start'])-now<timedelta(days=3) else far_hours
                    if prior and not force and prior['event_revision']==event['revision'] and (now-datetime.fromisoformat(prior['created_at'])).total_seconds()<interval*3600:
                        summary['skipped']+=1;continue
                try:
                    result=self.planning.preview(event,force=force)
                    assessment=result['assessment'];bundle=result.pop('bundle')
                    body={'forecast':bundle,'assessment':assessment,'alternatives':result['alternatives']}
                    fingerprint=hashlib.sha256(encode({'variables':bundle['variables'] if bundle else None,
                        'product':bundle['product'] if bundle else None,'event_revision':event['revision'],
                        'decision':decision_key(assessment)}).encode()).hexdigest()
                    with self.store.connect() as db:
                        current=db.execute('SELECT revision,status FROM events WHERE id=?',(event['id'],)).fetchone()
                        if not current or current['revision']!=event['revision'] or current['status']!='active':summary['skipped']+=1;continue
                        db.execute('UPDATE monitoring_leases SET expires_at=? WHERE name=? AND owner=?',((datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat(),'events',owner))
                        old=db.execute('SELECT id FROM forecast_snapshots WHERE event_id=? AND fingerprint=?',(event['id'],fingerprint)).fetchone()
                        if old:summary['unchanged']+=1;continue
                        snapshot=uuid.uuid4().hex
                        db.execute('INSERT INTO forecast_snapshots VALUES(?,?,?,?,?)',(snapshot,event['id'],utc_now(),fingerprint,encode(body)))
                        db.execute('INSERT INTO assessments VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,event['id'],snapshot,event['revision'],utc_now(),encode(assessment)))
                        changed=not prior or decision_key(json.loads(prior['body']))!=decision_key(assessment)
                        if changed and event['notifications']:
                            previous_assessment=json.loads(prior['body']) if prior else None
                            previous=previous_assessment['status'] if previous_assessment else None
                            changes=[]
                            for criterion,current in assessment['metrics'].items():
                                old=(previous_assessment or {}).get('metrics',{}).get(criterion)
                                if old is None or old['value']!=current['value']:
                                    changes.append({'criterion':criterion,'previous_value':old['value'] if old else None,
                                        'current_value':current['value'],'unit':current['unit'],'threshold':current['threshold']})
                            title='Cambió la evaluación del evento' if prior else 'Primera evaluación del evento'
                            message=event['name']+': '+assessment['label']+'. Revisar criterios, fuente y límites.'
                            dedupe=hashlib.sha256(encode([event['id'],event['revision'],fingerprint]).encode()).hexdigest()
                            count=db.execute('INSERT OR IGNORE INTO notifications VALUES(?,?,?,?,?,?,?,?,?)',
                                (uuid.uuid4().hex,row['user_id'],event['id'],dedupe,utc_now(),None,title,message,
                                 encode({'previous_status':previous,'assessment':assessment,'alternatives':body['alternatives'],
                                    'event':{'id':event['id'],'name':event['name'],'city_id':event['city_id'],'start':event['start'],'end':event['end']},
                                    'changes':changes,'recommendation':'Revisar los criterios y avisos oficiales; las alternativas requieren confirmación del usuario.',
                                    'potential_consequences':'Cambio de compatibilidad meteorológica. Sin evidencia espacial suficiente para afirmar impactos urbanos.'}))).rowcount
                            summary['notifications']+=count
                            if count==1:
                                from services.events import mailer
                                if mailer.is_configured():
                                    try:
                                        pref_row=db.execute("SELECT body FROM user_workspace_prefs WHERE user_id=?",(row['user_id'],)).fetchone()
                                    except Exception:
                                        pref_row=None
                                    if pref_row:
                                        prefs=json.loads(pref_row['body'])
                                        if prefs.get('email_alerts_enabled') and mailer.valid_email(prefs.get('email','')):
                                            try:
                                                mailer.send_event_alert(
                                                    prefs['email'],event,title,message,
                                                    changes=changes,
                                                    recommendation='Revisá el pronóstico actualizado en EarthLens para ajustar tu actividad si hace falta.'
                                                )
                                            except Exception:
                                                pass
                    summary['updated']+=1
                    if assessment['status']=='insufficient':summary['failed']+=1
                except Exception as error:
                    # Sólo clase de error; no requests URL ni credenciales ni eventos privados en logs.
                    summary['failed']+=1
        finally:
            with self.store.connect() as db:
                db.execute('UPDATE monitoring_runs SET finished_at=?,status=?,body=? WHERE id=?',(utc_now(),'partial' if summary['failed'] else 'ok',encode(summary),owner))
                db.execute('DELETE FROM monitoring_leases WHERE name=? AND owner=?',('events',owner))
        return {'status':'partial' if summary['failed'] else 'ok','run_id':owner,'summary':summary}
