"""Tests para modelos Pydantic del dominio."""

import pytest
from pydantic import ValidationError

from delivery_app.domain.models import (
    Coordinates,
    Delivery,
    FuelConfig,
    Metrics,
    NamedPoint,
    ReturnInfo,
    RouteResult,
    Trip,
)
from delivery_app.domain.enums import DeliveryStatus, ReturnMode, TripStatus


class TestCoordinates:
    def test_valid(self):
        c = Coordinates(latitude=21.86, longitude=-102.29)
        assert c.latitude == 21.86
        assert c.longitude == -102.29

    def test_lat_out_of_range_high(self):
        with pytest.raises(ValidationError):
            Coordinates(latitude=91.0, longitude=0.0)

    def test_lat_out_of_range_low(self):
        with pytest.raises(ValidationError):
            Coordinates(latitude=-91.0, longitude=0.0)

    def test_lon_out_of_range_high(self):
        with pytest.raises(ValidationError):
            Coordinates(latitude=0.0, longitude=181.0)

    def test_lon_out_of_range_low(self):
        with pytest.raises(ValidationError):
            Coordinates(latitude=0.0, longitude=-181.0)

    def test_boundary_values(self):
        c = Coordinates(latitude=90.0, longitude=180.0)
        assert c.latitude == 90.0
        c2 = Coordinates(latitude=-90.0, longitude=-180.0)
        assert c2.latitude == -90.0


class TestNamedPoint:
    def test_valid(self):
        np = NamedPoint(
            name="Bodega",
            coordinates=Coordinates(latitude=21.0, longitude=-102.0),
        )
        assert np.name == "Bodega"

    def test_empty_name(self):
        with pytest.raises(ValidationError):
            NamedPoint(
                name="",
                coordinates=Coordinates(latitude=0.0, longitude=0.0),
            )


class TestDelivery:
    def test_auto_id(self):
        d = Delivery(
            client_name="Test",
            coordinates=Coordinates(latitude=0.0, longitude=0.0),
        )
        assert d.delivery_id  # no vacío
        assert d.status == DeliveryStatus.PENDING

    def test_auto_timestamps(self):
        d = Delivery(
            client_name="Test",
            coordinates=Coordinates(latitude=0.0, longitude=0.0),
        )
        assert d.created_at is not None
        assert d.updated_at is not None
        assert d.completed_at is None

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            Delivery(
                client_name="",
                coordinates=Coordinates(latitude=0.0, longitude=0.0),
            )

    def test_whitespace_name_rejected(self):
        with pytest.raises(ValidationError):
            Delivery(
                client_name="   ",
                coordinates=Coordinates(latitude=0.0, longitude=0.0),
            )

    def test_name_stripped(self):
        d = Delivery(
            client_name="  Tienda Norte  ",
            coordinates=Coordinates(latitude=0.0, longitude=0.0),
        )
        assert d.client_name == "Tienda Norte"

    def test_with_note_and_reason(self):
        d = Delivery(
            client_name="Test",
            coordinates=Coordinates(latitude=0.0, longitude=0.0),
            note="Cerrado al llegar",
            reason="No encontrado",
        )
        assert d.note == "Cerrado al llegar"
        assert d.reason == "No encontrado"


class TestFuelConfig:
    def test_valid(self):
        fc = FuelConfig(km_per_liter=12.5, fuel_price=23.50)
        assert fc.km_per_liter == 12.5

    def test_zero_km_rejected(self):
        with pytest.raises(ValidationError):
            FuelConfig(km_per_liter=0.0, fuel_price=20.0)

    def test_negative_km_rejected(self):
        with pytest.raises(ValidationError):
            FuelConfig(km_per_liter=-5.0, fuel_price=20.0)

    def test_negative_price_rejected(self):
        with pytest.raises(ValidationError):
            FuelConfig(km_per_liter=10.0, fuel_price=-1.0)

    def test_zero_price_allowed(self):
        fc = FuelConfig(km_per_liter=10.0, fuel_price=0.0)
        assert fc.fuel_price == 0.0


class TestTrip:
    def _make_origin(self):
        return NamedPoint(
            name="Bodega",
            coordinates=Coordinates(latitude=21.86, longitude=-102.29),
        )

    def test_auto_trip_id(self):
        t = Trip(origin=self._make_origin())
        assert t.trip_id
        assert t.status == TripStatus.ACTIVE

    def test_auto_created_at(self):
        t = Trip(origin=self._make_origin())
        assert t.created_at is not None
        assert t.closed_at is None

    def test_default_return_mode(self):
        t = Trip(origin=self._make_origin())
        assert t.return_mode == ReturnMode.ORIGIN

    def test_empty_deliveries(self):
        t = Trip(origin=self._make_origin())
        assert t.deliveries == []

    def test_serialization_roundtrip(self):
        t = Trip(origin=self._make_origin())
        json_str = t.model_dump_json()
        t2 = Trip.model_validate_json(json_str)
        assert t2.trip_id == t.trip_id
        assert t2.origin.name == "Bodega"
