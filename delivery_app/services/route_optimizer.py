"""Optimizador de rutas.

Estrategia principal: OSRM Trip API (distancias reales por calles).
Fallback: Haversine + Nearest-Neighbor (distancias en línea recta × 1.3).

Soporta 3 modos de retorno:
  - "origin":  regresar al punto de origen (TSP circular clásico).
  - "custom":  regresar a un punto arbitrario elegido por el usuario.
  - "none":    ruta abierta, sin regreso.
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
    return_point: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """Resuelve TSP con nearest-neighbor desde el origen.

    Args:
        origin: Punto de partida {"latitude": float, "longitude": float}.
        points: Lista de puntos a visitar.
        return_point: Si se proporciona, suma la distancia del último
            punto visitado hasta este punto de retorno.

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

    # Sumar distancia de regreso si se solicitó
    if return_point is not None and ordered:
        last = ordered[-1]
        total_distance += haversine(
            last["latitude"], last["longitude"],
            return_point["latitude"], return_point["longitude"],
        )

    # Aplicar factor de corrección
    total_distance *= HAVERSINE_CORRECTION

    return ordered, round(total_distance, 2)


async def optimize_with_osrm(
    origin: dict[str, Any],
    points: list[dict[str, Any]],
    return_mode: str = "none",
    return_point: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Optimiza la ruta usando OSRM Trip API.

    Args:
        origin: Punto de origen {"latitude", "longitude"}.
        points: Lista de puntos pendientes.
        return_mode: "origin" | "custom" | "none".
        return_point: Punto de retorno personalizado (solo si return_mode == "custom").

    Returns:
        dict con optimized_order, total_distance_km, total_duration_min, method,
        return_info  —  o None si OSRM falla.
    """
    if not points:
        return {
            "optimized_order": [],
            "total_distance_km": 0.0,
            "total_duration_min": 0.0,
            "method": "osrm",
            "return_info": _build_return_info(return_mode, return_point, origin),
        }

    # Construir coordenadas: lon,lat (OSRM usa lon,lat)
    coords_parts = [f"{origin['longitude']},{origin['latitude']}"]
    for p in points:
        coords_parts.append(f"{p['longitude']},{p['latitude']}")

    # Si return_mode == "custom", agregar el punto de retorno como destino final
    if return_mode == "custom" and return_point is not None:
        coords_parts.append(
            f"{return_point['longitude']},{return_point['latitude']}"
        )

    coords_str = ";".join(coords_parts)

    url = f"{OSRM_BASE_URL}/trip/v1/driving/{coords_str}"

    # Configurar parámetros según el modo de retorno
    if return_mode == "origin":
        # Viaje de ida y vuelta al origen
        params = {
            "roundtrip": "true",
            "source": "first",
            "destination": "last",
            "overview": "false",
            "steps": "false",
        }
    elif return_mode == "custom":
        # Ruta abierta: origen → puntos → punto de retorno
        params = {
            "roundtrip": "false",
            "source": "first",
            "destination": "last",
            "overview": "false",
            "steps": "false",
        }
    else:
        # Sin regreso: ruta abierta desde el origen
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
        # y el punto de retorno si es custom (último index)
        num_delivery_points = len(points)

        ordered_points: list[dict[str, Any]] = []
        for wp in waypoints:
            orig_idx = wp["waypoint_index"]
            # Skip origin (index 0)
            if orig_idx == 0:
                continue
            # Skip return point (si custom, es el último)
            if return_mode == "custom" and return_point is not None:
                if orig_idx == num_delivery_points + 1:
                    continue
            # orig_idx - 1 porque origin ocupa posición 0
            point_idx = orig_idx - 1
            if 0 <= point_idx < num_delivery_points:
                ordered_points.append(points[point_idx])

        return {
            "optimized_order": ordered_points,
            "total_distance_km": round(trip["distance"] / 1000, 2),
            "total_duration_min": round(trip["duration"] / 60, 2),
            "method": "osrm",
            "return_info": _build_return_info(return_mode, return_point, origin),
        }

    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None


def _build_return_info(
    return_mode: str,
    return_point: dict[str, Any] | None,
    origin: dict[str, Any],
) -> dict[str, Any]:
    """Construye la información de retorno para incluir en el resultado.

    Returns:
        {"mode": str, "point_name": str, "latitude": float, "longitude": float}
    """
    if return_mode == "origin":
        return {
            "mode": "origin",
            "point_name": origin.get("name", "Origen"),
            "latitude": origin.get("latitude", 0.0),
            "longitude": origin.get("longitude", 0.0),
        }
    elif return_mode == "custom" and return_point is not None:
        return {
            "mode": "custom",
            "point_name": return_point.get("name", "Punto personalizado"),
            "latitude": return_point.get("latitude", 0.0),
            "longitude": return_point.get("longitude", 0.0),
        }
    else:
        return {"mode": "none", "point_name": "", "latitude": 0.0, "longitude": 0.0}


async def optimize_route(
    origin: dict[str, Any],
    points: list[dict[str, Any]],
    return_mode: str = "none",
    return_point: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Optimiza la ruta. Intenta OSRM, fallback a haversine.

    Usa esta función cuando el repartidor quiera calcular el orden
    óptimo de visita para sus puntos pendientes.

    Args:
        origin: Punto de origen {"name", "latitude", "longitude"}.
        points: Lista de puntos con status "pending".
        return_mode: Modo de retorno - "origin", "custom", o "none".
        return_point: Punto de retorno personalizado (solo si return_mode == "custom").

    Returns:
        {
            "optimized_order": list[dict],
            "total_distance_km": float,
            "total_duration_min": float,
            "method": "osrm" | "haversine_fallback",
            "return_info": {"mode": str, "point_name": str, "latitude": float, "longitude": float}
        }
    """
    pending = [p for p in points if p.get("status") == "pending"]

    if not pending:
        return {
            "optimized_order": [],
            "total_distance_km": 0.0,
            "total_duration_min": 0.0,
            "method": "osrm",
            "return_info": _build_return_info(return_mode, return_point, origin),
        }

    # Determinar el punto de regreso real para el cálculo
    effective_return_point: dict[str, Any] | None = None
    if return_mode == "origin":
        effective_return_point = origin
    elif return_mode == "custom" and return_point is not None:
        effective_return_point = return_point

    # Intentar OSRM primero
    result = await optimize_with_osrm(
        origin, pending, return_mode, effective_return_point,
    )
    if result is not None:
        return result

    # Fallback a haversine + nearest-neighbor
    ordered, total_km = _nearest_neighbor(
        origin, pending, effective_return_point,
    )

    # Estimar duración a 40 km/h promedio en ciudad
    duration_min = (total_km / 40) * 60 if total_km > 0 else 0.0

    return {
        "optimized_order": ordered,
        "total_distance_km": total_km,
        "total_duration_min": round(duration_min, 2),
        "method": "haversine_fallback",
        "return_info": _build_return_info(return_mode, return_point, origin),
    }
