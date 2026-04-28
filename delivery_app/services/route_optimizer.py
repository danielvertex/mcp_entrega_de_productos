"""Optimizador de rutas.

Estrategia principal: OSRM Trip API (distancias reales por calles).
Fallback: Haversine + Nearest-Neighbor (distancias en línea recta × 1.3).
"""

from __future__ import annotations

import math
from typing import Any

import httpx

# Servidor público de OSRM (para desarrollo; en producción hospedar propio)
OSRM_BASE_URL = "http://router.project-osrm.org"
OSRM_TIMEOUT = 10.0  # segundos

# Factor de corrección para haversine (línea recta → distancia real)
HAVERSINE_CORRECTION = 1.3

# Radio de la Tierra en km
EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia en km entre dos coordenadas usando haversine.

    Args:
        lat1, lon1: Coordenadas del primer punto (grados).
        lat2, lon2: Coordenadas del segundo punto (grados).

    Returns:
        Distancia en kilómetros.
    """
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def _nearest_neighbor(
    origin: dict[str, Any],
    points: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], float]:
    """Resuelve TSP con nearest-neighbor desde el origen.

    Args:
        origin: Punto de partida {"latitude": float, "longitude": float}.
        points: Lista de puntos a visitar.

    Returns:
        (ordered_points, total_distance_km) con factor de corrección 1.3x.
    """
    if not points:
        return [], 0.0

    remaining = list(points)
    ordered: list[dict[str, Any]] = []
    total_distance = 0.0

    current_lat = origin["latitude"]
    current_lon = origin["longitude"]

    while remaining:
        nearest = min(
            remaining,
            key=lambda p: haversine(
                current_lat, current_lon, p["latitude"], p["longitude"]
            ),
        )
        dist = haversine(
            current_lat, current_lon,
            nearest["latitude"], nearest["longitude"],
        )
        total_distance += dist
        ordered.append(nearest)
        current_lat = nearest["latitude"]
        current_lon = nearest["longitude"]
        remaining.remove(nearest)

    # Aplicar factor de corrección
    total_distance *= HAVERSINE_CORRECTION

    return ordered, round(total_distance, 2)


async def optimize_with_osrm(
    origin: dict[str, Any],
    points: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Optimiza la ruta usando OSRM Trip API.

    Args:
        origin: Punto de origen {"latitude", "longitude"}.
        points: Lista de puntos pendientes.

    Returns:
        dict con optimized_order, total_distance_km, total_duration_min, method
        o None si OSRM falla.
    """
    if not points:
        return {
            "optimized_order": [],
            "total_distance_km": 0.0,
            "total_duration_min": 0.0,
            "method": "osrm",
        }

    # Construir coordenadas: lon,lat (OSRM usa lon,lat)
    coords_parts = [f"{origin['longitude']},{origin['latitude']}"]
    for p in points:
        coords_parts.append(f"{p['longitude']},{p['latitude']}")
    coords_str = ";".join(coords_parts)

    url = f"{OSRM_BASE_URL}/trip/v1/driving/{coords_str}"
    params = {
        "roundtrip": "false",
        "source": "first",
        "overview": "false",
        "steps": "false",
    }

    try:
        async with httpx.AsyncClient(timeout=OSRM_TIMEOUT) as client:
            response = await client.get(url, params=params)

        if response.status_code != 200:
            return None

        data = response.json()
        if data.get("code") != "Ok":
            return None

        trip = data["trips"][0]
        waypoints = data["waypoints"]

        # Reconstruir el orden: excluir el origen (index 0 en nuestro input)
        # waypoints contiene waypoint_index (posición original) y
        # trips_index indica a qué trip pertenece
        # Necesitamos ordenar los puntos según el orden de visita en el trip
        #
        # Cada waypoint tiene 'waypoint_index' = posición en el trip
        # El orden de visita es el orden de waypoints en el array
        # pero debemos excluir el origen (primer coordenada)

        ordered_points: list[dict[str, Any]] = []
        # Los waypoints están en orden de visita.
        # "waypoint_index" indica cuál coordenada original es:
        # index 0 = origin, 1..n = points[0..n-1]
        for wp in waypoints:
            orig_idx = wp["waypoint_index"]
            # Skip origin (index 0)
            if orig_idx == 0:
                continue
            # orig_idx - 1 porque origin ocupa posición 0
            point_idx = orig_idx - 1
            if 0 <= point_idx < len(points):
                ordered_points.append(points[point_idx])

        return {
            "optimized_order": ordered_points,
            "total_distance_km": round(trip["distance"] / 1000, 2),
            "total_duration_min": round(trip["duration"] / 60, 2),
            "method": "osrm",
        }

    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None


async def optimize_route(
    origin: dict[str, Any],
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    """Optimiza la ruta. Intenta OSRM, fallback a haversine.

    Usa esta función cuando el repartidor quiera calcular el orden
    óptimo de visita para sus puntos pendientes.

    Args:
        origin: Punto de origen {"name", "latitude", "longitude"}.
        points: Lista de puntos con status "pending".

    Returns:
        {
            "optimized_order": list[dict],
            "total_distance_km": float,
            "total_duration_min": float,
            "method": "osrm" | "haversine_fallback"
        }
    """
    pending = [p for p in points if p.get("status") == "pending"]

    if not pending:
        return {
            "optimized_order": [],
            "total_distance_km": 0.0,
            "total_duration_min": 0.0,
            "method": "osrm",
        }

    # Intentar OSRM primero
    result = await optimize_with_osrm(origin, pending)
    if result is not None:
        return result

    # Fallback a haversine + nearest-neighbor
    ordered, total_km = _nearest_neighbor(origin, pending)

    # Estimar duración a 40 km/h promedio en ciudad
    duration_min = (total_km / 40) * 60 if total_km > 0 else 0.0

    return {
        "optimized_order": ordered,
        "total_distance_km": total_km,
        "total_duration_min": round(duration_min, 2),
        "method": "haversine_fallback",
    }
