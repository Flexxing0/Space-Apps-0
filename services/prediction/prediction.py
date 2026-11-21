"""Contrato desacoplado para experimentos; no cambia las proyecciones heredadas.

Los pesos TimesFM 3.0 descargables no se habilitan para el producto comercial.
El backtest es reproducible e inyectable: nunca descarga o entrena al importar.
"""
from datetime import date,timedelta
from math import sqrt,isfinite

def capabilities():
    return {'model':'TimesFM 3.0','enabled':False,'implementation':'not_implemented',
        'inference_endpoint':None,'generated_predictions':0,'model_accuracy_backtests':0,
        'status':'blocked_license_and_validation',
        'code_license':'Apache-2.0','weights_license':'timesfm-non-commercial-license-v1.0',
        'reason':'Pesos descargables restringidos a investigación no comercial y no productiva. Backend sin credenciales de un servicio Google Cloud autorizado.',
        'sources':['https://github.com/google-research/timesfm#license-notice-for-pretrained-weights',
            'https://huggingface.co/google/timesfm-3.0-pytorch'],
        'independent_from_operational_weather':True,'validation':'not_run','recommended_dates_enabled':False}


def backtest_daily(series,cuts,horizons=(1,3,7),predictor=None):
    """Cortes son índices exclusivos del entrenamiento; sólo datos diarios contiguos.

    predictor recibe copias del pasado y horizonte; nunca el segmento de evaluación.
    Devuelve {point: [...], lower: [...] opcional, upper: [...] opcional}.
    """
    if not series or any(p['value'] is None or isinstance(p['value'],bool) or not isfinite(p['value']) for p in series):
        raise ValueError('El backtest requiere valores diarios finitos, sin imputación')
    days=[date.fromisoformat(p['date']) for p in series]
    if any(b-a!=timedelta(days=1) for a,b in zip(days,days[1:])):raise ValueError('La serie no es diaria contigua')
    if not cuts or not horizons or any(type(h) is not int or h<1 for h in horizons):raise ValueError('Horizontes inválidos')
    if any(type(c) is not int or c<7 or c+max(horizons)>len(series) for c in cuts):raise ValueError('Cortes inválidos')
    rows=[]
    for cut in cuts:
        train=[float(p['value']) for p in series[:cut]];observed=[float(p['value']) for p in series[cut:cut+max(horizons)]]
        candidates={'persistence':{'point':[train[-1]]*max(horizons)},'seasonal_naive_7d':{'point':[train[-7+i%7] for i in range(max(horizons))]}}
        if predictor is not None:candidates['experimental_model']=predictor(train.copy(),max(horizons))
        for name,result in candidates.items():
            if len(result['point'])<max(horizons) or any(not isfinite(v) for v in result['point']):raise ValueError('Predicción inválida')
            if ('lower' in result)!=('upper' in result):raise ValueError('Intervalo incompleto')
            if 'lower' in result and (len(result['lower'])<max(horizons) or len(result['upper'])<max(horizons) or
                    any(not isfinite(a) or not isfinite(b) or a>b for a,b in zip(result['lower'],result['upper']))):raise ValueError('Bandas inválidas')
            for horizon in horizons:
                errors=[result['point'][i]-observed[i] for i in range(horizon)]
                rows.append({'model':name,'cut_date':series[cut]['date'],'training_last_date':series[cut-1]['date'],
                    'horizon_days':horizon,'n':horizon,'mae':sum(abs(e) for e in errors)/horizon,
                    'rmse':sqrt(sum(e*e for e in errors)/horizon),
                    'interval_coverage':sum(result['lower'][i]<=observed[i]<=result['upper'][i] for i in range(horizon))/horizon if 'lower' in result else None})
    return {'frequency':'daily','rows':rows,'method':'rolling_origin_no_future_access',
        'archived_weather_forecast_comparison':'not_available','timesfm_validated':False}
