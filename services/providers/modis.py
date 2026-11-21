"""MOD13Q1 puntual mediante ORNL DAAC; frecuencia nativa y QA explícita."""

import json
import re
import time

import requests

from services.science.analysis_results import content_hash
from services.providers.cache import utc_now, write_json_atomic
from services.science.scientific import make_record


BASE_URL = "https://modis.ornl.gov/rst/api/v1"
PRODUCT = "MOD13Q1"
BANDS = {"NDVI": "250m_16_days_NDVI", "EVI": "250m_16_days_EVI"}
RELIABILITY = "250m_16_days_pixel_reliability"
VI_QUALITY = "250m_16_days_VI_Quality"
QA_POLICY = "good-reliability-modland-no-cloud-snow-shadow-v1"


def decode_quality(reliability, vi_quality):
    if type(reliability) is not int or type(vi_quality) is not int:
        raise ValueError("Banderas QA inválidas")
    reasons = []
    if reliability != 0:
        reasons.append("reliability_not_good")
    if vi_quality < 0 or vi_quality > 65534 or vi_quality & 3:
        reasons.append("modland_not_good")
    for bit, name in ((8, "adjacent_cloud"), (10, "mixed_cloud"), (14, "snow_ice"), (15, "shadow")):
        if vi_quality >= 0 and vi_quality & (1 << bit):
            reasons.append(name)
    return {"pixel_reliability": reliability, "vi_quality": vi_quality,
            "modland": vi_quality & 3 if vi_quality >= 0 else None,
            "land_water_mask": (vi_quality >> 11) & 7 if vi_quality >= 0 else None,
            "accepted": not reasons, "reasons": reasons}


