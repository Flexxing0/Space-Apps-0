"""Obtiene las seis variables POWER para una selección argentina explícita."""

import argparse
import json
from pathlib import Path

from services.providers.bulk import DEFAULT_END_YEAR, DEFAULT_START_YEAR, PowerBulkService
from services.providers.cache import DEFAULT_CACHE_DIR, JsonCache


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--city", help="ID de una ciudad")
    selection.add_argument("--cities", nargs="+", help="IDs de un subconjunto")
    selection.add_argument("--region", help="Patagonia, centro-pampeana, Cuyo, NOA o NEA")
    selection.add_argument("--province", help="Nombre o ID GeoRef de provincia; también CABA")
    selection.add_argument("--all", action="store_true", help="Todo el catálogo argentino")
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--max-age-days", type=float, default=None, help="Vigencia opcional; por defecto reutiliza hasta --force")
    parser.add_argument("--delay", type=float, default=1.0, help="Intervalo mínimo entre inicios de consultas remotas, en segundos")
    parser.add_argument("--force", action="store_true", help="Actualizar aunque exista caché válida")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar selección y consultas sin acceder a NASA ni escribir cachés")
    return parser


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    selection = {"city_id": args.city, "city_ids": args.cities, "region": args.region,
                 "province": args.province, "start_year": args.start_year, "end_year": args.end_year}
    try:
        service = PowerBulkService(JsonCache(args.cache_dir), request_delay=args.delay,
                                   max_age_days=args.max_age_days)
        if args.dry_run:
            plans = service.plan_cities(**selection)
            print(json.dumps({"dry_run": True, "count": len(plans), "plans": plans}, ensure_ascii=True, indent=2))
            return int(any(plan["error"] for plan in plans))
        report = service.collect_cities(**selection, force=args.force)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    # Las series completas permanecen en la caché; consola con estado y cobertura.
    report["results"] = [{key: value for key, value in result.items() if key != "data"}
                         for result in report["results"]]
    print(json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False))
    return int(report["summary"]["failed"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
