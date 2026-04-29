"""Tests para validadores de negocio."""

from delivery_app.domain.models import Coordinates, Delivery
from delivery_app.domain.validators import (
    check_bounding_box,
    check_duplicate_name,
    check_duplicate_proximity,
    check_suspicious_swap,
    validate_client_name,
    validate_coordinates,
    validate_delivery_input,
)


class TestValidateCoordinates:
    def test_valid(self):
        assert validate_coordinates(21.86, -102.29) == []

    def test_lat_too_high(self):
        errors = validate_coordinates(91.0, 0.0)
        assert len(errors) == 1
        assert "latitud" in errors[0].message.lower()

    def test_lon_too_low(self):
        errors = validate_coordinates(0.0, -181.0)
        assert len(errors) == 1
        assert "longitud" in errors[0].message.lower()

    def test_both_invalid(self):
        errors = validate_coordinates(91.0, 181.0)
        assert len(errors) == 2


class TestCheckSuspiciousSwap:
    def test_normal_coords(self):
        assert check_suspicious_swap(21.86, -102.29) is None

    def test_swapped_coords(self):
        err = check_suspicious_swap(-102.29, 21.86)
        assert err is not None
        assert "invertidas" in err.message

    def test_positive_longitude_mexico(self):
        """BUG-6: Longitud positiva es sospechosa en México."""
        err = check_suspicious_swap(21.86, 102.29)
        assert err is not None
        assert "longitud" in err.field
        assert "negativa" in err.message


class TestCheckBoundingBox:
    def test_within_radius(self):
        err = check_bounding_box(21.90, -102.30, 21.86, -102.29, 100.0)
        assert err is None

    def test_outside_radius(self):
        # ~1000km away
        err = check_bounding_box(30.0, -102.29, 21.86, -102.29, 100.0)
        assert err is not None
        assert "centro operativo" in err.message


class TestCheckDuplicateName:
    def _deliveries(self):
        return [
            Delivery(
                client_name="Tienda Norte",
                coordinates=Coordinates(latitude=0.0, longitude=0.0),
            ),
        ]

    def test_no_duplicate(self):
        err = check_duplicate_name("Tienda Sur", self._deliveries())
        assert err is None

    def test_duplicate_exact(self):
        err = check_duplicate_name("Tienda Norte", self._deliveries())
        assert err is not None

    def test_duplicate_case_insensitive(self):
        err = check_duplicate_name("tienda norte", self._deliveries())
        assert err is not None


class TestCheckDuplicateProximity:
    def _deliveries(self):
        return [
            Delivery(
                client_name="Punto A",
                coordinates=Coordinates(latitude=21.860, longitude=-102.290),
            ),
        ]

    def test_far_away(self):
        err = check_duplicate_proximity(22.0, -102.0, self._deliveries())
        assert err is None

    def test_very_close(self):
        # ~10m away
        err = check_duplicate_proximity(21.8601, -102.2901, self._deliveries())
        assert err is not None
        assert "cerca" in err.message.lower()


class TestValidateClientName:
    def test_valid(self):
        assert validate_client_name("Test") is None

    def test_empty(self):
        err = validate_client_name("")
        assert err is not None

    def test_whitespace_only(self):
        err = validate_client_name("   ")
        assert err is not None


class TestValidateDeliveryInput:
    def test_all_valid(self):
        errors = validate_delivery_input(
            "Nuevo Cliente", 21.86, -102.29, [], 21.86, -102.29, 100.0
        )
        assert errors == []

    def test_empty_name(self):
        errors = validate_delivery_input("", 21.86, -102.29, [])
        assert len(errors) >= 1

    def test_invalid_coords(self):
        errors = validate_delivery_input("Test", 91.0, 0.0, [])
        assert len(errors) >= 1

    def test_combined_errors(self):
        errors = validate_delivery_input("", 91.0, 181.0, [])
        assert len(errors) >= 3
