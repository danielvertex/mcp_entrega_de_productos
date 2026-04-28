"""Tools para optimización y navegación de rutas."""

from __future__ import annotations

import logging

from fastmcp import FastMCPApp

from delivery_app.domain.trip_manager import get_pending_deliveries
from delivery_app.services.routing_service import RoutingService
from delivery_app.services.trip_service import TripService

logger = logging.getLogger(__name__)


def register_route_tools(
    app: FastMCPApp,
    trip_service: TripService,
    routing_service: RoutingService,
) -> None:
    """Registra los tools de ruta en la app."""

    @app.tool()
    async def optimize_route() -> str:
        """Calcula la ruta sugerida para las entregas pendientes."""
        trip = trip_service.load_active_trip()
        if not trip:
            raise ValueError("❌ Error: Agregue el punto de origen primero.")

        pending = get_pending_deliveries(trip)
        if not pending:
            return "⚠️ No hay entregas pendientes para optimizar."

        # Calcular ruta
        route_result = await routing_service.optimize(
            origin=trip.origin,
            deliveries=pending,
            return_mode=trip.return_mode,
            return_point=trip.return_point,
        )

        # Actualizar plan en el trip y persistir
        trip_service.update_route(trip, route_result)

        method_str = "OSRM" if route_result.method.value == "osrm" else "Fallback (Haversine)"
        return (
            f"✅ Ruta calculada ({method_str}): "
            f"{route_result.total_distance_km} km en "
            f"{route_result.total_duration_min} minutos."
        )

    # Nota: get_next_stop no es un tool porque se usa internamente
    # en el frontend para generar la UI de navegación.
