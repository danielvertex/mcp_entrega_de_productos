"""Servicio de navegación punto a punto.

Determina el siguiente destino en la cadena de entregas y genera
la URL de Google Maps con la lógica de precedencia correcta para
el punto de partida.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from delivery_app.domain.enums import DeliveryStatus, ReturnMode
from delivery_app.domain.models import Coordinates, Delivery, Trip
from delivery_app.infrastructure.maps_url_builder import build_gmaps_url


@dataclass(frozen=True)
class NavigationResult:
    """Resultado del cálculo de navegación."""

    url: str
    from_name: str
    next_stop_name: str
    next_stop_lat: float
    next_stop_lon: float
    has_next: bool
    is_return: bool


def get_next_navigation(
    trip: Trip,
    current_lat: float | None = None,
    current_lon: float | None = None,
) -> NavigationResult:
    """Calcula la navegación al siguiente punto de la cadena.

    Precedencia para determinar el origen de navegación:
      1. current_lat/current_lon explícitos (override manual)
      2. current_location del trip (última entrega completada)
      3. Origen configurado del trip

    Args:
        trip: Jornada actual.
        current_lat: Override manual de latitud.
        current_lon: Override manual de longitud.

    Returns:
        NavigationResult con URL y metadatos del siguiente punto.
    """
    # Construir mapa de entregas por ID para lookup rápido
    deliveries_by_id = {d.delivery_id: d for d in trip.deliveries}

    # Obtener el orden optimizado
    ordered_ids: list[str] = []
    if trip.route_plan:
        ordered_ids = trip.route_plan.optimized_order

    # Construir lista ordenada: seguir el plan de ruta y agregar puntos nuevos al final
    ordered_deliveries: list[Delivery] = []
    if ordered_ids:
        # 1. Puntos que están en el plan de ruta (en su orden optimizado)
        for did in ordered_ids:
            d = deliveries_by_id.get(did)
            if d:
                ordered_deliveries.append(d)
        
        # 2. Puntos que NO están en el plan (agregados después de optimizar)
        planned_ids = set(ordered_ids)
        for d in trip.deliveries:
            if d.delivery_id not in planned_ids:
                ordered_deliveries.append(d)
    else:
        # Sin plan de ruta, usar orden de creación
        ordered_deliveries = list(trip.deliveries)

    # Encontrar último entregado y siguiente pendiente en la secuencia
    last_delivered: Delivery | None = None
    next_stop: Delivery | None = None

    for d in ordered_deliveries:
        # BUG-2: Considerar todos los estados "visitados" como origen potencial
        # para el siguiente tramo, no solo los entregados con éxito.
        visited_states = {
            DeliveryStatus.DELIVERED,
            DeliveryStatus.NOT_FOUND,
            DeliveryStatus.CANCELLED,
            DeliveryStatus.REJECTED,
            DeliveryStatus.RESCHEDULED,
        }

        if d.status in visited_states:
            last_delivered = d
        elif d.status == DeliveryStatus.PENDING and next_stop is None:
            next_stop = d

    # Determinar punto de partida
    from_lat, from_lon, from_name = _resolve_origin(
        trip, last_delivered, current_lat, current_lon
    )

    # Si hay un punto pendiente → navegar hacia él
    if next_stop:
        url = build_gmaps_url(
            from_lat, from_lon,
            next_stop.coordinates.latitude,
            next_stop.coordinates.longitude,
        )
        return NavigationResult(
            url=url,
            from_name=from_name,
            next_stop_name=next_stop.client_name,
            next_stop_lat=next_stop.coordinates.latitude,
            next_stop_lon=next_stop.coordinates.longitude,
            has_next=True,
            is_return=False,
        )

    # Todos entregados → navegar al punto de retorno
    if trip.return_mode == ReturnMode.NONE:
        return NavigationResult(
            url="",
            from_name=from_name,
            next_stop_name="",
            next_stop_lat=0.0,
            next_stop_lon=0.0,
            has_next=False,
            is_return=False,
        )

    # Determinar destino de retorno
    if trip.return_mode == ReturnMode.CUSTOM and trip.return_point:
        ret_lat = trip.return_point.coordinates.latitude
        ret_lon = trip.return_point.coordinates.longitude
        ret_name = trip.return_point.name
    else:
        ret_lat = trip.origin.coordinates.latitude
        ret_lon = trip.origin.coordinates.longitude
        ret_name = trip.origin.name

    url = build_gmaps_url(from_lat, from_lon, ret_lat, ret_lon)
    return NavigationResult(
        url=url,
        from_name=from_name,
        next_stop_name=ret_name,
        next_stop_lat=ret_lat,
        next_stop_lon=ret_lon,
        has_next=True,
        is_return=True,
    )


def _resolve_origin(
    trip: Trip,
    last_delivered: Delivery | None,
    current_lat: float | None,
    current_lon: float | None,
) -> tuple[float, float, str]:
    """Resuelve el punto de partida según la precedencia definida.

    Returns:
        (latitude, longitude, display_name)
    """
    # 1. Override manual
    if current_lat is not None and current_lon is not None:
        return current_lat, current_lon, "Ubicación actual"

    # 2. current_location del trip (actualizado al completar entregas)
    if trip.current_location:
        # Intentar encontrar el nombre de la entrega que coincide con estas coordenadas
        name = "Última ubicación"
        
        # Buscar coincidencia exacta en coordenadas primero
        for d in trip.deliveries:
            if (abs(d.coordinates.latitude - trip.current_location.latitude) < 1e-7 and 
                abs(d.coordinates.longitude - trip.current_location.longitude) < 1e-7):
                name = d.client_name
                break
        else:
            # Si no hay coincidencia exacta, fallback al nombre del último visitado en la secuencia
            if last_delivered:
                name = last_delivered.client_name
                
        return (
            trip.current_location.latitude,
            trip.current_location.longitude,
            name,
        )

    # 3. Último visitado según secuencia (fallback si current_location es None)
    if last_delivered:
        return (
            last_delivered.coordinates.latitude,
            last_delivered.coordinates.longitude,
            last_delivered.client_name,
        )

    # 4. Origen del trip (bodega)
    return (
        trip.origin.coordinates.latitude,
        trip.origin.coordinates.longitude,
        trip.origin.name,
    )
