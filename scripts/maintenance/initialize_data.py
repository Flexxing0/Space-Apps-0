"""Inicialización reproducible: POWER real, auditoría de cobertura y Radar cache-only."""

import argparse
from pathlib import Path
from uuid import uuid4

from app import create_app
from services.providers.cache import DEFAULT_CACHE_DIR, utc_now, write_json_atomic


def initialize(*, cache_dir=DEFAULT_CACHE_DIR, start_year=2000, end_year=2024, force=False):
    app = create_app({"CACHE_DIR": Path(cache_dir)})
    bulk = app.extensions["earthlens_service"].bulk
    report = bulk.collect_cities(start_year=start_year, end_year=end_year, force=force)
    successful = [row for row in report["results"] if row["status"] == "ok"]
    quality = [q for row in successful for q in row["quality"].values()]
    report["audit"] = {
        "series": len(quality), "monthly_records": sum(q["expected_count"] for q in quality),
        "available_records": sum(q["valid_count"] for q in quality),
        "missing_records": sum(q["missing_count"] for q in quality),
        "units": {code: sorted({row["data"][code]["unit"] for row in successful})
                  for code in (successful[0]["data"] if successful else [])},
    }
    report["radar"] = {"regenerated": False}
    if report["summary"]["failed"] == 0:
        radar = app.extensions["earthlens_radar"]
        study = radar.generate(start_year=start_year, end_year=end_year)
        if study["summary"]["computed"] == study["summary"]["tests"]:
            document = radar.persist(study)
            report["radar"] = {"regenerated": True, "path": str(radar.artifact_path),
                               "study_id": document["study_id"], "summary": document["summary"]}
        else:
            report["radar"] = {"regenerated": False, "reason": "incomplete_analysis",
                               "summary": study["summary"]}
    for row in report["results"]:
        row.pop("data", None)
    report["initialization_finished_at"] = utc_now()
    output = Path(cache_dir).parent / "reports" / f"initialization-{start_year}-{end_year}-{uuid4().hex[:10]}.json"
    write_json_atomic(output, report)
    return report, output


def main(argv=None):
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    report, output = initialize(**vars(args))
    print(json.dumps({"summary": report["summary"], "audit": report["audit"],
                      "radar": report["radar"], "report": str(output)}, ensure_ascii=True))
    return int(report["summary"]["failed"] > 0 or not report["radar"]["regenerated"])


if __name__ == "__main__":
    raise SystemExit(main())