class ModisProvider:
    def __init__(self, store, request_delay=1.0):
        self.store = store
        self.request_delay = request_delay
        self._last_request = None

    def _json(self, resource, params=None, *, force=False):
        url = requests.Request("GET", BASE_URL + resource, params=params).prepare().url
        path = self.store.root / "raw" / "modis" / (content_hash(url) + ".json")
        if path.exists() and not force:
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                if saved["url"] == url and isinstance(saved["response"], dict):
                    return saved
            except (ValueError, KeyError, OSError):
                pass
        if self._last_request is not None:
            remaining = self.request_delay - (time.monotonic() - self._last_request)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request = time.monotonic()
        response = requests.get(url, timeout=(10, 90), headers={"Accept": "application/json"})
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError("Respuesta ORNL inválida")
        required = "products" if resource == "/products" else "bands" if resource.endswith("/bands") else "dates" if resource.endswith("/dates") else "subset"
        if not isinstance(value.get(required), list) or not value[required]:
            raise ValueError("Respuesta ORNL vacía o incompleta")
        saved = {"url": url, "fetched_at": utc_now(), "response": value}
        write_json_atomic(path, saved)
        return saved

    def _subsets(self, batch, coordinates, force):
        try:
            return [self._json(f"/{PRODUCT}/subset", {**coordinates, "startDate": batch[0]["modis_date"],
                               "endDate": batch[-1]["modis_date"], "kmAboveBelow": 0, "kmLeftRight": 0}, force=force)]
        except requests.HTTPError as error:
            if error.response is None or error.response.status_code not in {502, 503, 504} or len(batch) <= 1:
                raise
            middle = len(batch) // 2
            return self._subsets(batch[:middle], coordinates, force) + self._subsets(batch[middle:], coordinates, force)

    def fetch(self, city, variables, period, *, force=False):
        if not set(variables) <= set(BANDS):
            raise ValueError("MODIS sólo admite NDVI y EVI en este adaptador")
        if not force:
            for version in (self.store.root/'series'/'modis'/PRODUCT).glob('*-ornl-order-v1'):
                cached=[self.store.read(self.store.query('modis',PRODUCT,version.name,code,city,period,QA_POLICY)) for code in variables]
                if cached and all(cached):return cached
        products = self._json("/products", force=force)
        product = next((row for row in products["response"]["products"] if row["product"] == PRODUCT), None)
        if product is None:
            raise ValueError("MOD13Q1 no está en el catálogo real ORNL")
        bands = self._json(f"/{PRODUCT}/bands", force=force)
        metadata = {row["band"]: row for row in bands["response"]["bands"]}
        if not {RELIABILITY, VI_QUALITY, *BANDS.values()} <= set(metadata):
            raise ValueError("Faltan bandas científicas o QA")
        # La API no declara colección en sus respuestas. No inventar '061'.
        revision = "unreported-v1-" + content_hash({"product": product, "bands": metadata})[:12]
        queries = {code: self.store.query("modis", PRODUCT, revision, code, city, period, QA_POLICY) for code in variables}
        if not force:
            cached = {code: self.store.read(query) for code, query in queries.items()}
            if all(cached.values()):
                return [cached[code] for code in variables]
        coordinates = {"latitude": city["latitude"], "longitude": city["longitude"]}
        dates_response = self._json(f"/{PRODUCT}/dates", coordinates, force=force)
        dates = [row for row in dates_response["response"]["dates"]
                 if period["start_year"] <= int(row["calendar_date"][:4]) <= period["end_year"]]
        dates.sort(key=lambda row: row["calendar_date"])
        if not dates or len({row["calendar_date"] for row in dates}) != len(dates):
            raise ValueError("No hay fechas MODIS válidas para el período")
        rows = {}
        sources = [products["url"], bands["url"], dates_response["url"]]
        retrieved = []
        grid = None
        batches = [dates[index:index + 2] for index in range(0, len(dates), 2)]
        for batch in batches:
            for result in self._subsets(batch, coordinates, force):
                self._collect_rows(result, {row["calendar_date"] for row in batch}, rows)
                value = result["response"]
                grid_metadata = {key: value[key] for key in ("xllcorner", "yllcorner", "cellsize", "nrows", "ncols")}
                if grid is not None and grid != grid_metadata:
                    raise ValueError("La grilla cambió durante la consulta")
                grid = grid_metadata
                sources.append(result["url"])
                retrieved.append(result["fetched_at"])
        records = []
        for code, band in BANDS.items():
            records.append(self._record(code, band, metadata, dates, rows, grid, city, period, product, revision, sources, retrieved))
        for record in records:
            query = self.store.query("modis", PRODUCT, revision, record["variable"], city, period, QA_POLICY)
            self.store.write(query, record)
        return [record for record in records if record["variable"] in variables]

    def _collect_rows(self, result, expected_dates, rows):
        value = result["response"]
        if value.get("nrows") != 1 or value.get("ncols") != 1:
            raise ValueError("Se esperaba un solo píxel, sin promedio espacial")
        for row in value.get("subset", []):
            if row["band"] not in {RELIABILITY, VI_QUALITY, *BANDS.values()}:
                continue
            key = (row["calendar_date"], row["band"])
            if key in rows or key[0] not in expected_dates or len(row["data"]) != 1:
                raise ValueError("Respuesta MODIS duplicada, incompleta o de otra geometría")
            rows[key] = row

    def _record(self, code, band, metadata, dates, rows, grid, city, period, product, revision, sources, retrieved):
        band_metadata = metadata[band]
        scale = float(band_metadata["scale_factor"])
        offset = float(band_metadata.get("add_offset", 0))
        fill = float(band_metadata["fill_value"])
        bounds = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", band_metadata["valid_range"])]
        if len(bounds) != 2 or scale <= 0:
            raise ValueError("Escala o rango MODIS inválido")
        series = []
        for stamp in dates:
            day = stamp["calendar_date"]
            if any((day, name) not in rows for name in (band, RELIABILITY, VI_QUALITY)):
                raise ValueError("Falta un valor o su bandera QA; no se fabricó un registro")
            observation = rows[(day, band)]
            raw = observation["data"][0]
            qa = decode_quality(rows[(day, RELIABILITY)]["data"][0], rows[(day, VI_QUALITY)]["data"][0])
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError("Valor MODIS no numérico")
            if raw == fill:
                qa["reasons"].append("fill_value")
            elif not bounds[0] <= raw <= bounds[1]:
                qa["reasons"].append("outside_valid_range")
            qa["accepted"] = not qa["reasons"]
            series.append({"date": day, "value": raw * scale + offset if qa["accepted"] else None,
                           "raw_value": raw, "quality": qa, "tile": observation.get("tile"),
                           "processing_date": observation.get("proc_date")})
        record = make_record(provider="modis", product=PRODUCT, product_version=None, cache_version=revision,
            variable=code, unit=band_metadata["units"], location=city, period=period, frequency="16-day composite",
            resolution={"nominal_meters": product["resolution_meters"], "grid_cellsize_meters": grid["cellsize"],
                        "extraction": "single_native_pixel", "projection": "MODIS sinusoidal"},
            series=series, fetched_at=max(retrieved),
            metadata={"product": product, "band": band_metadata, "qa_bands": [metadata[RELIABILITY], metadata[VI_QUALITY]],
                      "grid": grid, "qa_policy": QA_POLICY, "scale_applied": scale, "offset_applied": offset,
                      "collection_version_verified": False, "collection_version_note": "ORNL REST does not identify the collection in this response.",
                      "source_date_count": len(dates), "first_composite": dates[0]["calendar_date"],
                      "last_composite": dates[-1]["calendar_date"]},
            provenance={"origin": "remote", "source_urls": sources, "request_fetched_at": retrieved,
                        "quality_guide": "https://modis-land.gsfc.nasa.gov/pdf/MOD13_User_Guide_V61.pdf"})
        return record
