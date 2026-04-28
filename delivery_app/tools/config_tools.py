"""Tools para configuración (origen, retorno, combustible)."""

from __future__ import annotations

import logging

from fastmcp import FastMCPApp

from delivery_app.domain.enums import ReturnMode
from delivery_app.domain.models import Coordinates, FuelConfig, NamedPoint
from delivery_app.services.trip_service import TripService

logger = logging.getLogger(__name__)


def register_config_tools(app: FastMCPApp, trip_service: TripService) -> None:
    """Registra los tools de configuración en la app."""

    @app.tool()
    def update_origin(name: str, latitude: str, longitude: str) -> dict:
        """Configura el punto de partida (origen) y crea la jornada si no existe."""
        try:
            lat = float(str(latitude).replace(",", ".").strip())
            lon = float(str(longitude).replace(",", ".").strip())
        except ValueError:
            raise ValueError("❌ Error: Coordenadas inválidas. Deben ser números.")

        origin = NamedPoint(
            name=name,
            coordinates=Coordinates(latitude=lat, longitude=lon),
        )

        trip = trip_service.load_active_trip()
        if trip:
            updated_trip = trip_service.update_origin(trip, origin)
        else:
            updated_trip = trip_service.get_or_create_trip(origin)

        from delivery_app.ui.state_mapper import map_trip_to_state
        state = map_trip_to_state(updated_trip, [])
        return {
            "message": f"✅ Origen configurado: {name}",
            "origin": state.get("origin"),
            "delivery_points": state.get("delivery_points", []),
            "gmaps_link": state.get("gmaps_link"),
            "_pending": state.get("_pending", 0),
            "_completed": state.get("_completed", 0),
            "summary": state.get("summary"),
        }

    @app.tool()
    def update_return_config(
        mode: str,
        custom_name: str = "",
        custom_lat: str = "0",
        custom_lon: str = "0",
    ) -> dict:
        """Configura el comportamiento de retorno al finalizar."""
        trip = trip_service.load_active_trip()
        if not trip:
            raise ValueError("❌ Error: Agregue el punto de origen primero.")

        try:
            return_mode = ReturnMode(mode)
        except ValueError:
            raise ValueError(f"❌ Error: Modo '{mode}' inválido.")

        return_point = None
        if return_mode == ReturnMode.CUSTOM:
            try:
                lat = float(str(custom_lat).replace(",", ".").strip())
                lon = float(str(custom_lon).replace(",", ".").strip())
                return_point = NamedPoint(
                    name=custom_name,
                    coordinates=Coordinates(latitude=lat, longitude=lon),
                )
            except ValueError:
                raise ValueError("❌ Error: Coordenadas personalizadas inválidas.")

        updated_trip = trip_service.update_return_config(trip, return_mode, return_point)
        from delivery_app.ui.state_mapper import map_trip_to_state
        state = map_trip_to_state(updated_trip, [])
        
        return {
            "message": f"✅ Retorno configurado a modo: {return_mode.value}",
            "return_config": state.get("return_config"),
            "gmaps_link": state.get("gmaps_link"),
        }

    @app.tool()
    def update_fuel_config(km_per_liter: str, price_per_liter: str) -> dict:
        """Configura los parámetros para cálculo de combustible."""
        trip = trip_service.load_active_trip()
        if not trip:
            raise ValueError("❌ Error: Agregue el punto de origen primero.")

        try:
            kpl = float(str(km_per_liter).replace(",", ".").strip())
            ppl = float(str(price_per_liter).replace(",", ".").strip())
            if kpl <= 0:
                raise ValueError("❌ Error: El rendimiento debe ser mayor a 0.")
            if ppl < 0:
                raise ValueError("❌ Error: El precio no puede ser negativo.")
        except ValueError:
            raise ValueError("❌ Error: Valores inválidos. Deben ser números.")

        fc = FuelConfig(km_per_liter=kpl, fuel_price=ppl)
        updated_trip = trip_service.update_fuel_config(trip, fc)
        
        from delivery_app.ui.state_mapper import map_trip_to_state
        state = map_trip_to_state(updated_trip, [])
        
        return {
            "message": "✅ Configuración de combustible guardada.",
            "fuel_config": state.get("fuel_config"),
            "summary": state.get("summary"),
        }
