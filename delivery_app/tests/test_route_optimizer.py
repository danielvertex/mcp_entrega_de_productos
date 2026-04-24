"""Tests para el optimizador de rutas."""

import math

import pytest

from delivery_app.services.route_optimizer import (
    HAVERSINE_CORRECTION,
    haversine,
    _nearest_neighbor,
)


class TestHaversine:
    """Tests para la función haversine."""

    def test_same_point(self):
        """Distancia a sí mismo debe ser 0."""
        assert haversine(20.0, -103.0, 20.0, -103.0) == 0.0

    def test_known_distance(self):
        """CDMX a Guadalajara ~468 km."""
        dist = haversine(19.4326, -99.1332, 20.6597, -103.3496)
        assert 460 < dist < 480

    def test_equator_one_degree(self):
        """Un grado en el ecuador ≈ 111 km."""
        dist = haversine(0.0, 0.0, 0.0, 1.0)
        assert 110 < dist < 113

    def test_symmetry(self):
        """haversine(A, B) == haversine(B, A)."""
        d1 = haversine(19.0, -99.0, 20.0, -103.0)
        d2 = haversine(20.0, -103.0, 19.0, -99.0)
        assert math.isclose(d1, d2, rel_tol=1e-9)


class TestNearestNeighbor:
    """Tests para el algoritmo nearest-neighbor."""

    def test_empty_points(self):
        origin = {"latitude": 20.0, "longitude": -103.0}
        ordered, dist = _nearest_neighbor(origin, [])
        assert ordered == []
        assert dist == 0.0

    def test_single_point(self):
        origin = {"latitude": 20.0, "longitude": -103.0}
        points = [{"latitude": 20.1, "longitude": -103.1, "client_name": "A"}]
        ordered, dist = _nearest_neighbor(origin, points)
        assert len(ordered) == 1
        assert dist > 0

    def test_ordering(self):
        """Los puntos deben ordenarse por cercanía al origen."""
        origin = {"latitude": 0.0, "longitude": 0.0}
        points = [
            {"latitude": 3.0, "longitude": 0.0, "client_name": "Lejos"},
            {"latitude": 1.0, "longitude": 0.0, "client_name": "Cerca"},
            {"latitude": 2.0, "longitude": 0.0, "client_name": "Medio"},
        ]
        ordered, dist = _nearest_neighbor(origin, points)
        assert ordered[0]["client_name"] == "Cerca"
        assert ordered[1]["client_name"] == "Medio"
        assert ordered[2]["client_name"] == "Lejos"

    def test_correction_factor(self):
        """La distancia debe incluir el factor de corrección 1.3x."""
        origin = {"latitude": 0.0, "longitude": 0.0}
        points = [{"latitude": 1.0, "longitude": 0.0, "client_name": "A"}]
        _, dist = _nearest_neighbor(origin, points)

        raw_dist = haversine(0.0, 0.0, 1.0, 0.0)
        expected = round(raw_dist * HAVERSINE_CORRECTION, 2)
        assert dist == expected
