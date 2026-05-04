"""Repositorio JSON para persistencia de jornadas.

Implementa una interfaz abstracta para facilitar futura migración
a SQLite u otra base de datos. La implementación concreta usa
archivos JSON con escrituras atómicas.
"""

from __future__ import annotations

import json
import shutil
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from delivery_app.domain.enums import ReturnMode, TripStatus
from delivery_app.domain.models import (
    Coordinates,
    Delivery,
    FuelConfig,
    Metrics,
    NamedPoint,
    Trip,
)
from delivery_app.infrastructure.atomic_file_io import atomic_write


class TripRepositoryBase(ABC):
    """Interfaz abstracta para repositorios de jornadas.

    Cualquier implementación futura (SQLite, PostgreSQL) debe
    implementar estos métodos.
    """

    @abstractmethod
    def load_active_trip(self) -> Trip | None:
        """Carga la jornada activa. Retorna None si no hay ninguna."""
        ...

    @abstractmethod
    def save_trip(self, trip: Trip) -> None:
        """Guarda (crea o actualiza) una jornada."""
        ...

    @abstractmethod
    def archive_trip(self, trip: Trip) -> str:
        """Archiva una jornada cerrada en el historial.

        Returns:
            Identificador del archivo archivado (trip_id o fecha).
        """
        ...

    @abstractmethod
    def load_archived_trip(self, trip_id: str) -> Trip | None:
        """Carga una jornada archivada por ID."""
        ...

    @abstractmethod
    def list_archived_trips(self) -> list[dict[str, Any]]:
        """Lista resúmenes de jornadas archivadas, orden descendente."""
        ...

    @abstractmethod
    def clear_active(self) -> None:
        """Elimina el estado activo (para después de archivar)."""
        ...


