"""Servicio de combustible.

Wrapper sobre fuel_calculator para usar los nuevos modelos de dominio.
"""

from __future__ import annotations

from delivery_app.domain.models import FuelConfig
from delivery_app.services.fuel_calculator import calculate_fuel


def calculate_fuel_cost(
    distance_km: float,
    config: FuelConfig | None,
) -> tuple[float, float]:
    """Calcula litros de combustible y costo.

    Args:
        distance_km: Distancia a recorrer.
        config: Configuración de combustible.

    Returns:
        (litros, costo)
    """
    if not config or distance_km <= 0:
        return 0.0, 0.0

    try:
        res = calculate_fuel(
            distance_km,
            config.km_per_liter,
            config.fuel_price,
        )
        return res["fuel_liters"], res["fuel_cost"]
    except ValueError:
        return 0.0, 0.0
