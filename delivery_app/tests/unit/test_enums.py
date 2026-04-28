"""Tests para enums del dominio."""

from delivery_app.domain.enums import (
    DeliveryStatus,
    ReturnMode,
    RouteMethod,
    TripStatus,
)


class TestDeliveryStatus:
    def test_has_six_values(self):
        assert len(DeliveryStatus) == 6

    def test_values(self):
        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.DELIVERED.value == "delivered"
        assert DeliveryStatus.NOT_FOUND.value == "not_found"
        assert DeliveryStatus.RESCHEDULED.value == "rescheduled"
        assert DeliveryStatus.CANCELLED.value == "cancelled"
        assert DeliveryStatus.REJECTED.value == "rejected"

    def test_str_serialization(self):
        """Los enums str+Enum se serializan como string en JSON."""
        assert str(DeliveryStatus.PENDING) == "DeliveryStatus.PENDING"
        assert DeliveryStatus.PENDING == "pending"


class TestReturnMode:
    def test_values(self):
        assert ReturnMode.ORIGIN.value == "origin"
        assert ReturnMode.CUSTOM.value == "custom"
        assert ReturnMode.NONE.value == "none"


class TestTripStatus:
    def test_values(self):
        assert TripStatus.ACTIVE.value == "active"
        assert TripStatus.CLOSED.value == "closed"


class TestRouteMethod:
    def test_values(self):
        assert RouteMethod.OSRM.value == "osrm"
        assert RouteMethod.HAVERSINE_FALLBACK.value == "haversine_fallback"
