"""Servicio de optimización de rutas.

Orquesta el cliente OSRM y el fallback Haversine para producir
un RouteResult limpio que el dominio pueda consumir.
"""

from __future__ import annotations

import math
from typing import Any

from delivery_app.domain.enums import ReturnMode, RouteMethod
from delivery_app.domain.models import (
    Coordinates,
    Delivery,
    NamedPoint,
    ReturnInfo,
    RouteResult,
)
from delivery_app.infrastructure.config import AppConfig, default_config
from delivery_app.infrastructure.osrm_client import OSRMClient


class RoutingService:
    """Servicio de rutas: OSRM primero, Haversine como fallback."""

    def __init__(
        self,
        osrm_client: OSRMClient | None = None,
        config: AppConfig | None = None,
    ) -> None:
        self._osrm = osrm_client or OSRMClient()
        self._config = config or default_config

    async def optimize(
        self,
        origin: NamedPoint,
        deliveries: list[Delivery],
        return_mode: ReturnMode = ReturnMode.NONE,
        return_point: NamedPoint | None = None,
    ) -> RouteResult:
        """Calcula la ruta sugerida para las entregas pendientes.

        Intenta OSRM primero. Si falla, usa Haversine + nearest-neighbor.
        OSRM usa heurísticas (farthest-insertion ≥10 pts, brute force <10)
        y no garantiza optimalidad exacta.

        Args:
            origin: Punto de partida.
            deliveries: Entregas a optimizar (deben ser solo las pendientes).
            return_mode: Modo de retorno.
            return_point: Punto de retorno personalizado.

        Returns:
            RouteResult con orden sugerido, distancia, duración y método.
        """
        return_info = self._build_return_info(return_mode, return_point, origin)

        if not deliveries:
            return RouteResult(
                optimized_order=[],
                total_distance_km=0.0,
                total_duration_min=0.0,
                method=RouteMethod.OSRM,
                return_info=return_info,
            )

        # Determinar punto de retorno efectivo
        effective_return: NamedPoint | None = None
        if return_mode == ReturnMode.ORIGIN:
            effective_return = origin
        elif return_mode == ReturnMode.CUSTOM and return_point:
            effective_return = return_point

        # Intentar OSRM
        result = await self._try_osrm(
            origin, deliveries, return_mode, effective_return, return_info
        )
        if result is not None:
            return result

        # Fallback a Haversine
        return self._haversine_fallback(
            origin, deliveries, effective_return, return_info
        )

    async def _try_osrm(
        self,
        origin: NamedPoint,
        deliveries: list[Delivery],
        return_mode: ReturnMode,
        effective_return: NamedPoint | None,
        return_info: ReturnInfo,
    ) -> RouteResult | None:
        """Intenta optimizar con OSRM."""
        # Construir coordenadas: (lon, lat) — OSRM usa lon,lat
        coords: list[tuple[float, float]] = [
            (origin.coordinates.longitude, origin.coordinates.latitude)
        ]
        for d in deliveries:
            coords.append(
                (d.coordinates.longitude, d.coordinates.latitude)
            )

        # Agregar punto de retorno custom si aplica
        if return_mode == ReturnMode.CUSTOM and effective_return:
            coords.append(
                (
                    effective_return.coordinates.longitude,
                    effective_return.coordinates.latitude,
                )
            )

        # Configurar parámetros OSRM según modo
        if return_mode == ReturnMode.ORIGIN:
            roundtrip = True
            source = "first"
            # BUG-3: OSRM Trip API no acepta 'destination' si 'roundtrip' es True.
            destination = None
        elif return_mode == ReturnMode.CUSTOM:
            roundtrip = False
            source = "first"
            destination = "last"
        else:
            roundtrip = False
            source = "first"
            destination = None

        data = await self._osrm.trip(
            coords,
            roundtrip=roundtrip,
            source=source,
            destination=destination,
        )
        if data is None:
            return None

        try:
            trip_data = data["trips"][0]
            waypoints = data["waypoints"]

            # Reconstruir orden: excluir origen (idx 0) y return point custom
            num_deliveries = len(deliveries)
            ordered_ids: list[str] = []

            for wp in waypoints:
                idx = wp["waypoint_index"]
                if idx == 0:  # origen
                    continue
                if return_mode == ReturnMode.CUSTOM and effective_return:
                    if idx == num_deliveries + 1:  # return point
                        continue
                point_idx = idx - 1
                if 0 <= point_idx < num_deliveries:
                    ordered_ids.append(deliveries[point_idx].delivery_id)

            return RouteResult(
                optimized_order=ordered_ids,
                total_distance_km=round(trip_data["distance"] / 1000, 2),
                total_duration_min=round(trip_data["duration"] / 60, 2),
                method=RouteMethod.OSRM,
                return_info=return_info,
            )
        except (KeyError, IndexError, ValueError):
            return None

    def _haversine_fallback(
        self,
        origin: NamedPoint,
        deliveries: list[Delivery],
        effective_return: NamedPoint | None,
        return_info: ReturnInfo,
    ) -> RouteResult:
        """Fallback con Haversine + nearest-neighbor."""
        cfg = self._config.haversine

        remaining = list(deliveries)
        ordered: list[Delivery] = []
        total_distance = 0.0

        current_lat = origin.coordinates.latitude
        current_lon = origin.coordinates.longitude

        while remaining:
            nearest = min(
                remaining,
                key=lambda d: _haversine(
                    current_lat,
                    current_lon,
                    d.coordinates.latitude,
                    d.coordinates.longitude,
                    cfg.earth_radius_km,
                ),
            )
            dist = _haversine(
                current_lat,
                current_lon,
                nearest.coordinates.latitude,
                nearest.coordinates.longitude,
                cfg.earth_radius_km,
            )
            total_distance += dist
            ordered.append(nearest)
            current_lat = nearest.coordinates.latitude
            current_lon = nearest.coordinates.longitude
            remaining.remove(nearest)

        # Sumar distancia de retorno
        if effective_return and ordered:
            last = ordered[-1]
            total_distance += _haversine(
                last.coordinates.latitude,
                last.coordinates.longitude,
                effective_return.coordinates.latitude,
                effective_return.coordinates.longitude,
                cfg.earth_radius_km,
            )

        total_distance *= cfg.correction_factor
        total_km = round(total_distance, 2)
        duration_min = round((total_km / cfg.assumed_speed_kmh) * 60, 2) if total_km > 0 else 0.0

        return RouteResult(
            optimized_order=[d.delivery_id for d in ordered],
            total_distance_km=total_km,
            total_duration_min=duration_min,
            method=RouteMethod.HAVERSINE_FALLBACK,
            return_info=return_info,
        )

    @staticmethod
    def _build_return_info(
        return_mode: ReturnMode,
        return_point: NamedPoint | None,
        origin: NamedPoint,
    ) -> ReturnInfo:
        """Construye la información de retorno."""
        if return_mode == ReturnMode.ORIGIN:
            return ReturnInfo(
                mode=ReturnMode.ORIGIN,
                point_name=origin.name,
                latitude=origin.coordinates.latitude,
                longitude=origin.coordinates.longitude,
            )
        elif return_mode == ReturnMode.CUSTOM and return_point:
            return ReturnInfo(
                mode=ReturnMode.CUSTOM,
                point_name=return_point.name,
                latitude=return_point.coordinates.latitude,
                longitude=return_point.coordinates.longitude,
            )
        return ReturnInfo(mode=ReturnMode.NONE)


def _haversine(
    lat1: float, lon1: float, lat2: float, lon2: float, radius: float = 6371.0
) -> float:
    """Calcula distancia en km entre dos coordenadas (haversine)."""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c
