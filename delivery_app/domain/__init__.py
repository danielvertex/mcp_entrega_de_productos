"""Domain layer — entidades, enums, reglas de negocio y validaciones."""

from delivery_app.domain.enums import (
    DeliveryStatus,
    ReturnMode,
    RouteMethod,
    TripStatus,
)
from delivery_app.domain.models import (
    Coordinates,
    Delivery,
    FuelConfig,
    Metrics,
    ReturnInfo,
    RouteResult,
    Trip,
)

__all__ = [
    "Coordinates",
    "Delivery",
    "DeliveryStatus",
    "FuelConfig",
    "Metrics",
    "ReturnInfo",
    "ReturnMode",
    "RouteMethod",
    "RouteResult",
    "Trip",
    "TripStatus",
]
