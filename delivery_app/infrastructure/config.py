"""Configuración centralizada de la aplicación.

Valores por defecto que se pueden sobrescribir por entorno
o configuración futura sin tocar código de negocio.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OSRMConfig:
    """Configuración del cliente OSRM."""

    base_url: str = "http://router.project-osrm.org"
    timeout_seconds: float = 10.0
    max_retries: int = 1


@dataclass(frozen=True)
class BoundingBoxConfig:
    """Zona operativa configurable.

    Si enabled=True, se valida que los puntos estén dentro del
    radio configurado desde el centro.
    """

    enabled: bool = False
    center_lat: float = 0.0
    center_lon: float = 0.0
    radius_km: float = 100.0


@dataclass(frozen=True)
class HaversineConfig:
    """Configuración del fallback Haversine."""

    correction_factor: float = 1.3
    assumed_speed_kmh: float = 40.0
    earth_radius_km: float = 6371.0


@dataclass(frozen=True)
class AppConfig:
    """Configuración raíz de la aplicación."""

    osrm: OSRMConfig = field(default_factory=OSRMConfig)
    bounding_box: BoundingBoxConfig = field(default_factory=BoundingBoxConfig)
    haversine: HaversineConfig = field(default_factory=HaversineConfig)
    duplicate_proximity_km: float = 0.05  # 50 metros


# Instancia global con defaults
default_config = AppConfig()
