"""Perfiles ambientales por ciudad; sin puntajes ni normalizaciones ambientales."""

from services.science.analysis_results import (PRIMARY_VARIABLES, EXTREME_VARIABLES, content_hash,
                                       result_counts)
from services.providers.bulk import DEFAULT_START_YEAR, DEFAULT_END_YEAR


def comparison_basis(profile):
    return {"period": profile["period"], "methodology": profile["methodology"],
            "indicators": [{"variable": row["variable"], "indicator": row["indicator"]["id"],
                            "unit": row["unit"], "years": [point["year"] for point in row["series"]],
                            "monthly_coverage": row["coverage"]["by_year"],
                            "source": {"provider": row["source"]["provider"], "dataset": row["source"]["dataset"],
                                       "header": {key: (row["source"]["metadata"] or {}).get("header", {}).get(key)
                                                  for key in ("sources", "api", "time_standard")}}}
                           for row in profile["results"]]}


def compare_compatibility(profile_a, profile_b):
    """Compatibilidad descriptiva estricta; no calcula diferencias ni significancia."""
    reasons = []
    if any(row["data_status"] != "valid" for profile in (profile_a, profile_b) for row in profile["results"]):
        reasons.append("incomplete_profile")
    if any(row["evidence"]["issues"] for profile in (profile_a, profile_b) for row in profile["results"]):
        reasons.append("inconsistent_statistics")
    if comparison_basis(profile_a) != comparison_basis(profile_b):
        reasons.append("period_method_indicators_units_or_years_differ")
    return {"compatible": not reasons, "reasons": reasons,
            "scope": "descriptive_only", "methodology_validated": False}


class FingerprintService:
    def __init__(self, analysis):
        self.analysis = analysis

    def profile(self, city_id, *, start_year=DEFAULT_START_YEAR, end_year=DEFAULT_END_YEAR,
                cache_only=False):
        records = self.analysis.results({"city_id": city_id, "start_year": start_year,
                                         "end_year": end_year}, cache_only=cache_only)
        counts = result_counts(records)
        status = "provisional" if counts["provisional"] else ("insufficient" if counts["insufficient"] else "error")
        profile = {
            "schema_version": "earthlens.fingerprint.v1", "status": status,
            "city": records[0]["location"], "period": records[0]["period"],
            "generated_at": records[0]["analyzed_at"], "methodology": records[0]["methodology"],
            "groups": {"primary": list(PRIMARY_VARIABLES), "extreme": list(EXTREME_VARIABLES)},
            "summary": {"variables": len(records), "statuses": counts,
                        "data_complete": all(row["data_status"] == "valid" for row in records),
                        "confirmed_discoveries": 0},
            "results": records,
        }
        profile["comparison"] = {"key": content_hash(comparison_basis(profile)),
                                 "all_indicators_available": profile["summary"]["data_complete"],
                                 "scope": "descriptive_only", "methodology_validated": False}
        return profile
