"""Auditoría local de TimesFM. No descarga pesos ni devuelve credenciales/rutas privadas."""
import importlib.util
import json
from pathlib import Path
from services.prediction.prediction import capabilities


def audit():
    modules={name:bool(importlib.util.find_spec(name)) for name in ('torch','timesfm','timesfm3')}
    roots=[Path('models/timesfm-3.0'),Path.home()/'.cache/huggingface/hub/models--google--timesfm-3.0-pytorch']
    checkpoints=sum(1 for root in roots for p in root.glob('**/*') if p.is_file() and p.suffix in {'.safetensors','.bin','.pt'})
    reports=[]
    for path in Path('data/cache/reports').glob('*backtest*.json'):
        try:
            row=json.loads(path.read_text(encoding='utf-8'))
            reports.append({'report':path.name,'timesfm_validated':row.get('timesfm_validated') is True,
                'models':sorted({r['model'] for r in row.get('rows',[])})})
        except (OSError,ValueError,KeyError):continue
    try:
        limit=Path('/sys/fs/cgroup/memory.max').read_text().strip()
        memory_limit=int(limit) if limit!='max' else None
    except (OSError,ValueError):memory_limit=None
    return {**capabilities(),'installed_dependencies':modules,'local_checkpoint_files':checkpoints,
        'inference_service':False,'time_machine_experimental_predictions':False,'backtest_reports':reports,
        'official_checkpoint_bytes':1322898824,'checkpoint_metadata_verified_at':'2026-11-15',
        'configured_backend_memory_bytes':memory_limit,
        'hardware_note':'Archivo F32 mayor al límite del backend, sin contar PyTorch/activaciones. No se ha verificado inferencia en este entorno.',
        'license_note':'Pesos descargables no habilitados para el producto comercial/productivo. No hay acceso configurado a una vía autorizada Google Cloud.',
        'operational_weather_independent':True}

def main():print(json.dumps(audit(),ensure_ascii=True,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
