"""Audita las 25 ciudades con datos reales existentes y la red NASA bloqueada.

No obtiene datos ni actualiza la caché. El informe queda en data/cache/reports.
"""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from app import create_app


def manifest(directory):
    return {path.name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "fetched_at": json.loads(path.read_text(encoding="utf-8"))["fetched_at"]}
            for path in directory.glob("*.json")}


def main():
    app = create_app({"TESTING": True})
    before = manifest(Path(app.config["CACHE_DIR"]))
    report = {"cities": [], "monthly_series": 0, "monthly_values": 0, "annual_analyses": 0}
    with app.test_client() as client, patch("requests.sessions.Session.request", side_effect=AssertionError("NASA bloqueada durante auditoría")) as network:
        cities = client.get("/api/cities").get_json()["data"]
        for city in cities:
            response = client.post("/api/data", json={"city_id": city["id"]})
            assert response.status_code == 200, (city["id"], response.get_json())
            monthly = response.get_json()
            assert monthly["meta"]["origin"] == "cache"
            assert len(monthly["data"]["variables"]) == 6
            for row in monthly["data"]["variables"].values():
                assert len(row["series"]) == 300
                report["monthly_series"] += 1
                report["monthly_values"] += sum(point["value"] is not None for point in row["series"])
            response = client.get("/api/summary", query_string={"city_id": city["id"]})
            assert response.status_code == 200, (city["id"], response.get_json())
            summary = response.get_json()
            assert summary["meta"]["origin"] == "cache"
            assert summary["meta"]["fetched_at"] == monthly["meta"]["fetched_at"]
            for result in summary["data"]["estimations"].values():
                assert result["is_mock"] is False
                assert len(result["series"]) == 25
                assert result["metadata"] == monthly["data"]["variables"][result["variable"]]["metadata"]
                report["annual_analyses"] += 1
            report["cities"].append({"city_id": city["id"], "origin": "cache", "fetched_at": monthly["meta"]["fetched_at"]})
        network.assert_not_called()
    after = manifest(Path(app.config["CACHE_DIR"]))
    assert before == after, "Cambió la caché durante la auditoría"
    report.update(status="ok", nasa_requests=0, cache_unchanged=True, cache_manifest=after)
    target = Path(app.config["CACHE_DIR"]).parent / "reports" / "integrated-cache-audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"cities", "cache_manifest"}}))


if __name__ == "__main__":
    main()
