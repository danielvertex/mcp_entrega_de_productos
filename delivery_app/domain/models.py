"""Modelos de dominio.

Pydantic BaseModels que representan las entidades del negocio.
Todas las validaciones de rango, formato y consistencia se
aplican en construcción.
"""

from __future__ import annotations

from datetime import datetime, timezone
from delivery_app.utils.time_utils import now_mx
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from delivery_app.domain.enums import (
    DeliveryStatus,
    ReturnMode,
    RouteMethod,
    TripStatus,
)


class Coordinates(BaseModel):
    """Par de coordenadas geográficas WGS84."""

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class NamedPoint(BaseModel):
    """Punto geográfico con nombre descriptivo."""

    name: str = Field(..., min_length=1)
    coordinates: Coordinates


class Delivery(BaseModel):
    """Entrega individual dentro de una jornada."""

    delivery_id: str = Field(default_factory=lambda: str(uuid4()))
    client_name: str = Field(..., min_length=1)
    coordinates: Coordinates
    status: DeliveryStatus = DeliveryStatus.PENDING
    note: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime = Field(
        default_factory=now_mx
    )
    updated_at: datetime = Field(
        default_factory=now_mx
    )
    completed_at: Optional[datetime] = None
    sequence_hint: Optional[int] = None

    @field_validator("client_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("El nombre del cliente no puede estar vacío")
        return stripped


class FuelConfig(BaseModel):
    """Configuración de combustible del vehículo."""

    km_per_liter: float = Field(..., gt=0.0)
    fuel_price: float = Field(..., ge=0.0)


class Metrics(BaseModel):
    """Métricas calculadas de una jornada."""

    planned_km: float = 0.0
    actual_km: Optional[float] = None
    planned_duration_min: float = 0.0
    estimated_fuel_liters: float = 0.0
    estimated_fuel_cost: float = 0.0


class ReturnInfo(BaseModel):
    """Información del punto de retorno en una ruta calculada."""

    mode: ReturnMode = ReturnMode.NONE
    point_name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0


class RouteResult(BaseModel):
    """Resultado de una optimización de ruta."""

    optimized_order: list[str] = Field(
        default_factory=list,
        description="Lista de delivery_ids en orden sugerido",
    )
    total_distance_km: float = 0.0
    total_duration_min: float = 0.0
    method: RouteMethod = RouteMethod.OSRM
    return_info: ReturnInfo = Field(default_factory=ReturnInfo)


class Trip(BaseModel):
    """Jornada completa de entregas.

    Entidad raíz del dominio. Contiene todas las entregas,
    configuración, ruta calculada y métricas.
    """

    trip_id: str = Field(default_factory=lambda: str(uuid4()))
    driver_id: Optional[str] = None  # TODO: para multi-user
    created_at: datetime = Field(
        default_factory=now_mx
    )
    closed_at: Optional[datetime] = None
    status: TripStatus = TripStatus.ACTIVE
    origin: NamedPoint
    return_mode: ReturnMode = ReturnMode.ORIGIN
    return_point: Optional[NamedPoint] = None
    current_location: Optional[Coordinates] = None
    route_plan: Optional[RouteResult] = None
    metrics: Metrics = Field(default_factory=Metrics)
    fuel_config: Optional[FuelConfig] = None
    deliveries: list[Delivery] = Field(default_factory=list)