class JsonTripRepository(TripRepositoryBase):
    """Implementación de repositorio usando archivos JSON.

    Archivos:
        - data/delivery_state.json: jornada activa
        - data/history/{trip_id}.json: jornadas archivadas
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._state_file = data_dir / "delivery_state.json"
        self._history_dir = data_dir / "history"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._history_dir.mkdir(parents=True, exist_ok=True)

    def load_active_trip(self) -> Trip | None:
        """Carga la jornada activa.

        Si el archivo tiene formato viejo (sin trip_id), lo migra
        automáticamente al formato nuevo con backup.
        """
        if not self._state_file.exists():
            return None

        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            self._backup_corrupt()
            return None

        # Detectar formato: nuevo tiene "trip_id", viejo no
        if "trip_id" in raw:
            try:
                return Trip.model_validate(raw)
            except Exception:
                self._backup_corrupt()
                return None
        else:
            return self._migrate_legacy(raw)

    def save_trip(self, trip: Trip) -> None:
        """Guarda la jornada activa con escritura atómica."""
        self._ensure_dirs()
        content = trip.model_dump_json(indent=2)
        atomic_write(self._state_file, content)

    def archive_trip(self, trip: Trip) -> str:
        """Archiva la jornada en historial usando trip_id como nombre.

        Es idempotente: si el archivo ya existe (mismo trip_id),
        lo sobreescribe con el mismo contenido.
        """
        self._ensure_dirs()
        archive_file = self._history_dir / f"{trip.trip_id}.json"
        content = trip.model_dump_json(indent=2)
        atomic_write(archive_file, content)
        return trip.trip_id

    def clear_active(self) -> None:
        """Elimina el estado activo (para después de archivar)."""
        if self._state_file.exists():
            self._state_file.unlink()

    def load_archived_trip(self, trip_id: str) -> Trip | None:
        """Carga una jornada archivada por trip_id.

        También soporta cargar por fecha (formato viejo YYYY-MM-DD)
        o coincidencias parciales en el nombre del archivo.
        """
        # Intentar por trip_id exacto primero
        archive_file = self._history_dir / f"{trip_id}.json"
        if archive_file.exists():
            trip = self._load_trip_file(archive_file)
            if trip:
                return trip
            # Si existe pero no es formato nuevo, intentar como legacy
            return self._load_legacy_trip_file(archive_file)

        # Fallback: buscar en el directorio por coincidencia de nombre
        # Útil si trip_id es una fecha o el archivo tiene prefijos/sufijos
        for f in self._history_dir.glob("*.json"):
            if trip_id in f.name:
                # Intentar cargar como nuevo formato primero
                trip = self._load_trip_file(f)
                if trip:
                    return trip
                # Si falla, intentar como legacy
                return self._load_legacy_trip_file(f)

        return None

    def list_archived_trips(self) -> list[dict[str, Any]]:
        """Lista resúmenes de jornadas archivadas.

        Soporta tanto archivos nuevos (por trip_id) como viejos (por fecha).
        """
        self._ensure_dirs()
        trips: list[dict[str, Any]] = []

        for f in sorted(self._history_dir.glob("*.json"), reverse=True):
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))

                # Formato nuevo
                if "trip_id" in raw:
                    trip = Trip.model_validate(raw)
                    from delivery_app.domain.trip_manager import get_summary

                    summary = get_summary(trip)
                    summary["trip_date"] = trip.created_at.strftime("%Y-%m-%d %H:%M")
                    trips.append(summary)
                else:
                    # Formato viejo — extraer lo básico
                    s = raw.get("summary", {})
                    trips.append({
                        "trip_id": f.stem,
                        "display_title": s.get("display_title", s.get("title", f"Viaje {f.stem}")),
                        "trip_date": f.stem,
                        "status": "closed",
                        "completed": s.get("completed") or 0,
                        "pending": s.get("pending") or 0,
                        "planned_km": s.get("total_km") or 0.0,
                        "estimated_fuel_cost": f"{s.get('fuel_cost') or 0.0:.2f}",
                    })
            except (json.JSONDecodeError, ValueError, Exception):
                continue

        return trips

    def _load_trip_file(self, path: Path) -> Trip | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return Trip.model_validate(raw)
        except Exception:
            return None

    def _load_legacy_trip_file(self, path: Path) -> Trip | None:
        """Carga un archivo de historial en formato viejo como Trip."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return self._migrate_legacy(raw, persist=False)
        except Exception:
            return None

    def _migrate_legacy(self, raw: dict[str, Any], *, persist: bool = True) -> Trip:
        """Convierte un estado viejo (dict plano) al modelo Trip.

        Si persist=True, guarda el formato nuevo y hace backup del viejo.
        """
        # Backup antes de migrar
        if persist and self._state_file.exists():
            backup = self._state_file.with_suffix(".json.v1.bak")
            if not backup.exists():
                shutil.copy2(self._state_file, backup)

        origin_raw = raw.get("origin", {})
        origin = NamedPoint(
            name=origin_raw.get("name", "Origen"),
            coordinates=Coordinates(
                latitude=origin_raw.get("latitude", 0.0),
                longitude=origin_raw.get("longitude", 0.0),
            ),
        )

        # Migrar return_config
        rc = raw.get("return_config", {})
        return_mode = ReturnMode(rc.get("mode", "origin"))
        return_point = None
        if return_mode == ReturnMode.CUSTOM:
            cp = rc.get("custom_point", {})
            if cp.get("name"):
                return_point = NamedPoint(
                    name=cp["name"],
                    coordinates=Coordinates(
                        latitude=cp.get("latitude", 0.0),
                        longitude=cp.get("longitude", 0.0),
                    ),
                )

        # Migrar fuel_config
        fc = raw.get("fuel_config", {})
        fuel_config = None
        if fc.get("km_per_liter", 0) > 0:
            fuel_config = FuelConfig(
                km_per_liter=fc["km_per_liter"],
                fuel_price=fc.get("price_per_liter", 0.0),
            )

        # Migrar delivery_points
        deliveries: list[Delivery] = []
        for dp in raw.get("delivery_points", []):
            deliveries.append(
                Delivery(
                    delivery_id=dp.get("id", str(uuid4())),
                    client_name=dp.get("client_name", "Sin nombre"),
                    coordinates=Coordinates(
                        latitude=dp.get("latitude", 0.0),
                        longitude=dp.get("longitude", 0.0),
                    ),
                    status=dp.get("status", "pending"),
                )
            )

        trip = Trip(
            origin=origin,
            return_mode=return_mode,
            return_point=return_point,
            fuel_config=fuel_config,
            deliveries=deliveries,
        )

        if persist:
            self.save_trip(trip)

        return trip

    def _backup_corrupt(self) -> None:
        """Hace backup de un archivo de estado corrupto."""
        if self._state_file.exists():
            backup = self._state_file.with_suffix(".json.corrupt.bak")
            shutil.copy2(self._state_file, backup)
