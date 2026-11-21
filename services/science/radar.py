"""Estudios completos y provisionales; GET sólo lee y filtra un artefacto persistido."""

from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

from services.science.analysis_results import (EVIDENCE_STATUSES, INDICATORS, METHOD_VERSION,
                                       content_hash, result_counts)
from services.api_service import ServiceError
from services.providers.bulk import DEFAULT_START_YEAR, DEFAULT_END_YEAR
from services.providers.cache import parse_timestamp, utc_now, write_json_atomic
from services.geography.cities import filter_cities
from services.science.fingerprint import FingerprintService
from services.providers.power import VARIABLES


RADAR_SCHEMA = "earthlens.radar.v1"
DEFAULT_ARTIFACT_NAME = "radar/latest.json"


class RadarService:
    def __init__(self, analysis, artifact_path):
        self.analysis = analysis
        self.fingerprints = FingerprintService(analysis)
        self.artifact_path = Path(artifact_path)

    def plan(self, *, start_year=DEFAULT_START_YEAR, end_year=DEFAULT_END_YEAR):
        cities = self.analysis.data_service.list_cities()
        self.analysis.selection({"city_id": cities[0]["id"], "start_year": start_year, "end_year": end_year}, summary=True)
        return {"period": {"start_year": start_year, "end_year": end_year}, "cities": cities,
                "variables": list(VARIABLES),
                "tests": [{"test_id": f"{city['id']}:{code}", "city_id": city["id"], "variable": code,
                           "indicator": deepcopy(INDICATORS[code])} for city in cities for code in VARIABLES]}

    def generate(self, *, start_year=DEFAULT_START_YEAR, end_year=DEFAULT_END_YEAR):
        """Nunca consulta NASA. La preparación de cachés es una operación explícita separada."""
        plan = self.plan(start_year=start_year, end_year=end_year)
        started_at = utc_now()
        records = []
        for city in plan["cities"]:
            profile = self.fingerprints.profile(city["id"], **plan["period"], cache_only=True)
            records.extend(profile["results"])
        method = records[0]["methodology"]
        family_definition = {"scope": "catalogue_cities_x_six_variables", "period": plan["period"],
                             "cities": plan["cities"], "variables": plan["variables"],
                             "tests": plan["tests"], "methodology": method}
        family_id = content_hash(family_definition)
        exclusions = [{"test_id": row["result_id"], "reason": row["evidence"]["status"],
                       "error": row["error"]} for row in records
                      if row["data_status"] != "valid" or row["evidence"]["issues"]]
        excluded_ids = {item["test_id"] for item in exclusions}
        counts = result_counts(records)
        inputs = {row["result_id"]: row["provenance"]["input_sha256"] for row in records}
        return {
            "schema_version": RADAR_SCHEMA, "status": "provisional", "study_id": content_hash({"family_id": family_id, "inputs": inputs}),
            "run_id": uuid4().hex, "started_at": started_at, "generated_at": utc_now(),
            "period": plan["period"], "methodology": method, "cities": plan["cities"],
            "family": {"id": family_id, "definition": "Producto cartesiano del catálogo completo y las seis variables, definido antes del análisis.",
                       "city_ids": [city["id"] for city in plan["cities"]], "variables": plan["variables"],
                       "planned_tests": len(plan["tests"]), "tests": plan["tests"],
                       "eligible_test_ids": [row["result_id"] for row in records if row["result_id"] not in excluded_ids],
                       "exclusions": exclusions},
            "multiple_testing": {"status": "not_applied", "method": None, "family_id": family_id,
                                 "scope": "entire_study_family", "ready_for_adjustment": False,
                                 "blockers": ["methodology_approval", "unrounded_statistics", "temporal_inference"],
                                 "adjusted_p_values": None, "filters_change_family": False},
            "summary": {"cities": len(plan["cities"]), "tests": len(records), "statuses": counts,
                        "computed": sum(row["data_status"] == "valid" for row in records),
                        "provisional_signals": sum(row["evidence"]["status"] == "provisional_signal" for row in records),
                        "exclusions": len(exclusions), "confirmed_discoveries": 0,
                        "cache_only": True, "cache_hit_cities": len({row["location"]["id"] for row in records if row["provenance"]["origin"] == "cache"})},
            "results": records,
        }

    def _validate(self, study):
        if (not isinstance(study, dict) or study.get("schema_version") != RADAR_SCHEMA
                or study["methodology"]["version"] != METHOD_VERSION or study["status"] != "provisional"
                or study["multiple_testing"]["status"] != "not_applied"
                or study["multiple_testing"]["family_id"] != study["family"]["id"]):
            raise ValueError("Artefacto Radar incompatible")
        for key in ("generated_at", "started_at"):
            parse_timestamp(study[key])
        expected = [test["test_id"] for test in study["family"]["tests"]]
        actual = [row["result_id"] for row in study["results"]]
        cartesian = [f"{city_id}:{code}" for city_id in study["family"]["city_ids"] for code in study["family"]["variables"]]
        if (len(expected) != len(set(expected)) or expected != actual
                or expected != cartesian or study["family"]["variables"] != list(VARIABLES)
                or len(actual) != study["family"]["planned_tests"]
                or any(row["evidence"]["confirmed"] for row in study["results"])
                or study["summary"]["confirmed_discoveries"] != 0):
            raise ValueError("Familia Radar inconsistente")
        if (study["summary"]["tests"] != len(actual)
                or study["summary"]["statuses"] != result_counts(study["results"])
                or any(row["period"] != study["period"] or row["methodology"] != study["methodology"]
                       or row["result_id"] != f"{row['location']['id']}:{row['variable']}"
                       or row["status"] not in {"provisional", "insufficient", "error"}
                       or row["evidence"]["adjustment_status"] != "not_applied"
                       or row["evidence"]["adjusted_p_value"] is not None for row in study["results"])):
            raise ValueError("Resultados Radar inconsistentes")

    def persist(self, study):
        # Un destino mal configurado nunca debe sustituir una caché de observaciones.
        power_dir = Path(self.analysis.data_service.bulk.cache.directory).resolve()
        if self.artifact_path.resolve().is_relative_to(power_dir):
            raise ValueError("El artefacto Radar debe estar fuera de la caché POWER")
        self._validate(study)
        document = deepcopy(study)
        document.pop("integrity", None)
        document["integrity"] = {"algorithm": "sha256", "payload_sha256": content_hash(document)}
        write_json_atomic(self.artifact_path, document)
        return document

    def read(self):
        try:
            with self.artifact_path.open(encoding="utf-8") as stream:
                document = json.load(stream)
            if not isinstance(document, dict):
                raise ValueError("Artefacto Radar inválido")
            integrity = document.pop("integrity")
            if integrity != {"algorithm": "sha256", "payload_sha256": content_hash(document)}:
                raise ValueError("Integridad Radar inválida")
            self._validate(document)
            document["integrity"] = integrity
            return document
        except FileNotFoundError:
            raise ServiceError("radar_unavailable", "El estudio Radar todavía no fue generado.") from None
        except (OSError, ValueError, KeyError, TypeError):
            raise ServiceError("radar_invalid_artifact", "El estudio Radar no es válido; regenerarlo antes de consultarlo.") from None

    def query(self, *, province=None, region=None, variable=None, direction=None, evidence_status=None):
        if variable is not None and variable not in VARIABLES:
            raise ServiceError("invalid_request", "Variable no admitida.", details={"allowed": list(VARIABLES)})
        if direction is not None and direction not in {"increasing", "decreasing", "stable"}:
            raise ServiceError("invalid_request", "Dirección no admitida.")
        if evidence_status is not None and evidence_status not in EVIDENCE_STATUSES:
            raise ServiceError("invalid_request", "Estado de evidencia no admitido.", details={"allowed": list(EVIDENCE_STATUSES)})
        study = self.read()
        city_ids = {city["id"] for city in filter_cities(study["cities"], province=province, region=region)}
        records = [row for row in study["results"] if row["location"]["id"] in city_ids
                   and (variable is None or row["variable"] == variable)
                   and (direction is None or row["direction"] == direction)
                   and (evidence_status is None or row["evidence"]["status"] == evidence_status)]
        study["results"] = records
        study["view"] = {"count": len(records), "filters": {key: value for key, value in {
            "province": province, "region": region, "variable": variable,
            "direction": direction, "evidence_status": evidence_status}.items() if value is not None},
            "family_unchanged": True}
        # El hash describe el artefacto completo, no esta proyección filtrada.
        study["artifact_integrity"] = study.pop("integrity")
        return study
