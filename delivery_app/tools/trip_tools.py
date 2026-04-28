"""Tools para gestionar la jornada (cerrar día)."""

from __future__ import annotations

import logging

from fastmcp import FastMCPApp

from delivery_app.services.trip_service import TripService

logger = logging.getLogger(__name__)


def register_trip_tools(app: FastMCPApp, trip_service: TripService) -> None:
    """Registra los tools de gestión de jornada en la app."""

    @app.tool()
    def close_day() -> dict:
        """Cierra la jornada activa, archiva los datos y limpia el estado.

        Esta operación es idempotente y guardará el resumen en el historial.
        """
        trip = trip_service.load_active_trip()
        if not trip:
            raise ValueError("❌ Error: No hay jornada activa para cerrar.")

        closed = trip_service.close_day(trip)
        
        # Obtener historial actualizado para el estado vacío
        past_trips = trip_service.list_archived_trips()
        from delivery_app.ui.state_mapper import map_trip_to_state
        state = map_trip_to_state(None, past_trips)
        
        return {
            "message": f"✅ Jornada cerrada y archivada exitosamente (ID: {closed.trip_id}).",
            "state": state
        }
