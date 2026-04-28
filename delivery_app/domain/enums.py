"""Enums del dominio de entregas.

Define los estados y modos que rigen la lógica de negocio.
Usar enums en lugar de strings libres previene errores de tipeo
y hace explícitos los valores válidos.
"""

from __future__ import annotations

from enum import Enum


class DeliveryStatus(str, Enum):
    """Estado de una entrega individual."""

    PENDING = "pending"
    DELIVERED = "delivered"
    NOT_FOUND = "not_found"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class ReturnMode(str, Enum):
    """Modo de retorno al finalizar la ruta."""

    ORIGIN = "origin"    # Regresar al punto de origen
    CUSTOM = "custom"    # Regresar a un punto personalizado
    NONE = "none"        # Ruta abierta, sin regreso


class TripStatus(str, Enum):
    """Estado de una jornada de entrega."""

    ACTIVE = "active"
    CLOSED = "closed"


class RouteMethod(str, Enum):
    """Método utilizado para calcular la ruta.

    OSRM usa heurísticas (farthest-insertion ≥10 puntos, brute force <10).
    Haversine es un fallback con distancias en línea recta × 1.3.
    Ninguno de los dos garantiza optimalidad exacta.
    """

    OSRM = "osrm"
    HAVERSINE_FALLBACK = "haversine_fallback"
