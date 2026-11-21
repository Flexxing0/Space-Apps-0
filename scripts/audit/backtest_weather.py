"""Evaluación retrospectiva diaria real de baselines; no es validación TimesFM."""
import argparse
import json
from app import create_app
from services.providers.cache import write_json_atomic
from services.prediction.prediction import backtest_daily

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--city',default='comodoro-rivadavia')
    parser.add_argument('--year',type=int,default=2023);parser.add_argument('--variable',default='T2M');args=parser.parse_args(argv)
    app=create_app();weather=app.extensions['earthlens_weather']
    row=weather.series(args.city,'power-daily',args.variable,f'{args.year}-01-01',f'{args.year}-12-31')
    result=backtest_daily(row['series'],[90,180,270])
    result.update(city_id=args.city,variable=args.variable,unit=row['unit'],provider=row['provider'],product=row['product'],
        provenance=row['provenance'],fetched_at=row['fetched_at'],limitations=['Sin archivo de pronósticos operativos para contrastar.',
        'Baselines de software con datos reales, no validación de un modelo físico ni TimesFM.'])
    path=weather.cache.directory.parent/'reports'/f'backtest-{args.city}-{args.year}-{args.variable}.json'
    write_json_atomic(path,result)
    print(json.dumps({'status':'ok','records':len(row['series']),'evaluation_rows':len(result['rows']),
        'timesfm_validated':False,'report':str(path),'metrics':result['rows']},ensure_ascii=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
