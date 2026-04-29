"""Validaciones de negocio para datos de entrada.

Funciones puras que validan coordenadas, detectan duplicados,
comprueban bounding box y nombres. No dependen de estado externo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from delivery_app.domain.models import Coordinates, Delivery


@dataclass(frozen=True)
class ValidationError:
    """Error de validación con campo y mensaje."""

    field: str
    message: str


def validate_coordinates(lat: float, lon: float) -> list[ValidationError]:
    """Valida que latitud y longitud estén en rangos WGS84.

    Returns:
        Lista de errores (vacía si todo es válido).
    """
    errors: list[ValidationError] = []

    if not (-90.0 <= lat <= 90.0):
        errors.append(
            ValidationError("latitude", f"Latitud {lat} fuera de rango [-90, 90]")
        )
    if not (-180.0 <= lon <= 180.0):
        errors.append(
            ValidationError("longitude", f"Longitud {lon} fuera de rango [-180, 180]")
        )
    return errors


def check_suspicious_swap(lat: float, lon: float) -> ValidationError | None:
    """Detecta coordenadas posiblemente invertidas o erróneas.

    Heurísticas:
    1. Si |lat| > 90 y |lon| <= 90, es probable que se hayan intercambiado.
    2. BUG-6: En el contexto de México, la longitud DEBE ser negativa.
       Si lon > 0, es probable que falte el signo menos o estén invertidas.

    Returns:
        ValidationError si se detecta anomalía sospechosa, None en caso contrario.
    """
    if abs(lat) > 90.0 and abs(lon) <= 90.0:
        return ValidationError(
            "coordinates",
            f"Coordenadas posiblemente invertidas: lat={lat}, lon={lon}. "
            f"¿Quisiste decir lat={lon}, lon={lat}?",
        )

    if lon > 0:
        return ValidationError(
            "longitude",
            f"Longitud positiva ({lon}) detectada. En México la longitud es negativa "
            f"(aprox. -99 a -118). Revisa si falta el signo menos o están invertidas.",
        )

    return None


def check_bounding_box(
    lat: float,
    lon: float,
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> ValidationError | None:
    """Verifica que un punto esté dentro del radio operativo.

    Usa una aproximación rápida de distancia (no haversine exacto)
    para evitar dependencias circulares con el módulo de rutas.

    Args:
        lat, lon: Coordenadas del punto a validar.
        center_lat, center_lon: Centro de la zona operativa.
        radius_km: Radio máximo en kilómetros.

    Returns:
        ValidationError si el punto está fuera del radio.
    """
    import math

    # Aproximación: 1° lat ≈ 111 km, 1° lon ≈ 111 * cos(lat) km
    dlat = abs(lat - center_lat) * 111.0
    dlon = abs(lon - center_lon) * 111.0 * math.cos(math.radians(center_lat))
    approx_dist = math.sqrt(dlat**2 + dlon**2)

    if approx_dist > radius_km:
        return ValidationError(
            "coordinates",
            f"Punto a ~{approx_dist:.0f} km del centro operativo. "
            f"Máximo permitido: {radius_km:.0f} km.",
        )
    return None


def check_duplicate_name(
    client_name: str,
    existing: Sequence[Delivery],
) -> ValidationError | None:
    """Detecta nombres de cliente duplicados (case-insensitive).

    Returns:
        ValidationError si ya existe una entrega con el mismo nombre.
    """
    normalized = client_name.strip().lower()
    for d in existing:
        if d.client_name.strip().lower() == normalized:
            return ValidationError(
                "client_name",
                f"Ya existe una entrega para '{d.client_name}' "
                f"(ID: {d.delivery_id}).",
            )
    return None


def check_duplicate_proximity(
    lat: float,
    lon: float,
    existing: Sequence[Delivery],
    threshold_km: float = 0.05,
) -> ValidationError | None:
    """Detecta puntos de entrega demasiado cercanos entre sí.

    Default: 50 metros de radio.

    Args:
        lat, lon: Coordenadas del nuevo punto.
        existing: Entregas existentes.
        threshold_km: Distancia mínima en km (default: 0.05 = 50m).

    Returns:
        ValidationError si hay una entrega existente dentro del umbral.
    """
    import math

    for d in existing:
        dlat = abs(lat - d.coordinates.latitude) * 111.0
        dlon = (
            abs(lon - d.coordinates.longitude)
            * 111.0
            * math.cos(math.radians(lat))
        )
        dist = math.sqrt(dlat**2 + dlon**2)
        if dist < threshold_km:
            return ValidationError(
                "coordinates",
                f"Muy cerca de '{d.client_name}' (~{dist * 1000:.0f}m). "
                f"¿Es un duplicado?",
            )
    return None


def validate_client_name(name: str) -> ValidationError | None:
    """Valida que el nombre del cliente no sea vacío ni solo espacios.

    Returns:
        ValidationError si el nombre es inválido.
    """
    if not name or not name.strip():
        return ValidationError(
            "client_name",
            "El nombre del cliente es obligatorio.",
        )
    return None


def validate_delivery_input(
    client_name: str,
    lat: float,
    lon: float,
    existing_deliveries: Sequence[Delivery],
    center_lat: float | None = None,
    center_lon: float | None = None,
    radius_km: float = 100.0,
) -> list[ValidationError]:
    """Ejecuta todas las validaciones sobre un nuevo punto de entrega.

    Args:
        client_name: Nombre del cliente.
        lat, lon: Coordenadas del punto.
        existing_deliveries: Entregas ya registradas.
        center_lat, center_lon: Centro de zona operativa (opcional).
        radius_km: Radio máximo de la zona operativa.

    Returns:
        Lista de errores de validación (vacía si todo es válido).
    """
    errors: list[ValidationError] = []

    # Nombre
    name_err = validate_client_name(client_name)
    if name_err:
        errors.append(name_err)

    # Coordenadas
    errors.extend(validate_coordinates(lat, lon))

    # Solo continuar con validaciones de proximidad si las coords son válidas
    if not errors:
        swap_err = check_suspicious_swap(lat, lon)
        if swap_err:
            errors.append(swap_err)

        dup_name = check_duplicate_name(client_name, existing_deliveries)
        if dup_name:
            errors.append(dup_name)

        dup_prox = check_duplicate_proximity(lat, lon, existing_deliveries)
        if dup_prox:
            errors.append(dup_prox)

        if center_lat is not None and center_lon is not None:
            bbox_err = check_bounding_box(
                lat, lon, center_lat, center_lon, radius_km
            )
            if bbox_err:
                errors.append(bbox_err)

    return errors
