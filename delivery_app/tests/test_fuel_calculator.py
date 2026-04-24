"""Tests para el calculador de combustible."""

import pytest

from delivery_app.services.fuel_calculator import calculate_fuel


class TestCalculateFuel:
    """Tests para calculate_fuel."""

    def test_basic_calculation(self):
        result = calculate_fuel(100.0, 10.0, 20.0)
        assert result["fuel_liters"] == 10.0
        assert result["fuel_cost"] == 200.0

    def test_zero_distance(self):
        result = calculate_fuel(0.0, 10.0, 20.0)
        assert result["fuel_liters"] == 0.0
        assert result["fuel_cost"] == 0.0

    def test_fractional_results(self):
        result = calculate_fuel(75.0, 12.0, 23.50)
        assert result["fuel_liters"] == 6.25
        assert result["fuel_cost"] == 146.88  # 6.25 * 23.50

    def test_invalid_km_per_liter(self):
        with pytest.raises(ValueError, match="rendimiento"):
            calculate_fuel(100.0, 0.0, 20.0)

    def test_negative_km_per_liter(self):
        with pytest.raises(ValueError, match="rendimiento"):
            calculate_fuel(100.0, -5.0, 20.0)

    def test_invalid_price(self):
        with pytest.raises(ValueError, match="precio"):
            calculate_fuel(100.0, 10.0, 0.0)

    def test_negative_distance(self):
        with pytest.raises(ValueError, match="distancia"):
            calculate_fuel(-10.0, 10.0, 20.0)
