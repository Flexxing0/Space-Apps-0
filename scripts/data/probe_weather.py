"""Piloto real acotado: pronóstico y dos históricos para Comodoro. No agrega fixtures."""
from datetime import datetime,timezone,timedelta
import json
from app import create_app
from services.api_service import ServiceError

def main():
    app=create_app();service=app.extensions['earthlens_weather'];today=datetime.now(timezone.utc).date()
    rows=[]
    for kind,start,end in [('forecast',today.isoformat(),(today+timedelta(days=6)).isoformat()),
            ('power-daily','2017-03-29','2017-04-08'),('reanalysis','2017-03-29','2017-04-08')]:
        try:
            result=service.bundle('comodoro-rivadavia',kind,start,end)
            row={'city_id':'comodoro-rivadavia','kind':kind,'product':result['product'],'status':'ok',
                'period':{'start':start,'end':end},'series':len(result['variables']),
                'records':sum(len(v['series']) for v in result['variables'].values()),
                'missing':sum(p['value'] is None for v in result['variables'].values() for p in v['series']),
                'units':{k:v['unit'] for k,v in result['variables'].items()},'fetched_at':result['fetched_at'],'issued_at':result['issued_at']}
        except ServiceError as error:row={'kind':kind,'status':'error','code':error.code,'message':error.message}
        rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
    return int(any(r['status']!='ok' for r in rows))

if __name__=='__main__':raise SystemExit(main())
