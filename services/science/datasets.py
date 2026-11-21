"""
EarthLens — Catálogo de variables y misiones científicas (datasets.py)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
VARIABLES_PATH = BASE_DIR / "data" / "variables.json"
MISSIONS_PATH = BASE_DIR / "data" / "missions.json"


def get_variables_catalog() -> List[Dict[str, Any]]:
    if VARIABLES_PATH.exists():
        with open(VARIABLES_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("variables", [])
    return []


def get_missions_list() -> List[Dict[str, Any]]:
    if MISSIONS_PATH.exists():
        with open(MISSIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("missions", [])
    return []


def get_mission_by_id(mission_id: str) -> Optional[Dict[str, Any]]:
    target = str(mission_id).strip().lower()
    for mission in get_missions_list():
        if str(mission.get("id", "")).lower() == target or str(mission.get("code", "")).lower() == target:
            return mission
    return None
