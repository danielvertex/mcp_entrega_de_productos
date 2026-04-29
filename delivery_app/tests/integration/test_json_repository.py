"""Tests de integración para JsonTripRepository."""

import json

import pytest

from delivery_app.domain.enums import DeliveryStatus, ReturnMode, TripStatus
from delivery_app.domain.models import (
    Coordinates,
    Delivery,
    FuelConfig,
    NamedPoint,
    Trip,
)
from delivery_app.domain.trip_manager import add_delivery, close_day, create_trip
from delivery_app.infrastructure.json_repository import JsonTripRepository


@pytest.fixture
def repo(tmp_path):
    return JsonTripRepository(tmp_path / "data")


def _origin():
    return NamedPoint(
        name="Bodega",
        coordinates=Coordinates(latitude=21.86, longitude=-102.29),
    )


class TestSaveAndLoad:
    def test_save_and_load_roundtrip(self, repo):
        trip = create_trip(origin=_origin())
        repo.save_trip(trip)
        loaded = repo.load_active_trip()
        assert loaded is not None
        assert loaded.trip_id == trip.trip_id
        assert loaded.origin.name == "Bodega"

    def test_load_returns_none_when_empty(self, repo):
        assert repo.load_active_trip() is None

    def test_save_with_deliveries(self, repo):
        trip = create_trip(origin=_origin())
        d = Delivery(
            client_name="Test",
            coordinates=Coordinates(latitude=21.87, longitude=-102.28),
        )
        trip = add_delivery(trip, d)
        repo.save_trip(trip)

        loaded = repo.load_active_trip()
        assert len(loaded.deliveries) == 1
        assert loaded.deliveries[0].client_name == "Test"

    def test_save_with_fuel_config(self, repo):
        fc = FuelConfig(km_per_liter=12.0, fuel_price=23.50)
        trip = create_trip(origin=_origin(), fuel_config=fc)
        repo.save_trip(trip)

        loaded = repo.load_active_trip()
        assert loaded.fuel_config is not None
        assert loaded.fuel_config.km_per_liter == 12.0


class TestMigrateLegacy:
    def test_migrates_old_format(self, repo):
        """Un archivo viejo (sin trip_id) se migra automáticamente."""
        old_state = {
            "origin": {"name": "B&G HQ", "latitude": 21.86, "longitude": -102.29},
            "delivery_points": [
                {"id": "abc", "client_name": "Test", "latitude": 21.87,
                 "longitude": -102.28, "status": "pending"},
            ],
            "fuel_config": {"km_per_liter": 5.0, "price_per_liter": 29.5},
            "return_config": {"mode": "origin", "custom_point": {"name": "", "latitude": 0.0, "longitude": 0.0}},
            "optimized_route": {"optimized_order": [], "total_distance_km": 0.0,
                               "total_duration_min": 0.0, "method": ""},
            "summary": {"completed": 0, "pending": 1},
        }
        state_file = repo._state_file
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(old_state), encoding="utf-8")

        trip = repo.load_active_trip()
        assert trip is not None
        assert trip.trip_id  # Should have been generated
        assert trip.origin.name == "B&G HQ"
        assert len(trip.deliveries) == 1
        assert trip.deliveries[0].client_name == "Test"
        assert trip.fuel_config.km_per_liter == 5.0

    def test_creates_backup_on_migration(self, repo):
        old_state = {
            "origin": {"name": "Test", "latitude": 0.0, "longitude": 0.0},
            "delivery_points": [],
            "fuel_config": {"km_per_liter": 0.0, "price_per_liter": 0.0},
            "return_config": {"mode": "none"},
        }
        state_file = repo._state_file
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(old_state), encoding="utf-8")

        repo.load_active_trip()
        backup = state_file.with_suffix(".json.v1.bak")
        assert backup.exists()


class TestCorruptionHandling:
    def test_handles_corrupt_json(self, repo):
        state_file = repo._state_file
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("{invalid json!!!", encoding="utf-8")

        result = repo.load_active_trip()
        assert result is None

        backup = state_file.with_suffix(".json.corrupt.bak")
        assert backup.exists()


class TestArchiveAndHistory:
    def test_archive_and_list(self, repo):
        trip = create_trip(origin=_origin())
        d = Delivery(
            client_name="Test",
            coordinates=Coordinates(latitude=21.87, longitude=-102.28),
        )
        trip = add_delivery(trip, d)
        trip = close_day(trip)

        repo.save_trip(trip)
        archive_id = repo.archive_trip(trip)
        assert archive_id == trip.trip_id

        trips = repo.list_archived_trips()
        assert len(trips) == 1
        assert trips[0]["trip_id"] == trip.trip_id

    def test_archive_idempotent(self, repo):
        """Archivar el mismo trip dos veces no duplica."""
        trip = create_trip(origin=_origin())
        trip = close_day(trip)

        repo.archive_trip(trip)
        repo.archive_trip(trip)

        trips = repo.list_archived_trips()
        assert len(trips) == 1

    def test_load_archived(self, repo):
        trip = create_trip(origin=_origin())
        trip = close_day(trip)
        repo.archive_trip(trip)

        loaded = repo.load_archived_trip(trip.trip_id)
        assert loaded is not None
        assert loaded.trip_id == trip.trip_id

    def test_load_nonexistent_archived(self, repo):
        assert repo.load_archived_trip("nonexistent") is None

    def test_clear_active(self, repo):
        trip = create_trip(origin=_origin())
        repo.save_trip(trip)
        assert repo.load_active_trip() is not None

        repo.clear_active()
        assert repo.load_active_trip() is None

    def test_load_archived_legacy_fallback(self, repo):
        """BUG-1: Probar que carga archivos viejos por coincidencia parcial de nombre."""
        legacy_data = {
            "origin": {"name": "Viejo", "latitude": 0.0, "longitude": 0.0},
            "delivery_points": [],
        }
        # Guardar con un nombre que no es trip_id (ej: fecha)
        history_dir = repo._history_dir
        history_dir.mkdir(parents=True, exist_ok=True)
        f = history_dir / "2024-04-28.json"
        f.write_text(json.dumps(legacy_data), encoding="utf-8")

        # Debe cargar por coincidencia parcial
        loaded = repo.load_archived_trip("2024-04-28")
        assert loaded is not None
        assert loaded.origin.name == "Viejo"
