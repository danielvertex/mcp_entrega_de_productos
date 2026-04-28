"""Smoke tests para la aplicación completa."""

import pytest
from fastmcp import FastMCPApp

from delivery_app.app import (
    app,
    repo,
    routing_service,
    trip_service,
)
from delivery_app.domain.enums import ReturnMode, TripStatus
from delivery_app.domain.models import Coordinates, NamedPoint
from delivery_app.ui.app_builder import PAGE_DASHBOARD


@pytest.fixture
def clean_repo(tmp_path):
    """Reemplaza el repo de la app global por uno limpio en memoria/tmp."""
    from delivery_app.infrastructure.json_repository import JsonTripRepository
    
    test_repo = JsonTripRepository(tmp_path / "test_data")
    old_repo = trip_service._repo
    trip_service._repo = test_repo
    yield test_repo
    trip_service._repo = old_repo


@pytest.mark.asyncio
async def test_happy_path(clean_repo):
    """Simula un flujo completo del repartidor."""
    # 1. Configurar origen
    trip_service.get_or_create_trip(
        NamedPoint(
            name="Bodega",
            coordinates=Coordinates(latitude=21.86, longitude=-102.29),
        )
    )

    trip = trip_service.load_active_trip()
    assert trip is not None
    assert trip.origin.name == "Bodega"

    # 2. Configurar retorno
    trip_service.update_return_config(trip, ReturnMode.NONE)

    # 3. Agregar puntos
    trip = trip_service.add_delivery(trip, "Cliente 1", 21.87, -102.28)
    trip = trip_service.add_delivery(trip, "Cliente 2", 21.88, -102.27)
    assert len(trip.deliveries) == 2

    # 4. Optimizar ruta
    # Como no estamos mockeando OSRM aquí, usamos el fallback interno 
    # si no hay conexión, pero probamos la integración de las capas.
    route = await routing_service.optimize(
        trip.origin, trip.deliveries, trip.return_mode, trip.return_point
    )
    trip = trip_service.update_route(trip, route)
    assert trip.route_plan is not None

    # 5. UI Builder funciona sin errores
    from delivery_app.app import ui_builder
    prefab_app = ui_builder.build_app(PAGE_DASHBOARD)
    assert prefab_app.state["_pending"] == 2

    # 6. Cerrar día
    closed = trip_service.close_day(trip)
    assert closed.status == TripStatus.CLOSED

    # Verificar que se limpió el estado activo
    assert trip_service.load_active_trip() is None
    
    # Verificar que se archivó
    history = clean_repo.list_archived_trips()
    assert len(history) == 1
    assert history[0]["trip_id"] == closed.trip_id
