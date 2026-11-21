"""Genera un estudio Radar completo, provisional y sin red, desde cachés existentes."""

import argparse
import json
from pathlib import Path

from app import create_app
from services.api_service import ServiceError
from services.providers.bulk import DEFAULT_START_YEAR, DEFAULT_END_YEAR
from services.providers.cache import DEFAULT_CACHE_DIR


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, help="JSON derivado, fuera de data/cache/power")
    parser.add_argument("--dry-run", action="store_true", help="Sólo muestra el conjunto de pruebas; no lee series ni escribe resultados")
    args = parser.parse_args(argv)
    config = {"CACHE_DIR": args.cache_dir}
    if args.output is not None:
        config["RADAR_ARTIFACT_PATH"] = args.output
    app = create_app(config)
    radar = app.extensions["earthlens_radar"]
    try:
        if args.dry_run:
            plan = radar.plan(start_year=args.start_year, end_year=args.end_year)
            print(json.dumps({"dry_run": True, "cities": len(plan["cities"]), "period": plan["period"],
                              "tests": plan["tests"]}, ensure_ascii=True))
            return 0
        study = radar.generate(start_year=args.start_year, end_year=args.end_year)
        document = radar.persist(study)
    except (ServiceError, ValueError, OSError) as error:
        parser.error(error.message if isinstance(error, ServiceError) else str(error))
    print(json.dumps({"study_id": document["study_id"], "run_id": document["run_id"],
                      "output": str(radar.artifact_path), "summary": document["summary"]}, ensure_ascii=True))
    return int(document["summary"]["statuses"]["error"] > 0 or document["summary"]["statuses"]["insufficient"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
