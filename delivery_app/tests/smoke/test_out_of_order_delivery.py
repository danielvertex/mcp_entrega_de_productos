"""Smoke test para manejo de entregas fuera de orden."""

import pytest

from delivery_app.app import trip_service, routing_service
from delivery_app.domain.enums import DeliveryStatus, ReturnMode
from delivery_app.domain.models import Coordinates, NamedPoint


@pytest.fixture
def clean_repo(tmp_path):
    from delivery_app.infrastructure.json_repository import JsonTripRepository
    
    test_repo = JsonTripRepository(tmp_path / "test_data_ooo")
    old_repo = trip_service._repo
    trip_service._repo = test_repo
    yield test_repo
    trip_service._repo = old_repo


@pytest.mark.asyncio
async def test_out_of_order_delivery(clean_repo):
    """Simula entregar el punto B antes que el punto A."""
    trip = trip_service.get_or_create_trip(
        NamedPoint(
            name="Bodega",
            coordinates=Coordinates(latitude=21.86, longitude=-102.29),
        )
    )
    trip_service.update_return_config(trip, ReturnMode.ORIGIN)

    trip = trip_service.add_delivery(trip, "A", 21.87, -102.28)
    trip = trip_service.add_delivery(trip, "B", 21.88, -102.27)
    
    route = await routing_service.optimize(
        trip.origin, trip.deliveries, trip.return_mode, trip.return_point
    )
    trip = trip_service.update_route(trip, route)

    # Entregar B (index 1) primero
    b_id = trip.deliveries[1].delivery_id
    trip = trip_service.change_status(trip, b_id, DeliveryStatus.DELIVERED)

    # El dashboard y navigation UI deben funcionar sin caerse
    from delivery_app.app import ui_builder
    from delivery_app.ui.app_builder import PAGE_DASHBOARD
    
    prefab_app = ui_builder.build_app(PAGE_DASHBOARD)
    state = prefab_app.state
    
    assert state["_completed"] == 1
    assert state["_pending"] == 1
    
    # La navegación debe apuntar ahora a "A", y partir de "B"
    nav = state["gmaps_link"]
    assert nav["has_next"] is True
    assert nav["from_name"] == "B"
    assert nav["next_stop"]["client_name"] == "A"
