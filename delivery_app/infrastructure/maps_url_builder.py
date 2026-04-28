"""Generador de URLs de Google Maps Directions.

Función pura, sin estado ni dependencias externas.
"""

from __future__ import annotations


def build_gmaps_url(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    travel_mode: str = "driving",
) -> str:
    """Construye una URL de Google Maps Directions.

    Args:
        origin_lat: Latitud del punto de partida.
        origin_lon: Longitud del punto de partida.
        dest_lat: Latitud del destino.
        dest_lon: Longitud del destino.
        travel_mode: Modo de viaje (driving, walking, bicycling, transit).

    Returns:
        URL completa de Google Maps Directions.
    """
    return (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={origin_lat},{origin_lon}"
        f"&destination={dest_lat},{dest_lon}"
        f"&travelmode={travel_mode}"
    )
