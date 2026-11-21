"""Extracción GLDAS puntual: CMR y subconjuntos NetCDF-3 de OPeNDAP Cloud."""

from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import math
import re
import time
from urllib.parse import urlparse

import requests

from services.science.analysis_results import content_hash
from services.api_service import ServiceError
from services.providers.bulk import validate_period
from services.providers.cache import JsonCache, utc_now, write_json_atomic
from services.science.scientific import make_record


POLICY = "nearest-native-grid-monthly-fill-v1"
MAX_RESPONSE_BYTES = 2_000_000


def json_attribute(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if hasattr(value, "tolist"):
        return json_attribute(value.tolist())
    if isinstance(value, list):
        return [json_attribute(item) for item in value]
    return value


def decode_netcdf(payload):
    from scipy.io import netcdf_file
    if payload[:4] not in (b"CDF\x01", b"CDF\x02"):
        raise ValueError("El subconjunto no es NetCDF-3")
    with netcdf_file(BytesIO(payload), mmap=False, maskandscale=False) as source:
        result = {"attributes": {k: json_attribute(v) for k, v in source._attributes.items()}, "variables": {}}
        for name, variable in source.variables.items():
            result["variables"][name] = {
                "dimensions": list(variable.dimensions), "shape": list(variable.shape),
                "data": variable.data.reshape(-1).tolist(),
                "attributes": {k: json_attribute(v) for k, v in variable._attributes.items()},
            }
    content_hash(result)  # Tampoco se permiten NaN/Infinity en metadatos o valores crudos.
    return result


def source_datetime(variable):
    attributes = variable["attributes"]
    if attributes.get("calendar", "standard") not in {"standard", "gregorian", "proleptic_gregorian"}:
        raise ValueError("Calendario GLDAS no admitido")
    match = re.fullmatch(r"(seconds|minutes|hours|days) since (.+)", attributes["units"])
    if not match or len(variable["data"]) != 1:
        raise ValueError("Coordenada temporal GLDAS inválida")
    reference = datetime.fromisoformat(match[2].replace(" UTC", "+00:00").replace("Z", "+00:00"))
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return reference + timedelta(**{match[1]: float(variable["data"][0])})


def unpack_value(variable):
    if variable["dimensions"] != ["time", "lat", "lon"] or variable["shape"] != [1, 1, 1]:
        raise ValueError("Se esperaba exactamente un píxel y un tiempo GLDAS")
    attributes = variable["attributes"]
    if not attributes.get("units") or "_FillValue" not in attributes:
        raise ValueError("Faltan unidades o valor de relleno GLDAS")
    raw = variable["data"][0]
    missing = raw == attributes["_FillValue"] or raw == attributes.get("missing_value")
    scale, offset = attributes.get("scale_factor", 1), attributes.get("add_offset", 0)
    value = None if missing else raw * scale + offset
    if value is not None and not math.isfinite(value):
        raise ValueError("Valor GLDAS no finito")
    return raw, value, {"missing": missing, "reason": "provider_fill_value" if missing else None}


class GldasPointClient:
    def __init__(self, store, request_delay=1.0):
        from services.providers.gldas import PRODUCT, VERSION
        self.store = store
        self.product, self.version = PRODUCT, VERSION
        self.cache = JsonCache(store.root / "raw" / "gldas" / PRODUCT / VERSION)
        self.request_delay = request_delay
        self._last_request = None

    def _pace(self):
        if self._last_request is not None:
            remaining = self.request_delay - (time.monotonic() - self._last_request)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request = time.monotonic()

    def _granules(self, period, force):
        from services.providers.gldas import CMR
        query = {"kind": "cmr-granules", "product": self.product, "version": self.version, **period}
        cached = None if force else self.cache.read(query)
        if cached:
            return cached["data"]
        self._pace()
        response = requests.get(CMR + "/collections.json", params={"short_name": self.product, "version": self.version}, timeout=40)
        response.raise_for_status()
        collections = [row for row in response.json()["feed"]["entry"] if row["short_name"] == self.product and row["version_id"] == self.version]
        if len(collections) != 1:
            raise ValueError("Colección GLDAS ambigua o ausente")
        collection = collections[0]["id"]
        start, end = period["start_year"], period["end_year"]
        expected = [f"{year:04d}-{month:02d}" for year in range(start, end + 1) for month in range(1, 13)]
        result = {"collection_id": collection, "months": {}}
        page = 1
        while True:
            self._pace()
            response = requests.get(CMR + "/granules.json", params={"collection_concept_id": collection,
                "temporal": f"{start}-01-01T00:00:00Z,{end}-12-31T23:59:59Z", "page_size": 2000, "page_num": page}, timeout=40)
            response.raise_for_status()
            entries = response.json()["feed"]["entry"]
            for row in entries:
                match = re.fullmatch(re.escape(self.product) + r"\.A(\d{4})(\d{2})\.021\.nc4", row.get("producer_granule_id", ""))
                if not match:
                    continue
                month = f"{match[1]}-{match[2]}"
                if month not in expected:
                    continue
                urls = [link["href"] for link in row.get("links", []) if urlparse(link.get("href", "")).hostname == "opendap.earthdata.nasa.gov"
                        and urlparse(link["href"]).scheme == "https"]
                if len(urls) != 1 or month in result["months"]:
                    raise ValueError("Enlace puntual GLDAS ambiguo o ausente")
                result["months"][month] = {"url": urls[0], "granule_id": row["id"], "producer_granule_id": row["producer_granule_id"],
                                          "time_start": row["time_start"], "time_end": row["time_end"]}
            if len(entries) < 2000:
                break
            page += 1
        if set(result["months"]) != set(expected):
            raise ValueError("CMR no devolvió todos los meses solicitados; no se crearon meses ausentes")
        self.cache.write(query, result, utc_now())
        return result

    @staticmethod
    def _validate_subset(data, coordinates_only, expected_cell, expected_month):
        variables = data["variables"]
        if coordinates_only:
            if set(variables) != {"lat", "lon"}:
                raise ValueError("La consulta de coordenadas devolvió otras variables")
            return
        from services.providers.gldas import VARIABLES
        if not {"lat", "lon", "time", *VARIABLES} <= set(variables):
            raise ValueError("Faltan variables en el subconjunto GLDAS")
        for key in VARIABLES:
            unpack_value(variables[key])
        if any(variables[a]["data"] != [expected_cell[k]] for a,k in (("lat","latitude"),("lon","longitude"))):
            raise ValueError("El servidor no respetó las coordenadas del subconjunto")
        if source_datetime(variables["time"]).strftime("%Y-%m") != expected_month:
            raise ValueError("El servidor devolvió otro mes")

    def _subset(self, base, constraint, token, force, *, coordinates_only=False, expected_cell=None, expected_month=None):
        from services.providers.gldas import public_diagnostic
        url = requests.Request("GET", base + ".nc", params=constraint).prepare().url
        query = {"kind": "opendap-netcdf3", "url": url}
        cached = None if force else self.cache.read(query)
        if cached:
            self._validate_subset(cached["data"], coordinates_only, expected_cell, expected_month)
            return cached
        self._pace()
        with requests.get(url, headers={"Authorization": "Bearer " + token}, timeout=(10, 90), stream=True) as response:
            if response.status_code != 200:
                write_json_atomic(self.store.root / "discovery" / "gldas-last-request-error.json", {
                    "fetched_at": utc_now(), "request_url": url, "http_status": response.status_code,
                    "diagnostic": public_diagnostic(response, token)})
                raise ServiceError("provider_auth_required" if response.status_code == 401 else "provider_error",
                                   "GLDAS no devolvió el subconjunto solicitado.", details={"http_status": response.status_code})
            chunks, length = [], 0
            for chunk in response.iter_content(65536):
                length += len(chunk)
                if length > MAX_RESPONSE_BYTES:
                    raise ValueError("El servidor no respetó el tamaño del subconjunto puntual")
                chunks.append(chunk)
            data = decode_netcdf(b"".join(chunks))
        self._validate_subset(data, coordinates_only, expected_cell, expected_month)
        if token in json.dumps(data):
            raise ValueError("La respuesta incluyó una credencial y no se guardó")
        previous = self.cache.read(query) if force else None
        if previous and not coordinates_only:
            from services.providers.gldas import VARIABLES
            for key in VARIABLES:
                old_value = unpack_value(previous["data"]["variables"][key])[1]
                new_value = unpack_value(data["variables"][key])[1]
                if old_value is not None and new_value is None:
                    raise ValueError("La respuesta degradaría un valor crudo GLDAS válido")
        stamp = utc_now()
        self.cache.write(query, data, stamp)
        return {"data": data, "fetched_at": stamp}

    def fetch(self, city, variables, period, *, force=False):
        from services.providers.gldas import VARIABLES, environment_token
        validate_period(period["start_year"], period["end_year"])
        if period["start_year"] < 2000 or not variables or not set(variables) <= set(VARIABLES):
            raise ValueError("Período o variables fuera del producto GLDAS 2.1")
        queries = {v: self.store.query("gldas", self.product, self.version, v, city, period, POLICY) for v in variables}
        if not force:
            cached = [self.store.read(queries[v]) for v in variables]
            if all(cached):
                return cached
        token = environment_token()
        if not token:
            raise ServiceError("provider_auth_required", "GLDAS requiere Earthdata configurado para descargar observaciones.")
        listing = self._granules(period, force)
        first = next(iter(sorted(listing["months"])))
        axes = self._subset(listing["months"][first]["url"], "lat,lon", token, force, coordinates_only=True)
        coordinates = axes["data"]["variables"]
        indices, selected = {}, {}
        for axis, key in (("lat", "latitude"), ("lon", "longitude")):
            values = coordinates[axis]["data"]
            if len(values) < 2 or any(not math.isfinite(v) for v in values) or any(abs(b-a-0.25)>1e-6 for a,b in zip(values,values[1:])):
                raise ValueError("Grilla GLDAS distinta de la esperada; no se supusieron coordenadas")
            index = min(range(len(values)), key=lambda i: abs(values[i]-city[key]))
            if abs(values[index]-city[key]) > 0.125 + 1e-6:
                raise ValueError("Ubicación fuera de la grilla GLDAS")
            indices[axis], selected[key] = index, values[index]
        i, j = indices["lat"], indices["lon"]
        constraint = f"lat[{i}],lon[{j}],time[0]," + ",".join(f"{v}[0][{i}][{j}]" for v in VARIABLES)
        series = {v: [] for v in VARIABLES}
        metadata, requests_used, fetched = {}, [], []
        for month, granule in sorted(listing["months"].items()):
            subset = self._subset(granule["url"], constraint, token, force, expected_cell=selected, expected_month=month)
            values = subset["data"]["variables"]
            if any(values[a]["data"] != [selected[k]] for a,k in (("lat","latitude"),("lon","longitude"))):
                raise ValueError("Las coordenadas efectivas cambiaron o el servidor ignoró el subconjunto")
            actual_time = source_datetime(values["time"])
            if actual_time.strftime("%Y-%m") != month:
                raise ValueError("El tiempo devuelto no corresponde al mes del gránulo")
            for code in VARIABLES:
                raw, value, quality = unpack_value(values[code])
                attributes = values[code]["attributes"]
                essential = ("units", "_FillValue", "missing_value", "scale_factor", "add_offset")
                if code in metadata and any(metadata[code].get(k) != attributes.get(k) for k in essential):
                    raise ValueError("Unidades o metadatos de variable cambiaron dentro de la serie")
                metadata[code] = attributes
                series[code].append({"date": month + "-01", "value": value, "raw_value": raw, "quality": quality,
                                     "source_time": actual_time.isoformat(), "granule_id": granule["granule_id"]})
            requests_used.append({"url": requests.Request("GET", granule["url"] + ".nc", params=constraint).prepare().url,
                                  "fetched_at": subset["fetched_at"], "granule": granule,
                                  "global_attributes": subset["data"]["attributes"], "time": values["time"]["attributes"],
                                  "parameters":{code:values[code]["attributes"] for code in VARIABLES}})
            fetched.append(subset["fetched_at"])
        records = []
        for code in VARIABLES:
            records.append(make_record(provider="gldas", product=self.product, product_version=self.version, cache_version=self.version,
                variable=code, unit=metadata[code]["units"], location=city, period=period, frequency="monthly",
                resolution={"latitude_degrees":0.25,"longitude_degrees":0.25,"extraction":"nearest_native_grid_cell"},
                series=series[code], fetched_at=max(fetched),
                metadata={"parameter":metadata[code],"depth_cm":VARIABLES[code].get("depth_cm"),"collection_id":listing["collection_id"],
                          "qa_policy":POLICY,"grid_indices":indices,"effective_coordinates":selected,"source_grid_coordinates":coordinates,
                          "requests":requests_used,"monthly_semantics":"Monthly mean of model outputs; not a monthly accumulation."},
                provenance={"source_urls":[r["url"] for r in requests_used],"origin":"remote",
                            "date_semantics":"First day labels monthly period; source_time preserves actual coordinate."}))
        for record in records:
            query = self.store.query("gldas", self.product, self.version, record["variable"], city, period, POLICY)
            self.store.write(query, record)
        return [record for record in records if record["variable"] in variables]
