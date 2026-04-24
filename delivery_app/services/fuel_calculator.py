"""Calculadora de combustible.

Calcula litros necesarios y costo total dada la distancia,
rendimiento del vehículo y precio por litro.
"""

from __future__ import annotations


def calculate_fuel(
    distance_km: float,
    km_per_liter: float,
    price_per_liter: float,
) -> dict[str, float]:
    """Calcula litros y costo de combustible para una distancia dada.

    Args:
        distance_km: Distancia total en kilómetros.
        km_per_liter: Rendimiento del vehículo (km/litro).
        price_per_liter: Precio actual del combustible por litro.

    Returns:
        {"fuel_liters": float, "fuel_cost": float}

    Raises:
        ValueError: Si km_per_liter o price_per_liter son <= 0.
    """
    if km_per_liter <= 0:
        raise ValueError("El rendimiento debe ser mayor a 0")
    if price_per_liter <= 0:
        raise ValueError("El precio por litro debe ser mayor a 0")
    if distance_km < 0:
        raise ValueError("La distancia no puede ser negativa")

    liters = distance_km / km_per_liter
    cost = liters * price_per_liter

    return {
        "fuel_liters": round(liters, 2),
        "fuel_cost": round(cost, 2),
    }
