"""Tests para el servicio de persistencia."""

import json

import pytest

from delivery_app.services.persistence import (
    DEFAULT_STATE,
    load_state,
    save_state,
    archive_day,
    load_trip,
    list_trips,
    DATA_DIR,
    STATE_FILE,
    HISTORY_DIR,
)


@pytest.fixture(autouse=True)
def clean_data(tmp_path, monkeypatch):
    """Redirige DATA_DIR a un directorio temporal para cada test."""
    test_data = tmp_path / "data"
    test_state = test_data / "delivery_state.json"
    test_history = test_data / "history"

    import delivery_app.services.persistence as mod

    monkeypatch.setattr(mod, "DATA_DIR", test_data)
    monkeypatch.setattr(mod, "STATE_FILE", test_state)
    monkeypatch.setattr(mod, "HISTORY_DIR", test_history)

    yield test_data


class TestLoadState:
    def test_returns_default_when_no_file(self):
        state = load_state()
        assert state["delivery_points"] == []
        assert state["origin"]["name"] == "Bodega Principal"

    def test_loads_existing_state(self, clean_data):
        custom = DEFAULT_STATE.copy()
        custom["origin"] = {"name": "Bodega Sur", "latitude": 1.0, "longitude": 2.0}
        save_state(custom)

        loaded = load_state()
        assert loaded["origin"]["name"] == "Bodega Sur"

    def test_handles_corrupt_json(self, clean_data):
        clean_data.mkdir(parents=True, exist_ok=True)
        state_file = clean_data / "delivery_state.json"
        state_file.write_text("{invalid json!!!", encoding="utf-8")

        state = load_state()
        assert state == DEFAULT_STATE
        # Debe crear backup
        assert (clean_data / "delivery_state.json.bak").exists()


class TestArchiveDay:
    def test_archives_and_cleans(self, clean_data):
        state = DEFAULT_STATE.copy()
        state["delivery_points"] = [
            {"id": "1", "client_name": "Test", "latitude": 1.0,
             "longitude": 2.0, "status": "delivered"}
        ]
        state["origin"] = {"name": "MiBodega", "latitude": 10.0, "longitude": 20.0}
        save_state(state)

        archived_date = archive_day(state)
        assert archived_date  # No vacío

        # Debe existir el archivo de historial
        history_file = clean_data / "history" / f"{archived_date}.json"
        assert history_file.exists()

        # El estado activo debe estar limpio pero con origin
        new_state = load_state()
        assert new_state["delivery_points"] == []
        assert new_state["origin"]["name"] == "MiBodega"


class TestLoadTrip:
    def test_returns_none_for_nonexistent(self):
        result = load_trip("2020-01-01")
        assert result is None

    def test_loads_existing_trip(self, clean_data):
        state = DEFAULT_STATE.copy()
        state["delivery_points"] = [
            {"id": "1", "client_name": "Test", "latitude": 1.0,
             "longitude": 2.0, "status": "delivered"}
        ]
        save_state(state)
        archived_date = archive_day(state)

        trip = load_trip(archived_date)
        assert trip is not None
        assert len(trip["delivery_points"]) == 1


class TestListTrips:
    def test_empty_history(self):
        trips = list_trips()
        assert trips == []

    def test_lists_archived_trips(self, clean_data):
        state = DEFAULT_STATE.copy()
        state["summary"] = {
            "completed": 3, "pending": 0,
            "total_km": 15.0, "total_duration_min": 25.0,
            "fuel_liters": 1.5, "fuel_cost": 30.0,
            "optimized_order": [],
        }
        save_state(state)
        archive_day(state)

        trips = list_trips()
        assert len(trips) == 1
        assert trips[0]["completed"] == 3
