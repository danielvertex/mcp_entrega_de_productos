"""Servicio de jornadas de entrega.

Orquesta TripManager (lógica pura) con TripRepository (persistencia)
para ofrecer una interfaz completa a la capa de tools.
"""

from __future__ import annotations

from typing import Any

from delivery_app.domain import trip_manager
from delivery_app.domain.enums import DeliveryStatus, ReturnMode
from delivery_app.domain.models import (
    Coordinates,
    Delivery,
    FuelConfig,
    NamedPoint,
    RouteResult,
    Trip,
)
from delivery_app.infrastructure.json_repository import (
    JsonTripRepository,
    TripRepositoryBase,
)


class TripService:
    """Servicio principal de jornadas.

    Centraliza todas las operaciones sobre trips, garantizando
    que cada mutación se persista de forma atómica.
    """

    def __init__(self, repository: TripRepositoryBase) -> None:
        self._repo = repository

    def get_or_create_trip(self, origin: NamedPoint) -> Trip:
        """Obtiene la jornada activa o crea una nueva.

        Args:
            origin: Punto de origen para una nueva jornada.

        Returns:
            Trip activo (existente o recién creado).
        """
        trip = self._repo.load_active_trip()
        if trip is not None:
            return trip

        new_trip = trip_manager.create_trip(origin=origin)
        self._repo.save_trip(new_trip)
        return new_trip

    def load_active_trip(self) -> Trip | None:
        """Carga la jornada activa sin crear una nueva."""
        return self._repo.load_active_trip()

    def add_delivery(
        self,
        trip: Trip,
        client_name: str,
        lat: float,
        lon: float,
    ) -> Trip:
        """Agrega una entrega y persiste.

        Args:
            trip: Jornada actual.
            client_name: Nombre del cliente.
            lat: Latitud.
            lon: Longitud.

        Returns:
            Trip actualizado.
        """
        delivery = Delivery(
            client_name=client_name,
            coordinates=Coordinates(latitude=lat, longitude=lon),
        )
        updated = trip_manager.add_delivery(trip, delivery)
        self._repo.save_trip(updated)
        return updated

    def remove_delivery(self, trip: Trip, delivery_id: str) -> Trip:
        """Elimina una entrega y persiste."""
        updated = trip_manager.remove_delivery(trip, delivery_id)
        self._repo.save_trip(updated)
        return updated

    def change_status(
        self,
        trip: Trip,
        delivery_id: str,
        new_status: DeliveryStatus,
        *,
        note: str | None = None,
        reason: str | None = None,
    ) -> Trip:
        """Cambia el estado de una entrega y persiste."""
        updated = trip_manager.change_delivery_status(
            trip, delivery_id, new_status, note=note, reason=reason
        )
        self._repo.save_trip(updated)
        return updated

    def update_route(self, trip: Trip, route_result: RouteResult) -> Trip:
        """Actualiza el plan de ruta y persiste."""
        updated = trip_manager.update_route_plan(trip, route_result)
        self._repo.save_trip(updated)
        return updated

    def update_origin(self, trip: Trip, origin: NamedPoint) -> Trip:
        """Actualiza el punto de origen y persiste."""
        updated = trip.model_copy(update={"origin": origin})
        self._repo.save_trip(updated)
        return updated

    def update_return_config(
        self,
        trip: Trip,
        return_mode: ReturnMode,
        return_point: NamedPoint | None = None,
    ) -> Trip:
        """Actualiza la configuración de retorno y persiste."""
        updates: dict[str, Any] = {"return_mode": return_mode}
        if return_mode == ReturnMode.CUSTOM and return_point:
            updates["return_point"] = return_point
        elif return_mode != ReturnMode.CUSTOM:
            updates["return_point"] = None

        updated = trip.model_copy(update=updates)
        self._repo.save_trip(updated)
        return updated

    def update_fuel_config(
        self, trip: Trip, fuel_config: FuelConfig
    ) -> Trip:
        """Actualiza la configuración de combustible y persiste."""
        updated = trip_manager.update_fuel_config(trip, fuel_config)
        self._repo.save_trip(updated)
        return updated

    def close_day(self, trip: Trip) -> Trip:
        """Cierra la jornada de forma idempotente, archiva y limpia.

        Si ya está cerrada, retorna sin cambios.
        Si está activa:
          1. Cierra el trip (idempotente en trip_manager).
          2. Archiva en historial (idempotente por trip_id).
          3. Limpia el estado activo.

        Returns:
            Trip cerrado.
        """
        closed = trip_manager.close_day(trip)

        if trip.status != closed.status:
            # Solo archivar si realmente se cerró (era ACTIVE)
            self._repo.archive_trip(closed)
            self._repo.clear_active()

        return closed

    def get_summary(self, trip: Trip) -> dict:
        """Calcula el resumen de la jornada."""
        return trip_manager.get_summary(trip)

    def load_archived_trip(self, trip_id: str) -> Trip | None:
        """Carga una jornada archivada."""
        return self._repo.load_archived_trip(trip_id)

    def list_archived_trips(self) -> list[dict[str, Any]]:
        """Lista resúmenes de jornadas archivadas."""
        return self._repo.list_archived_trips()
