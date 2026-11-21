"""Compatibilidad explicable con preferencias del usuario; nunca una garantía."""
from datetime import datetime, timedelta, timezone
import hashlib
import math

from services.api_service import ServiceError
from services.providers.cache import utc_now
from services.events.events import stamp
from services.weather.weather import official_alerts

LABELS={'favorable':'Favorable según los criterios configurados','review':'Requiere revisión',
    'unfavorable':'Desfavorable según los criterios configurados','insufficient':'Datos insuficientes'}
# Categorías explícitas, no umbrales universales. Ninguna regla se activa sin preferencia.
RULES={'min_temperature':('temperature_2m','min','comfort','°C'),
    'max_temperature':('temperature_2m','max','comfort','°C'),
    'max_probability':('precipitation_probability','max','operational','%'),
    'max_precipitation':('precipitation','max','operational','mm por hora'),
    'max_wind':('wind_speed_10m','max','operational','m/s'),
    'max_gust':('wind_gusts_10m','max','operational','m/s'),
    'min_visibility':('visibility','min','operational','m'),
    'max_humidity':('relative_humidity_2m','max','comfort','%'),
    'min_apparent_temperature':('apparent_temperature','min','comfort','°C'),
    'max_apparent_temperature':('apparent_temperature','max','comfort','°C')}

def evaluate(event,bundle=None,*,alerts=None,failure=None):
    first,last=stamp(event['start']),stamp(event['end']);prefs=event['preferences'];reasons=[];metrics={};violations=0;missing=False
    if failure or bundle is None:
        missing=True;reasons.append({'category':'data','message':'No hay pronóstico operativo verificable para este intervalo.','code':failure or 'missing_forecast'})
    else:
        if bundle.get('kind')!='forecast':
            raise ValueError('Sólo un pronóstico operativo puede evaluar un evento futuro')
        floor=first.astimezone(timezone.utc).replace(minute=0,second=0,microsecond=0)
        expected=math.ceil((last.astimezone(timezone.utc)-floor).total_seconds()/3600)
        for key,(variable,operator,category,unit) in RULES.items():
            if key not in prefs:continue
            points=[p for p in bundle['variables'].get(variable,{}).get('series',[]) if datetime.fromisoformat(p['date'])<last and datetime.fromisoformat(p['date'])+timedelta(hours=1)>first]
            valid=[p['value'] for p in points if p['value'] is not None]
            if len(points)!=expected or len(valid)!=expected:
                missing=True;reasons.append({'category':'data','criterion':key,'message':'Cobertura horaria incompleta para '+variable});continue
            value=min(valid) if operator=='min' else max(valid);metrics[key]={'value':value,'unit':unit,'threshold':prefs[key],'category':category}
            breached=value<prefs[key] if operator=='min' else value>prefs[key]
            if breached:violations+=1
            reasons.append({'criterion':key,'category':category,'breached':breached,
                'message':f'{variable}: {value:g} {unit}; límite configurado {prefs[key]:g}. '+('Fuera del criterio.' if breached else 'Dentro del criterio.')})
        if not any(k in prefs for k in RULES):
            missing=True;reasons.append({'category':'configuration','message':'Definí criterios de la actividad; no se aplican umbrales arbitrarios por defecto.'})
    alerts=alerts or official_alerts()
    official_unknown=alerts['status']!='verified'
    if official_unknown:reasons.append({'category':'safety','message':'Alertas oficiales SMN sin verificación automática. Revisar https://www.smn.gob.ar/alertas.'})
    has_alert=alerts['status']=='verified' and bool(alerts.get('alerts'))
    if has_alert:reasons.append({'category':'safety','message':'Existen alertas oficiales aplicables; revisar el aviso original.'})
    status='insufficient' if missing else 'unfavorable' if violations else 'review' if has_alert or (official_unknown and prefs.get('require_official_alerts',True)) else 'favorable'
    return {'status':status,'label':LABELS[status],'generated_at':utc_now(),'metrics':metrics,'reasons':reasons,
        'violation_count':violations,'event_period':{'start':event['start'],'end':event['end']},
        'activity':event['activity'],'preferences':prefs,'official_alerts':alerts,
        'forecast':{'provider':bundle['provider'],'product':bundle['product'],'fetched_at':bundle['fetched_at'],
            'issued_at':bundle.get('issued_at'),'uncertainty':bundle.get('uncertainty')} if bundle else None,
        'impact':{'status':'insufficient_spatial_evidence','location_precision':'city_centroid'},
        'limitations':['Compatibilidad descriptiva, no probabilidad de seguridad.',
            'Las preferencias son del usuario; los requisitos propios de cada actividad deben acordarse con sus responsables.',
            'Sin validación del sitio exacto ni capas territoriales para inferir impactos urbanos.',
            'La ausencia de bandas de incertidumbre y la falta de alertas verificadas siguen visibles.']}


class PlanningService:
    def __init__(self,weather):self.weather=weather

    def preview(self,event,*,force=False):
        try:
            bundle=self.weather.bundle(event['city_id'],start=datetime.now(timezone.utc).date().isoformat(),
                end=(datetime.now(timezone.utc).date()+timedelta(days=15)).isoformat(),force=force)
            assessment=evaluate(event,bundle)
        except ServiceError as error:
            bundle=None;assessment=evaluate(event,failure=error.code)
        alternatives=[]
        if bundle:
            candidates=[(day,hour) for day in range(-event['flexible_days'],event['flexible_days']+1)
                for hour in range(-event.get('flexible_hours',0),event.get('flexible_hours',0)+1) if day or hour]
            for offset,hour in candidates:
                start=stamp(event['start'])+timedelta(days=offset,hours=hour);end=stamp(event['end'])+timedelta(days=offset,hours=hour)
                if start<=datetime.now(timezone.utc):continue
                candidate={**event,'start':start.isoformat(),'end':end.isoformat()}
                result=evaluate(candidate,bundle)
                if result['status']=='insufficient':continue
                alternatives.append({'start':candidate['start'],'end':candidate['end'],'offset_days':offset,'offset_hours':hour,
                    'assessment':result,'explanation':f"{result['violation_count']} criterios incumplidos; duración conservada, desplazamiento {offset} días y {hour} horas. "
                        'Orden por datos suficientes, criterios incumplidos y cercanía a la fecha original. Alertas y límites se conservan.'})
            alternatives.sort(key=lambda a:(a['assessment']['status']=='unfavorable',a['assessment']['violation_count'],abs(a['offset_days']*24+a['offset_hours']),a['start']))
        return {'assessment':assessment,'alternatives':alternatives,'bundle':bundle}


def decision_key(assessment):
    # Las diferencias numéricas se conservan en snapshots; se notifica sólo un cambio de decisión.
    import json
    return hashlib.sha256(json.dumps({'status':assessment['status'],
        'criteria':[(r.get('criterion'),r.get('breached'),r.get('code')) for r in assessment['reasons']],
        'alerts':assessment['official_alerts']},sort_keys=True).encode()).hexdigest()
