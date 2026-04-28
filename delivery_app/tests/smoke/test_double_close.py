"""Smoke test para prevención de doble submit en el cierre de jornada."""

import pytest

from delivery_app.app import trip_service
from delivery_app.domain.models import Coordinates, NamedPoint
from delivery_app.domain.enums import TripStatus


@pytest.fixture
def clean_repo(tmp_path):
    from delivery_app.infrastructure.json_repository import JsonTripRepository
    
    test_repo = JsonTripRepository(tmp_path / "test_data_dc")
    old_repo = trip_service._repo
    trip_service._repo = test_repo
    yield test_repo
    trip_service._repo = old_repo


def test_double_close_is_idempotent(clean_repo):
    """Simula hacer doble click en el botón 'Cerrar Día'."""
    trip = trip_service.get_or_create_trip(
        NamedPoint(
            name="Bodega",
            coordinates=Coordinates(latitude=21.86, longitude=-102.29),
        )
    )
    
    # Primer click
    closed1 = trip_service.close_day(trip)
    assert closed1.status == TripStatus.CLOSED
    
    history1 = clean_repo.list_archived_trips()
    assert len(history1) == 1
    
    # Segundo click (el frontend envía request)
    # En el backend, el tool hace:
    trip_from_db = trip_service.load_active_trip()
    
    # El resultado debe ser None porque el estado activo se limpió
    assert trip_from_db is None
    
    # El archivo no debió duplicarse en el historial
    history2 = clean_repo.list_archived_trips()
    assert len(history2) == 1
    assert history1[0]["trip_id"] == history2[0]["trip_id"]
