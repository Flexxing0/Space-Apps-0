"""Verifica y obtiene series nativas reales, sin modificar la familia Radar."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from app import create_app
from services.providers.cache import DEFAULT_CACHE_DIR, utc_now, write_json_atomic
from services.providers.gldas import GldasProvider
from services.api_service import ServiceError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=("power", "modis", "gldas", "gpm"))
    parser.add_argument("--access", choices=("giovanni",), help="Acceso puntual alternativo GLDAS/GPM; conserva su procedencia y precisión CSV")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--city")
    selection.add_argument("--cities", nargs="+")
    selection.add_argument("--region")
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--variables", nargs="+")
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--probe", action="store_true", help="Sólo descubre GLDAS y prueba autenticación; no obtiene observaciones")
    args = parser.parse_args(argv)
    app = create_app({"CACHE_DIR": args.cache_dir})
    service = app.extensions["earthlens_science"]
    if args.probe:
        if args.provider != "gldas":
            parser.error("--probe sólo aplica a GLDAS")
        try:
            result = GldasProvider(service.store).probe()
        except ServiceError as error:
            print(json.dumps({"status": "error", "code": error.code, "message": error.message, "details": error.details}, ensure_ascii=True))
            return 1
        print(json.dumps(result, ensure_ascii=True))
        return int(not result["authenticated_metadata_access"])
    if not args.variables or not any((args.city, args.cities, args.region, args.all)):
        parser.error("Seleccionar ciudades y variables explícitamente")
    plans = service.data_service.bulk.plan_cities(city_id=args.city, city_ids=args.cities, region=args.region,
                                                 start_year=args.start_year, end_year=args.end_year)
    report = {"provider": args.provider, "started_at": utc_now(), "period": {"start_year": args.start_year, "end_year": args.end_year}, "results": []}
    for plan in plans:
        identifier = plan["location"]["id"]
        try:
            if plan["error"]:
                raise ValueError("Ciudad no disponible en el catálogo argentino")
            records = service.fetch(provider=args.provider, city_id=identifier, variables=args.variables,
                                    start_year=args.start_year, end_year=args.end_year, force=args.force,access=args.access)
            result = {"city_id": identifier, "status": "ok", "series": len(records),
                      "records": sum(row["coverage"]["expected_count"] for row in records),
                      "valid": sum(row["coverage"]["valid_count"] for row in records),
                      "missing": sum(row["coverage"]["missing_count"] for row in records),
                      "variables": [{key: row[key] for key in ("variable", "product", "product_version", "cache_version", "unit", "frequency", "coverage", "fetched_at")} for row in records]}
        except Exception as error:
            result = {"city_id": identifier, "status": "error", "error_type": type(error).__name__,
                      "error_code": getattr(error, "code", "source_request_failed")}
        report["results"].append(result)
        print(json.dumps({key: value for key, value in result.items() if key != "variables"}, ensure_ascii=True), flush=True)
    report["finished_at"] = utc_now()
    report["summary"] = {"requested": len(plans), "succeeded": sum(row["status"] == "ok" for row in report["results"]),
                          "failed": sum(row["status"] == "error" for row in report["results"]),
                          **{key: sum(row.get(key, 0) for row in report["results"]) for key in ("series", "records", "valid", "missing")}}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = service.store.root.parent / "reports" / f"scientific-{args.provider}-{stamp}-{uuid4().hex[:8]}.json"
    write_json_atomic(output, report)
    print(json.dumps({"summary": report["summary"], "report": str(output)}, ensure_ascii=True), flush=True)
    return int(report["summary"]["failed"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
