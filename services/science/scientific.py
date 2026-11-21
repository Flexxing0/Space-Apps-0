"""Contrato multiproveedor independiente del motor OLS y de su familia Radar."""

from datetime import date, datetime, timezone
from copy import deepcopy
import json
import math
from pathlib import Path
import re
from threading import RLock

from services.science.analysis_results import content_hash
from services.api_service import ServiceError
from services.providers.bulk import make_query, validate_period, validate_power_data
from services.providers.cache import JsonCache, parse_timestamp, utc_now
from services.providers import power


SCHEMA = "earthlens.scientific-series.v1"


def validate_record(record):
    if (not isinstance(record, dict) or record.get("schema_version") != SCHEMA
            or record.get("location", {}).get("country_code") != "AR"):
        raise ValueError("Serie científica incompatible o fuera del catálogo argentino")
    for field in ("provider", "product", "variable", "unit", "frequency", "cache_version"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise ValueError(f"Falta {field}")
    for field in ("metadata", "spatial_resolution"):
        if not isinstance(record.get(field), dict) or not record[field]:
            raise ValueError(f"Falta {field}")
    validate_period(record["period"]["start_year"], record["period"]["end_year"])
    parse_timestamp(record.get("fetched_at"))
    dates = []
    valid = 0
    for point in record.get("series", []):
        stamp = date.fromisoformat(point["date"])
        if not record["period"]["start_year"] <= stamp.year <= record["period"]["end_year"]:
            raise ValueError("Fecha fuera del período solicitado")
        value = point["value"]
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Valor científico no finito")
            valid += 1
        dates.append(point["date"])
    if not dates or dates != sorted(set(dates)):
        raise ValueError("Fechas ausentes, repetidas o desordenadas")
    if record.get("coverage") != {"expected_count": len(dates), "valid_count": valid, "missing_count": len(dates) - valid}:
        raise ValueError("Cobertura inconsistente")
    if not isinstance(record.get("provenance"), dict) or not record["provenance"].get("source_urls"):
        raise ValueError("Falta procedencia científica")
    content_hash(record)  # Rechaza NaN también en QA/metadatos.
    return record


def make_record(*, provider, product, product_version, cache_version, variable, unit,
                location, period, frequency, resolution, series, fetched_at, metadata, provenance):
    values = sum(point["value"] is not None for point in series)
    return validate_record({
        "schema_version": SCHEMA, "provider": provider, "product": product,
        "product_version": product_version, "cache_version": cache_version,
        "variable": variable, "unit": unit, "location": location, "period": period,
        "frequency": frequency, "spatial_resolution": resolution,
        "series": series, "fetched_at": fetched_at,
        "coverage": {"expected_count": len(series), "valid_count": values, "missing_count": len(series) - values},
        "metadata": metadata, "provenance": provenance,
        "analysis": {"enabled": False, "reason": "Native series; methodology must be approved before new analyses or Radar membership."},
    })


class ScientificStore:
    """Cada proveedor/producto/revisión/variable tiene su propio espacio de caché."""

    def __init__(self, root):
        self.root = Path(root)

    def cache(self, provider, product, version, variable):
        fields = (provider, product, version, variable)
        if any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) or ".." in value for value in fields):
            raise ValueError("Identificador de caché inválido")
        return JsonCache(self.root.joinpath("series", *fields))

    def query(self, provider, product, version, variable, city, period, processing):
        return {"provider": provider, "product": product, "cache_version": version, "variable": variable,
                "city_id": city["id"], "latitude": city["latitude"], "longitude": city["longitude"],
                **period, "processing": processing}

    def read(self, query):
        entry = self.cache(query["provider"], query["product"], query["cache_version"], query["variable"]).read(query)
        if entry is None:
            return None
        record = validate_record(entry["data"]["record"])
        if entry["data"].get("sha256") != content_hash(record):
            raise ValueError("Integridad científica inválida")
        self._validate_identity(query, record)
        return record

    @staticmethod
    def _validate_identity(query, record):
        for field in ("provider", "product", "cache_version", "variable"):
            if record[field] != query[field]:
                raise ValueError("Identidad de serie incompatible")
        if (record["period"] != {key: query[key] for key in ("start_year", "end_year")}
                or record["location"]["id"] != query["city_id"]
                or any(record["location"][key] != query[key] for key in ("latitude", "longitude"))):
            raise ValueError("Ubicación o período incompatible")

    def write(self, query, record):
        validate_record(record)
        self._validate_identity(query, record)
        previous = self.read(query)
        if previous == record:
            return  # Un acierto idéntico no cambia fecha, bytes ni mtime.
        if previous:
            if any(previous[key] != record[key] for key in ("unit", "frequency", "spatial_resolution", "product_version")):
                raise ValueError("Unidades, versión o resolución cambiaron sin una nueva identidad de producto")
            old = {point["date"]: point["value"] for point in previous["series"]}
            new = {point["date"]: point["value"] for point in record["series"]}
            if any(value is not None and new.get(day) is None for day, value in old.items()):
                raise ValueError("La respuesta perdería datos científicos válidos")
        cache = self.cache(query["provider"], query["product"], query["cache_version"], query["variable"])
        cache.write(query, {"record": record, "sha256": content_hash(record)}, record["fetched_at"], location=record["location"])

    def inventory(self):
        result = {}
        for path in self.root.joinpath("series").glob("*/*/*/*/*.json"):
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
                record = self.read(entry["query"])
                if not record or not record["coverage"]["valid_count"]:
                    continue
                key = (record["provider"], record["product"], record["cache_version"], record["variable"])
                row = result.setdefault(key, {key: record[key] for key in (
                    "provider", "product", "product_version", "cache_version", "variable", "unit", "frequency", "spatial_resolution")})
                row["source_urls"] = record["provenance"]["source_urls"]
                row["quality_policy"] = record["metadata"].get("qa_policy")
                row.setdefault("verification", []).append({"city_id": record["location"]["id"], "period": record["period"],
                                                          "coverage": record["coverage"], "fetched_at": record["fetched_at"]})
                row["available"] = True
            except (ValueError, OSError, KeyError, TypeError):
                continue  # Una entrada corrupta no habilita una variable.
        return list(result.values())


