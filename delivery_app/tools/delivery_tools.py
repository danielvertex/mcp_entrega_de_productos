"""Tools para gestionar las entregas individuales."""

from __future__ import annotations

import logging

from fastmcp import FastMCPApp

from delivery_app.domain.enums import DeliveryStatus
from delivery_app.domain.validators import validate_delivery_input
from delivery_app.infrastructure.config import default_config
from delivery_app.services.trip_service import TripService

logger = logging.getLogger(__name__)


def register_delivery_tools(app: FastMCPApp, trip_service: TripService) -> None:
    """Registra los tools de entregas en la app."""

    @app.tool()
    def add_delivery_point(
        client_name: str,
        latitude: str,
        longitude: str,
    ) -> dict:
        """Agrega un nuevo punto de entrega a la ruta.

        Valida que el punto esté dentro de la zona operativa y que no
        sea un duplicado antes de agregarlo.
        """
        try:
            lat = float(str(latitude).replace(",", "."))
            lon = float(str(longitude).replace(",", "."))
        except ValueError:
            raise ValueError("❌ Error: Coordenadas inválidas. Deben ser números.")

        trip = trip_service.load_active_trip()
        if not trip:
            raise ValueError("❌ Error: Agregue el punto de origen primero.")

        # Validaciones de negocio
        errors = validate_delivery_input(
            client_name=client_name,
            lat=lat,
            lon=lon,
            existing_deliveries=trip.deliveries,
            center_lat=trip.origin.coordinates.latitude,
            center_lon=trip.origin.coordinates.longitude,
            radius_km=default_config.bounding_box.radius_km,
        )

        if errors:
            msg = "\n".join(f"- {e.message}" for e in errors)
            raise ValueError(f"❌ Error de validación:\n{msg}")

        # Agregar entrega
        updated_trip = trip_service.add_delivery(trip, client_name, lat, lon)
        from delivery_app.ui.state_mapper import map_trip_to_state
        state = map_trip_to_state(updated_trip, [])
        return {
            "message": f"✅ Punto agregado: {client_name} ({lat}, {lon})",
            "points": state.get("delivery_points", []),
            "gmaps_link": state.get("gmaps_link", {}),
            "_pending": state.get("_pending", 0),
            "_completed": state.get("_completed", 0),
            "summary": state.get("summary")
        }

    @app.tool()
    def remove_delivery_point(delivery_id: str) -> dict:
        """Elimina un punto de entrega por su ID."""
        trip = trip_service.load_active_trip()
        if not trip:
            raise ValueError("❌ Error: Agregue el punto de origen primero.")

        try:
            updated_trip = trip_service.remove_delivery(trip, delivery_id)
            from delivery_app.ui.state_mapper import map_trip_to_state
            state = map_trip_to_state(updated_trip, [])
            return {
                "message": "✅ Punto eliminado exitosamente.",
                "points": state.get("delivery_points", []),
                "gmaps_link": state.get("gmaps_link", {}),
                "_pending": state.get("_pending", 0),
                "_completed": state.get("_completed", 0),
                "summary": state.get("summary")
            }
        except ValueError as e:
            raise ValueError(f"❌ Error: {e}")

    @app.tool()
    def mark_delivery_status(
        delivery_id: str,
        status: str,
        note: str = "",
        reason: str = "",
    ) -> dict:
        """Cambia el estado de una entrega (pending, delivered, not_found, etc)."""
        trip = trip_service.load_active_trip()
        if not trip:
            raise ValueError("❌ Error: No hay jornada activa.")

        try:
            new_status = DeliveryStatus(status)
        except ValueError:
            raise ValueError(f"❌ Error: Estado '{status}' no es válido.")

        try:
            updated_trip = trip_service.change_status(
                trip,
                delivery_id,
                new_status,
                note=note,
                reason=reason,
            )
            from delivery_app.ui.state_mapper import map_trip_to_state
            state = map_trip_to_state(updated_trip, [])
            return {
                "message": f"✅ Estado actualizado a {new_status.value}.",
                "points": state.get("delivery_points", []),
                "gmaps_link": state.get("gmaps_link", {}),
                "_pending": state.get("_pending", 0),
                "_completed": state.get("_completed", 0),
                "summary": state.get("summary")
            }
        except ValueError as e:
            raise ValueError(f"❌ Error: {e}")
