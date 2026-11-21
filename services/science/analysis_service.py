"""Adaptador del contrato mensual real al motor del equipo (sin modificarlo)."""

from services.api_service import ServiceError, validate_data_request
from services.science import trend_analysis as engine
from services.science.analysis_results import content_hash, make_result, methodology
from services.providers.cache import utc_now


METHOD = {
    "engine": "services.science.trend_analysis (origin/results-charts e33c76d)",
    "regression": "OLS sobre medias aritméticas anuales de meses válidos",
    "min_months_per_year": 9, "min_valid_years": 3, "min_coverage_ratio": 0.70,
    "alpha": 0.05, "confidence_level": 0.95,
    "limitations": [
        "Datos de grilla NASA POWER; no son mediciones de estaciones locales.",
        "OLS supone linealidad, independencia y homocedasticidad; no verifica esos supuestos.",
        "No se corrige autocorrelación ni comparaciones múltiples. No usar para descubrimientos automáticos.",
        "Correlación temporal y significancia no demuestran causalidad.",
        "PRECTOTCORR sigue en mm/day; no es precipitación acumulada anual.",
        "El motor excluye sus centinelas -99, -999, -9999 y valores <= -900 al agregar.",
    ],
}


class AnalysisService:
    def __init__(self, data_service):
        self.data_service = data_service

    def selection(self, payload, *, summary=False):
        if not isinstance(payload, dict):
            raise ServiceError("invalid_request", "El cuerpo JSON debe ser un objeto.")
        if {"latitude", "longitude", "lat", "lon", "coordinates"} & set(payload):
            raise ServiceError("coordinates_not_supported", "Seleccionar una ciudad argentina del catálogo; las coordenadas libres siguen deshabilitadas.")
        allowed = {"city_id", "start_year", "end_year"}
        if not summary:
            allowed.add("variable")
        if set(payload) - allowed:
            raise ServiceError("invalid_request", "La solicitud contiene campos no admitidos.")
        translated = {key: value for key, value in payload.items() if key != "variable"}
        if not summary:
            translated["variables"] = [payload.get("variable", "T2M")]
        selected = validate_data_request(translated)
        if selected["end_year"] - selected["start_year"] < 2:
            raise ServiceError("invalid_request", "El análisis requiere un período de al menos tres años.")
        return selected

    def _analyze(self, row, data, meta):
        if not engine.HAS_SCIPY:
            raise ServiceError("analysis_unavailable", "El motor requiere SciPy; reconstruir la imagen con sus dependencias.")
        code = row["variable"]
        expected_units = {
            "T2M": {"C", "deg C", "°C"}, "T2M_MAX": {"C", "deg C", "°C"},
            "T2M_MIN": {"C", "deg C", "°C"}, "PRECTOTCORR": {"mm/day"},
            "RH2M": {"%"}, "WS2M": {"m/s"},
        }
        if row["unit"] not in expected_units[code]:
            raise ServiceError("incompatible_analysis", "La unidad recibida no es compatible con el contrato del motor; no se realizó una conversión.")
        raw = {point["date"].replace("-", ""): point["value"] for point in row["series"]}
        annual = engine.aggregate_to_annual_series(raw, data["start_year"], data["end_year"])
        coverage = engine.evaluate_completeness(annual, data["start_year"], data["end_year"])
        if not coverage["is_complete"]:
            raise ServiceError("insufficient_data", "La cobertura anual no satisface los criterios del motor.", details={"completeness": coverage})
        result = engine.analyze_series(
            raw, variable=code, source="NASA POWER", unit=row["unit"],
            start_year=data["start_year"], end_year=data["end_year"],
            location_name=data["city"]["name"],
        )
        result["statistics"]["t_critical_95"] = float(engine.scipy_stats.t.ppf(0.975, len(result["series"]) - 2))
        return {
            **result, "is_mock": False, "location": data["city"],
            "period": {"start_year": data["start_year"], "end_year": data["end_year"]},
            "provider": data["provider"], "dataset": data["dataset"],
            "frequency": "annual", "input_frequency": "monthly",
            "metadata": row["metadata"], "method": METHOD,
            "provenance": {"origin": meta["origin"], "fetched_at": meta["fetched_at"],
                           "monthly_quality": meta["quality"][code]},
        }

    def analyze(self, payload):
        selection = self.selection(payload)
        data, meta = self.data_service.get_data(selection)
        return self._analyze(data["variables"][selection["variables"][0]], data, meta), meta

    def summary(self, payload):
        selection = self.selection(payload, summary=True)
        data, meta = self.data_service.get_data(selection)
        estimations = {}
        for code, row in data["variables"].items():
            try:
                result = self._analyze(row, data, meta)
            except ServiceError as error:
                if error.code != "insufficient_data":
                    raise
                estimations[code] = {"variable": code, "unit": row["unit"],
                                     "status": "insufficient_data", "completeness": error.details["completeness"]}
                continue
            estimations[code] = {**result, "mean_value": result["statistics"]["mean"],
                                 "latest_value": result["series"][-1]["value"]}
        return {"is_mock": False, "location": data["city"], "estimations": estimations,
                "start_year": data["start_year"], "end_year": data["end_year"], "method": METHOD}, meta

    def results(self, payload, *, cache_only=False):
        """Seis resultados comunes de una única obtención; errores científicos aislados por variable."""
        selection = self.selection(payload, summary=True)
        city = self.data_service.get_city(selection["city_id"])
        period = {key: selection[key] for key in ("start_year", "end_year")}
        method = methodology()
        analyzed_at = utc_now()
        try:
            data, meta = self.data_service.get_data(selection, cache_only=cache_only)
        except ServiceError as error:
            return [make_result(city, code, period, method=method, error=error, analyzed_at=analyzed_at)
                    for code in selection["variables"]]
        records = []
        for code, row in data["variables"].items():
            analysis, error = None, None
            try:
                analysis = self._analyze(row, data, meta)
                content_hash(analysis)  # Rechaza números no finitos sin publicar JSON inválido.
            except ServiceError as exc:
                error = exc
            except Exception:
                # El contrato de producto nunca expone excepciones internas del motor.
                error = ServiceError("internal_error", "No se pudo analizar esta variable.")
                analysis = None
            records.append(make_result(city, code, period, method=method, row=row, meta=meta,
                                       analysis=analysis, error=error, analyzed_at=analyzed_at))
        return records

    def compare(self, payload):
        if not isinstance(payload, dict) or set(payload) - {"city_id_a", "city_id_b", "variable", "start_year", "end_year"}:
            raise ServiceError("invalid_request", "Usar city_id_a, city_id_b, variable y período.")
        shared = {key: value for key, value in payload.items() if key not in {"city_id_a", "city_id_b"}}
        requests = [{**shared, "city_id": payload.get(key)} for key in ("city_id_a", "city_id_b")]
        # Validar ambas ubicaciones y períodos antes de acceder a datos o red.
        for item in requests:
            self.selection(item)
            self.data_service.get_city(item["city_id"])
        a, meta_a = self.analyze(requests[0])
        b, meta_b = self.analyze(requests[1])
        if a["unit"] != b["unit"] or [p["year"] for p in a["series"]] != [p["year"] for p in b["series"]]:
            raise ServiceError("incompatible_analysis", "La comparación requiere unidades y años válidos idénticos.")
        result = engine.compare_two_locations(a, b, a["location"]["name"], b["location"]["name"])
        return {**result, "is_mock": False, "method": METHOD}, {"location_a": meta_a, "location_b": meta_b}