class ScientificService:
    def __init__(self, data_service, root=None):
        self.data_service = data_service
        self.store = ScientificStore(root or Path(data_service.bulk.cache.directory).parent / "science")
        self._lock = RLock()
        self._providers = {}

    def variables(self):
        records = self.store.inventory()
        # El contrato POWER histórico permanece intacto; la disponibilidad se comprueba sin red.
        available = {}
        cities_by_position = {(city["latitude"], city["longitude"]): city for city in self.data_service.list_cities()}
        for path in self.data_service.bulk.cache.directory.glob("*.json"):
            try:
                query = json.loads(path.read_text(encoding="utf-8"))["query"]
                city = cities_by_position.get((query["latitude"], query["longitude"]))
                if city is None:
                    continue
                entry = self.data_service.bulk.cache.read(query)
                if entry is None:
                    continue
                quality = validate_power_data(entry["data"], query)
                for code, row in entry["data"].items():
                    item = available.setdefault(code, {"provider": "power", "product": "POWER_MONTHLY_AG", "product_version": None,
                                                      "variable": code, "name": power.VARIABLES[code]["name"], "unit": row["unit"],
                                                      "frequency": "monthly", "available": True, "verification": [],
                                                      "spatial_resolution": {"latitude_degrees": 0.5, "longitude_degrees": 0.625},
                                                      "source_urls": [power.BASE_URL], "sources": row["metadata"]["header"].get("sources", []),
                                                      "quality_policy": "complete-monthly-grid-preserve-provider-null-v1"})
                    item["verification"].append({"city_id": city["id"], "period": {key: query[key] for key in ("start_year", "end_year")},
                                                  "coverage": quality[code], "fetched_at": entry["fetched_at"]})
            except (ValueError, OSError, KeyError, TypeError):
                continue
        return list(available.values()) + [row for row in records if row["provider"] != "power"]

    def fetch(self, *, provider, city_id, variables, start_year=2000, end_year=2024, force=False, access=None):
        with self._lock:
            return self._fetch(provider=provider, city_id=city_id, variables=variables,
                               start_year=start_year, end_year=end_year, force=force, access=access)

    def _cached_selection(self,provider,city,variables,period,access):
        """Recorta una única extracción compatible; no mezcla versiones ni inventa meses."""
        groups={}
        for path in (self.store.root/'series'/provider).glob('*/*/*/*.json'):
            try:
                query=json.loads(path.read_text(encoding='utf-8'))['query']
                if (query['city_id']!=city['id'] or query['variable'] not in variables
                        or query['latitude']!=city['latitude'] or query['longitude']!=city['longitude']
                        or query['start_year']>period['start_year'] or query['end_year']<period['end_year']
                        or (access=='giovanni' and 'giovanni' not in query['cache_version'])):continue
                record=self.store.read(query)
                if record is None:continue
                key=(query['product'],record['product_version'],query['cache_version'],query.get('processing'),query['start_year'],query['end_year'])
                groups.setdefault(key,{})[query['variable']]=record
            except (ValueError,KeyError,TypeError,OSError):continue
        candidates=[rows for rows in groups.values() if all(v in rows for v in variables)]
        def priority(rows):
            sample=rows[variables[0]]
            return (sample['product_version'] is None,'giovanni' in sample['cache_version'],
                    sample['period']['end_year']-sample['period']['start_year'],sample['cache_version'])
        for rows in sorted(candidates,key=priority):
            selected=[]
            for code in variables:
                original=rows[code]
                if original['period']==period:selected.append(original);continue
                record=deepcopy(original)
                record['series']=[p for p in record['series'] if period['start_year']<=int(p['date'][:4])<=period['end_year']]
                if not record['series']:break
                record['period']=dict(period)
                n=len(record['series']);valid=sum(p['value'] is not None for p in record['series'])
                record['coverage']={'expected_count':n,'valid_count':valid,'missing_count':n-valid}
                record['provenance']['cache_selection']={'source_period':original['period'],'requested_period':dict(period),
                    'operation':'date_filter_only','source_fetched_at':original['fetched_at']}
                selected.append(validate_record(record))
            if len(selected)==len(variables):return selected
        return None

    def _power_source_period(self,city,period):
        candidates=[];bulk=self.data_service.bulk
        for path in bulk.cache.directory.glob('*.json'):
            try:
                query=json.loads(path.read_text(encoding='utf-8'))['query']
                if (query!=make_query(city['latitude'],city['longitude'],query['start_year'],query['end_year'])
                        or query['start_year']>period['start_year'] or query['end_year']<period['end_year']):continue
                entry=bulk.cache.read(query)
                if entry is None:continue
                validate_power_data(entry['data'],query)
                age=(datetime.now(timezone.utc)-parse_timestamp(entry['fetched_at'])).total_seconds()
                if age<0 or (bulk.max_age_days is not None and age>=bulk.max_age_days*86400):continue
                candidates.append({k:query[k] for k in ('start_year','end_year')})
            except (ValueError,KeyError,TypeError,OSError):continue
        return min(candidates,key=lambda p:p['end_year']-p['start_year']) if candidates else period

    def _fetch(self, *, provider, city_id, variables, start_year=2000, end_year=2024, force=False, access=None):
        city = self.data_service.get_city(city_id)
        validate_period(start_year, end_year)
        if end_year > datetime.now(timezone.utc).year or type(force) is not bool:
            raise ValueError("Período o force inválido")
        if not isinstance(variables, list) or not variables or any(not isinstance(v, str) for v in variables):
            raise ValueError("variables debe ser una lista no vacía")
        variables = list(dict.fromkeys(variables))
        period = {"start_year": start_year, "end_year": end_year}
        if access is not None and (provider not in {"gldas","gpm"} or access != "giovanni"):
            raise ValueError("Método de acceso no admitido")
        if not force and provider in {'modis','gldas','gpm'}:
            cached=self._cached_selection(provider,city,variables,period,access)
            if cached is not None:return cached
        if provider == "gpm" or access == "giovanni":
            from services.providers.giovanni import GiovanniMonthlyClient
            key = provider + ":giovanni"
            self._providers.setdefault(key,GiovanniMonthlyClient(self.store,provider))
            return self._providers[key].fetch(city,variables,period,force=force)
        if provider == "power":
            source_period=period if force else self._power_source_period(city,period)
            data, meta = self.data_service.get_data({"city_id": city_id, "variables": variables, **source_period, "force": force})
            records = []
            for code, row in data["variables"].items():
                api_version = row["metadata"]["header"]["api"]["version"]
                revision = "unreported-api-" + api_version
                record = make_record(provider="power", product="POWER_MONTHLY_AG", product_version=None,
                    cache_version=revision, variable=code, unit=row["unit"], location=city, period=period,
                    frequency="monthly", resolution={"latitude_degrees": 0.5, "longitude_degrees": 0.625},
                    series=[{"date": point["date"] + "-01", "value": point["value"]} for point in row["series"]
                            if start_year<=int(point['date'][:4])<=end_year],
                    fetched_at=meta["fetched_at"], metadata=row["metadata"],
                    provenance={"origin": meta["origin"], "source_urls": [power.BASE_URL],
                                "cache_selection":{"source_period":source_period,"requested_period":period,"operation":"date_filter_only"},
                                "date_semantics": "First day labels the monthly period; not an instantaneous observation."})
                query = self.store.query("power", record["product"], revision, code, city, period, "legacy-monthly-v1")
                self.store.write(query, record)
                records.append(record)
            return records
        if provider == "modis":
            from services.providers.modis import ModisProvider
            self._providers.setdefault("modis", ModisProvider(self.store))
            return self._providers["modis"].fetch(city, variables, period, force=force)
        if provider == "gldas":
            from services.providers.gldas import GldasProvider
            self._providers.setdefault("gldas", GldasProvider(self.store))
            return self._providers["gldas"].fetch(city, variables, period, force=force)
        raise ValueError("Proveedor no registrado")
