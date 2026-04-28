"""Servicio de persistencia en JSON.

Gestiona el estado activo (delivery_state.json) y el historial
de viajes cerrados (history/{fecha}.json).
"""

from __future__ import annotations

import copy
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATE_FILE = DATA_DIR / "delivery_state.json"
HISTORY_DIR = DATA_DIR / "history"

DEFAULT_STATE: dict[str, Any] = {
    "origin": {
        "name": "Bodega Principal",
        "latitude": 0.0,
        "longitude": 0.0,
    },
    "delivery_points": [],
    "optimized_route": {
        "optimized_order": [],
        "total_distance_km": 0.0,
        "total_duration_min": 0.0,
        "method": "",
        "return_info": {
            "mode": "none",
            "point_name": "",
            "latitude": 0.0,
            "longitude": 0.0,
        },
    },
    "return_config": {
        "mode": "origin",
        "custom_point": {
            "name": "",
            "latitude": 0.0,
            "longitude": 0.0,
        },
    },
    "fuel_config": {
        "km_per_liter": 0.0,
        "price_per_liter": 0.0,
    },
    "summary": {
        "completed": 0,
        "pending": 0,
        "total_km": 0.0,
        "total_duration_min": 0.0,
        "fuel_liters": 0.0,
        "fuel_cost": 0.0,
        "optimized_order": [],
    },
}


def _ensure_dirs() -> None:
    """Crea los directorios data/ y data/history/ si no existen."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict[str, Any]:
    """Carga el estado desde JSON. Si no existe o está corrupto, retorna default."""
    _ensure_dirs()
    if not STATE_FILE.exists():
        default = copy.deepcopy(DEFAULT_STATE)
        save_state(default)
        return default

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        # Deep-merge: start from a fresh default copy, overlay loaded data
        merged = copy.deepcopy(DEFAULT_STATE)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, ValueError):
        # Backup del archivo corrupto
        backup = STATE_FILE.with_suffix(".json.bak")
        shutil.copy2(STATE_FILE, backup)
        default = copy.deepcopy(DEFAULT_STATE)
        save_state(default)
        return default


def save_state(state: dict[str, Any]) -> None:
    """Guarda el estado completo en JSON."""
    _ensure_dirs()
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def archive_day(state: dict[str, Any]) -> str:
    """Guarda snapshot del estado actual en history/{fecha}.json.

    Retorna la fecha usada como nombre del archivo.
    """
    _ensure_dirs()
    today = date.today().isoformat()
    history_file = HISTORY_DIR / f"{today}.json"
    history_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Limpiar estado activo: mantener origin y fuel_config
    clean_state = copy.deepcopy(DEFAULT_STATE)
    clean_state["origin"] = copy.deepcopy(
        state.get("origin", DEFAULT_STATE["origin"])
    )
    clean_state["fuel_config"] = copy.deepcopy(
        state.get("fuel_config", DEFAULT_STATE["fuel_config"])
    )
    save_state(clean_state)

    return today


def load_trip(trip_date: str) -> dict[str, Any] | None:
    """Carga un viaje archivado por fecha (YYYY-MM-DD)."""
    _ensure_dirs()
    history_file = HISTORY_DIR / f"{trip_date}.json"
    if not history_file.exists():
        return None
    try:
        return json.loads(history_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return None


def list_trips() -> list[dict[str, Any]]:
    """Lista todos los viajes archivados con métricas resumidas.

    Retorna lista ordenada por fecha descendente.
    """
    _ensure_dirs()
    trips: list[dict[str, Any]] = []
    for f in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            summary = data.get("summary", {})
            trips.append(
                {
                    "date": f.stem,
                    "completed": summary.get("completed", 0),
                    "pending": summary.get("pending", 0),
                    "total_km": summary.get("total_km", 0.0),
                    "fuel_cost": summary.get("fuel_cost", 0.0),
                }
            )
        except (json.JSONDecodeError, ValueError):
            continue
    return trips
