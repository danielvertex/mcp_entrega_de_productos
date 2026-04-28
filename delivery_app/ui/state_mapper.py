"""UI state mapper. Mapea el dominio a diccionarios para prefab-ui."""

from __future__ import annotations

from typing import Any

from delivery_app.domain.enums import ReturnMode
from delivery_app.domain.models import Trip
from delivery_app.domain.trip_manager import get_summary
from delivery_app.services.navigation_service import get_next_navigation


def map_trip_to_state(trip: Trip | None, past_trips: list[dict[str, Any]]) -> dict[str, Any]:
    """Genera el diccionario de estado para PrefabApp."""
    if not trip:
        return _empty_state(past_trips)

    # Generar la lista base de puntos
    points = []
    for d in trip.deliveries:
        points.append({
            "id": d.delivery_id,
            "client_name": d.client_name,
            "latitude": d.coordinates.latitude,
            "longitude": d.coordinates.longitude,
            "status": d.status.value,
        })

    # Si hay una ruta optimizada, ordenar 'points' de acuerdo al 'optimized_order'
    if trip.route_plan and trip.route_plan.optimized_order:
        # Crear un mapa para lookup rápido del orden
        order_map = {d_id: idx for idx, d_id in enumerate(trip.route_plan.optimized_order)}
        # Los puntos que no estén en optimized_order (por si acaso) irán al final
        points.sort(key=lambda p: order_map.get(p["id"], 999999))

    completed = sum(1 for p in points if p["status"] == "delivered")
    pending = sum(1 for p in points if p["status"] == "pending")

    origin = {
        "name": trip.origin.name,
        "latitude": trip.origin.coordinates.latitude,
        "longitude": trip.origin.coordinates.longitude,
    }

    if trip.route_plan:
        ri = trip.route_plan.return_info
        return_info = {
            "mode": ri.mode.value,
            "point_name": ri.point_name,
            "latitude": ri.latitude,
            "longitude": ri.longitude,
        }
        optimized_route = {
            "total_distance_km": trip.route_plan.total_distance_km,
            "total_duration_min": trip.route_plan.total_duration_min,
            "method": trip.route_plan.method.value,
            "return_info": return_info,
        }
    else:
        optimized_route = {
            "total_distance_km": 0.0,
            "total_duration_min": 0.0,
            "method": "",
            "return_info": {"mode": "none", "point_name": "", "latitude": 0.0, "longitude": 0.0},
        }

    fuel_config = {"km_per_liter": 0.0, "price_per_liter": 0.0}
    if trip.fuel_config:
        fuel_config = {
            "km_per_liter": trip.fuel_config.km_per_liter,
            "price_per_liter": trip.fuel_config.fuel_price,
        }

    return_config = {"mode": trip.return_mode.value, "custom_point": {}}
    if trip.return_mode == ReturnMode.CUSTOM and trip.return_point:
        return_config["custom_point"] = {
            "name": trip.return_point.name,
            "latitude": trip.return_point.coordinates.latitude,
            "longitude": trip.return_point.coordinates.longitude,
        }

    nav = get_next_navigation(trip)
    gmaps_link = {
        "url": nav.url,
        "from_name": nav.from_name,
        "next_stop": {
            "client_name": nav.next_stop_name,
            "latitude": nav.next_stop_lat,
            "longitude": nav.next_stop_lon,
        } if nav.has_next else None,
        "has_next": nav.has_next,
        "is_return": nav.is_return,
    }

    return {
        "delivery_points": points,
        "_completed": completed,
        "_pending": pending,
        "origin": origin,
        "optimized_route": optimized_route,
        "fuel_config": fuel_config,
        "return_config": return_config,
        "past_trips": past_trips,
        "gmaps_link": gmaps_link,
        "summary": get_summary(trip),
        "page": "dashboard",
    }


def _empty_state(past_trips: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "delivery_points": [],
        "_completed": 0,
        "_pending": 0,
        "origin": {"name": "", "latitude": 0.0, "longitude": 0.0},
        "optimized_route": {
            "total_distance_km": 0.0,
            "total_duration_min": 0.0,
            "method": "",
            "return_info": {"mode": "none", "point_name": "", "latitude": 0.0, "longitude": 0.0},
        },
        "fuel_config": {"km_per_liter": 0.0, "price_per_liter": 0.0},
        "return_config": {"mode": "none", "custom_point": {}},
        "past_trips": past_trips,
        "gmaps_link": {"url": "", "next_stop": None, "has_next": False},
        "summary": {},
        "page": "dashboard",
    }
