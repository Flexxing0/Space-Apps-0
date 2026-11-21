"""Obtiene una respuesta real de Giovanni para inspección; no publica variables."""

import argparse
import json
from pathlib import Path

import requests

from services.providers.cache import DEFAULT_CACHE_DIR, utc_now, write_json_atomic
from services.geography.cities import get_city
from services.providers.gldas import environment_token, public_diagnostic


BASE_URL = "https://api.giovanni.earthdata.nasa.gov"


def probe(city_id, variable, start_year, end_year, *, root=None):
    from services.providers.bulk import validate_period
    validate_period(start_year,end_year)
    city = get_city(city_id)
    if city is None:
        raise ValueError("Seleccionar una ciudad del catálogo argentino")
    token = environment_token()
    if not token:
        raise ValueError("EARTHDATA_TOKEN no está configurado en este proceso")
    root = Path(root or DEFAULT_CACHE_DIR.parent / "science")
    catalog = requests.get(BASE_URL + "/configured-variables",timeout=40)
    catalog.raise_for_status()
    if variable not in catalog.json()["configured_variables"]:
        raise ValueError("Variable no anunciada por el catálogo real Giovanni")
    params = {"data":variable,"location":json.dumps([city["latitude"],city["longitude"]],separators=(",",":")),
              "time":f"{start_year}-01-01T00:00:00/{end_year}-12-31T23:59:59"}
    response = requests.get(BASE_URL + "/timeseries",params=params,headers={"Authorization":"Bearer " + token},timeout=(10,120))
    if token in response.text:
        raise ValueError("La respuesta incluyó una credencial y no se guardó")
    if len(response.content)>2_000_000:
        raise ValueError("La respuesta excedió el tamaño puntual esperado")
    result = {"city_id":city_id,"variable":variable,"period":{"start_year":start_year,"end_year":end_year},
              "request_url":response.url,"fetched_at":utc_now(),"http_status":response.status_code,
              "content_type":response.headers.get("Content-Type"),"bytes":len(response.content),
              "verification_status":"raw_response_only","variables_enabled":False}
    if response.status_code==200:
        result["body"] = response.text
    else:
        result["diagnostic"] = public_diagnostic(response,token)
    path = root / "discovery" / f"giovanni-{city_id}-{variable}-{start_year}-{end_year}.json"
    write_json_atomic(path,result)
    return result,path


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--city',required=True)
    parser.add_argument('--variable',required=True)
    parser.add_argument('--start-year',type=int,default=2024)
    parser.add_argument('--end-year',type=int,default=2024)
    args=parser.parse_args(argv)
    try:
        result,path=probe(args.city,args.variable,args.start_year,args.end_year)
    except Exception as error:
        print(json.dumps({'status':'error','error_type':type(error).__name__}))
        return 1
    print(json.dumps({**{k:v for k,v in result.items() if k not in {'body','diagnostic'}},'report':str(path)}))
    return int(result['http_status']!=200)


if __name__=='__main__':raise SystemExit(main())
