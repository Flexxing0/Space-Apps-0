"""Series mensuales oficiales GLDAS/GPM mediante Giovanni in the Cloud."""

import csv
from datetime import datetime
from io import StringIO
import math
import time

import requests

from services.api_service import ServiceError
from services.providers.bulk import validate_period
from services.providers.cache import JsonCache, utc_now
from services.providers.gldas import environment_token
from services.science.scientific import make_record


BASE_URL = "https://api.giovanni.earthdata.nasa.gov"
POLICY = "native-monthly-giovanni-csv-v1"
PRODUCTS = {
    "gldas": {"product":"GLDAS_NOAH025_M","version":"2.1","prefix":"GLDAS_NOAH025_M_2_1_", "resolution":0.25,
              "variables":("SoilMoi0_10cm_inst","SoilMoi10_40cm_inst","SoilMoi40_100cm_inst","SoilMoi100_200cm_inst","Evap_tavg")},
    "gpm": {"product":"GPM_3IMERGM","version":"07","prefix":"GPM_3IMERGM_07_","resolution":0.1,
            "variables":("precipitation",)},
}


def parse_monthly_csv(text, *, product, version, variable, city, period):
    metadata, series, in_data = {}, [], False
    for row in csv.reader(StringIO(text)):
        if not row or not any(value.strip() for value in row):
            continue
        if row == ["Timestamp (UTC)","Data"]:
            in_data = True
            continue
        if len(row) != 2:
            raise ValueError("CSV Giovanni inesperado; no se supusieron columnas")
        if not in_data:
            if row[0] in metadata:
                raise ValueError("Metadatos Giovanni duplicados")
            metadata[row[0]] = row[1]
            continue
        stamp = datetime.fromisoformat(row[0])
        value = float(row[1])
        if not math.isfinite(value) or stamp.day != 1 or not period["start_year"] <= stamp.year <= period["end_year"]:
            raise ValueError("Fecha o valor Giovanni inválido")
        series.append({"date":stamp.date().isoformat(),"value":value,"raw_value":value,"source_time":row[0]})
    required = {"prod_name","param_short_name","unit","undef","lat","lon","lat_resolution","lon_resolution","doi"}
    if not in_data or not required <= set(metadata) or not series:
        raise ValueError("Faltan datos o metadatos esenciales Giovanni")
    parameter_names = {variable}
    if product == "GPM_3IMERGM" and variable == "precipitation":
        parameter_names.add("/Grid/precipitation")  # Ruta HDF5 devuelta por el CSV real IMERG V07.
    if metadata["prod_name"] != product + "." + version or metadata["param_short_name"] not in parameter_names:
        raise ValueError("El CSV corresponde a otro producto, versión o variable")
    for axis,key in (("lat","latitude"),("lon","longitude")):
        resolution = float(metadata[axis+"_resolution"])
        coordinate = float(metadata[axis])
        if not math.isfinite(resolution) or resolution <= 0 or not math.isfinite(coordinate) or abs(coordinate-city[key])>resolution/2+1e-6:
            raise ValueError("La celda recibida no corresponde a la ubicación solicitada")
    expected = [f"{year:04d}-{month:02d}-01" for year in range(period["start_year"],period["end_year"]+1) for month in range(1,13)]
    if [row["date"] for row in series] != expected:
        raise ValueError("La serie Giovanni no cubre todos los meses solicitados; no se crearon fechas")
    fill = float(metadata["undef"])
    if not math.isfinite(fill):
        raise ValueError("Valor de relleno Giovanni inválido")
    for row in series:
        missing = row["value"] == fill
        row["quality"] = {"missing":missing,"reason":"provider_fill_value" if missing else None}
        if missing:
            row["value"] = None
    return metadata,series


class GiovanniMonthlyClient:
    def __init__(self, store, provider, request_delay=1.0):
        self.store,self.provider,self.config = store,provider,PRODUCTS[provider]
        self.revision = self.config["version"] + "-giovanni-csv-v1"
        self.raw = JsonCache(store.root / "raw" / "giovanni" / self.config["product"] / self.config["version"])
        self.request_delay,self._last_request = request_delay,None
        self._catalog = None

    def cached(self, city, variables, period):
        rows = [self.store.read(self.store.query(self.provider,self.config["product"],self.revision,v,city,period,POLICY)) for v in variables]
        return rows if rows and all(rows) else None

    def _get(self,url,**kwargs):
        if self._last_request is not None:
            remaining = self.request_delay - (time.monotonic()-self._last_request)
            if remaining>0:time.sleep(remaining)
        self._last_request=time.monotonic()
        response=requests.get(url,timeout=(10,120),**kwargs)
        response.raise_for_status()
        return response

    def fetch(self, city, variables, period, *, force=False):
        validate_period(period["start_year"],period["end_year"])
        if not variables or not set(variables)<=set(self.config["variables"]):
            raise ValueError("Variable no admitida por el adaptador Giovanni")
        cached = None if force else self.cached(city,variables,period)
        if cached:return cached
        result=[]
        for variable in variables:
            params={"data":self.config["prefix"]+variable,
                    "location":f'[{city["latitude"]},{city["longitude"]}]',
                    "time":f'{period["start_year"]}-01-01T00:00:00/{period["end_year"]}-12-31T23:59:59'}
            url=requests.Request("GET",BASE_URL+"/timeseries",params=params).prepare().url
            query={"url":url,"processing":POLICY}
            entry=None if force else self.raw.read(query)
            if entry:
                text,stamp=entry["data"]["csv"],entry["fetched_at"]
            else:
                token = environment_token()
                if not token:
                    raise ServiceError("provider_auth_required","Giovanni requiere Earthdata para descargar nuevas observaciones.")
                if self._catalog is None:
                    self._catalog = self._get(BASE_URL+"/configured-variables").json()["configured_variables"]
                if self.config["prefix"]+variable not in self._catalog:
                    raise ValueError("La variable no figura en el catálogo real de Giovanni")
                response=self._get(url,headers={"Authorization":"Bearer "+token})
                text,stamp=response.text,utc_now()
                if token in text or len(response.content)>2_000_000:
                    raise ValueError("Respuesta Giovanni no apta para almacenar")
            metadata,series=parse_monthly_csv(text,product=self.config["product"],version=self.config["version"],variable=variable,city=city,period=period)
            record=make_record(provider=self.provider,product=self.config["product"],product_version=self.config["version"],cache_version=self.revision,
                variable=variable,unit=metadata["unit"],location=city,period=period,frequency="monthly",
                resolution={"latitude_degrees":float(metadata["lat_resolution"]),"longitude_degrees":float(metadata["lon_resolution"]),"extraction":"nearest_native_grid_cell"},
                series=series,fetched_at=stamp,
                metadata={"csv_header":metadata,"qa_policy":POLICY,"effective_coordinates":{"latitude":float(metadata["lat"]),"longitude":float(metadata["lon"])},
                          "precision_note":"Decimal values exactly as delivered by Giovanni CSV; may be rounded compared with native NetCDF.",
                          "access_method":"NASA Earthdata Giovanni in the Cloud","monthly_semantics":"Native monthly model/product values; no accumulation performed."},
                provenance={"source_urls":[url,"https://doi.org/"+metadata["doi"]],"origin":"remote","date_semantics":"Native monthly timestamps from CSV, without resampling."})
            normalized_query=self.store.query(self.provider,self.config["product"],self.revision,variable,city,period,POLICY)
            self.store.write(normalized_query,record)
            if not entry:self.raw.write(query,{"csv":text},stamp)
            result.append(record)
        return result
