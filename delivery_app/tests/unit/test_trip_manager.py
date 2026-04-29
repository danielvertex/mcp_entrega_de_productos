"""Tests para TripManager — lógica pura de negocio."""

import pytest

from delivery_app.domain.enums import DeliveryStatus, ReturnMode, RouteMethod, TripStatus
from delivery_app.domain.models import (
    Coordinates,
    Delivery,
    FuelConfig,
    NamedPoint,
    RouteResult,
    Trip,
)
from delivery_app.domain.trip_manager import (
    add_delivery,
    change_delivery_status,
    close_day,
    create_trip,
    get_completed_deliveries,
    get_failed_deliveries,
    get_pending_deliveries,
    get_summary,
    remove_delivery,
    update_route_plan,
)


def _origin():
    return NamedPoint(
        name="Bodega",
        coordinates=Coordinates(latitude=21.86, longitude=-102.29),
    )


def _delivery(name="Cliente A"):
    return Delivery(
        client_name=name,
        coordinates=Coordinates(latitude=21.87, longitude=-102.28),
    )


class TestCreateTrip:
    def test_creates_active_trip(self):
        trip = create_trip(origin=_origin())
        assert trip.status == TripStatus.ACTIVE
        assert trip.trip_id
        assert trip.origin.name == "Bodega"

    def test_with_fuel_config(self):
        fc = FuelConfig(km_per_liter=12.0, fuel_price=23.50)
        trip = create_trip(origin=_origin(), fuel_config=fc)
        assert trip.fuel_config is not None
        assert trip.fuel_config.km_per_liter == 12.0

    def test_with_custom_return(self):
        rp = NamedPoint(
            name="Casa",
            coordinates=Coordinates(latitude=22.0, longitude=-102.0),
        )
        trip = create_trip(
            origin=_origin(),
            return_mode=ReturnMode.CUSTOM,
            return_point=rp,
        )
        assert trip.return_mode == ReturnMode.CUSTOM
        assert trip.return_point.name == "Casa"


class TestAddDelivery:
    def test_adds_delivery(self):
        trip = create_trip(origin=_origin())
        d = _delivery()
        updated = add_delivery(trip, d)
        assert len(updated.deliveries) == 1
        assert updated.deliveries[0].client_name == "Cliente A"

    def test_preserves_existing(self):
        trip = create_trip(origin=_origin())
        d1 = _delivery("A")
        d2 = _delivery("B")
        trip = add_delivery(trip, d1)
        trip = add_delivery(trip, d2)
        assert len(trip.deliveries) == 2

    def test_rejects_on_closed_trip(self):
        trip = create_trip(origin=_origin())
        trip = close_day(trip)
        with pytest.raises(ValueError, match="cerrada"):
            add_delivery(trip, _delivery())


class TestRemoveDelivery:
    def test_removes_delivery(self):
        trip = create_trip(origin=_origin())
        d = _delivery()
        trip = add_delivery(trip, d)
        trip = remove_delivery(trip, d.delivery_id)
        assert len(trip.deliveries) == 0

    def test_raises_if_not_found(self):
        trip = create_trip(origin=_origin())
        with pytest.raises(ValueError, match="no encontrada"):
            remove_delivery(trip, "nonexistent-id")


class TestChangeDeliveryStatus:
    def test_mark_delivered(self):
        trip = create_trip(origin=_origin())
        d = _delivery()
        trip = add_delivery(trip, d)
        trip = change_delivery_status(trip, d.delivery_id, DeliveryStatus.DELIVERED)
        assert trip.deliveries[0].status == DeliveryStatus.DELIVERED
        assert trip.deliveries[0].completed_at is not None

    def test_mark_with_note(self):
        trip = create_trip(origin=_origin())
        d = _delivery()
        trip = add_delivery(trip, d)
        trip = change_delivery_status(
            trip, d.delivery_id, DeliveryStatus.REJECTED,
            note="Cerrado", reason="Negocio cerrado",
        )
        assert trip.deliveries[0].note == "Cerrado"
        assert trip.deliveries[0].reason == "Negocio cerrado"

    def test_revert_to_pending(self):
        trip = create_trip(origin=_origin())
        d = _delivery()
        trip = add_delivery(trip, d)
        trip = change_delivery_status(trip, d.delivery_id, DeliveryStatus.DELIVERED)
        trip = change_delivery_status(trip, d.delivery_id, DeliveryStatus.PENDING)
        assert trip.deliveries[0].status == DeliveryStatus.PENDING
        assert trip.deliveries[0].completed_at is None

    def test_updates_current_location_on_delivered(self):
        trip = create_trip(origin=_origin())
        d = _delivery()
        trip = add_delivery(trip, d)
        trip = change_delivery_status(trip, d.delivery_id, DeliveryStatus.DELIVERED)
        assert trip.current_location is not None
        assert trip.current_location.latitude == d.coordinates.latitude

    def test_updates_current_location_on_failed_but_visited(self):
        """BUG-4: Actualizar ubicación también si falló (pero se visitó)."""
        trip = create_trip(origin=_origin())
        d = _delivery()
        trip = add_delivery(trip, d)
        # Si se cancela, se asume que el conductor llegó al punto o estuvo cerca
        trip = change_delivery_status(trip, d.delivery_id, DeliveryStatus.CANCELLED)
        assert trip.current_location is not None
        assert trip.current_location.latitude == d.coordinates.latitude

    def test_all_statuses_accepted(self):
        """Todos los DeliveryStatus deben ser asignables."""
        trip = create_trip(origin=_origin())
        for status in DeliveryStatus:
            d = _delivery(f"Test {status.value}")
            trip_tmp = add_delivery(trip, d)
            result = change_delivery_status(trip_tmp, d.delivery_id, status)
            assert result.deliveries[-1].status == status


class TestCloseDay:
    def test_closes_active_trip(self):
        trip = create_trip(origin=_origin())
        closed = close_day(trip)
        assert closed.status == TripStatus.CLOSED
        assert closed.closed_at is not None

    def test_idempotent(self):
        """Cerrar un trip ya cerrado retorna el mismo trip."""
        trip = create_trip(origin=_origin())
        closed1 = close_day(trip)
        closed2 = close_day(closed1)
        assert closed1.closed_at == closed2.closed_at
        assert closed1.trip_id == closed2.trip_id

    def test_rejects_modifications_after_close(self):
        trip = create_trip(origin=_origin())
        closed = close_day(trip)
        with pytest.raises(ValueError):
            add_delivery(closed, _delivery())


class TestUpdateRoutePlan:
    def test_updates_route_and_metrics(self):
        fc = FuelConfig(km_per_liter=10.0, fuel_price=20.0)
        trip = create_trip(origin=_origin(), fuel_config=fc)
        route = RouteResult(
            optimized_order=["id1"],
            total_distance_km=50.0,
            total_duration_min=75.0,
            method=RouteMethod.OSRM,
        )
        updated = update_route_plan(trip, route)
        assert updated.route_plan is not None
        assert updated.metrics.planned_km == 50.0
        assert updated.metrics.estimated_fuel_liters == 5.0
        assert updated.metrics.estimated_fuel_cost == 100.0

    def test_no_fuel_without_config(self):
        trip = create_trip(origin=_origin())
        route = RouteResult(
            optimized_order=["id1"],
            total_distance_km=50.0,
            total_duration_min=75.0,
        )
        updated = update_route_plan(trip, route)
        assert updated.metrics.estimated_fuel_liters == 0.0


class TestHelpers:
    def test_get_pending(self):
        trip = create_trip(origin=_origin())
        d1 = _delivery("A")
        d2 = _delivery("B")
        trip = add_delivery(trip, d1)
        trip = add_delivery(trip, d2)
        trip = change_delivery_status(trip, d1.delivery_id, DeliveryStatus.DELIVERED)
        assert len(get_pending_deliveries(trip)) == 1
        assert len(get_completed_deliveries(trip)) == 1

    def test_get_failed(self):
        trip = create_trip(origin=_origin())
        d = _delivery()
        trip = add_delivery(trip, d)
        trip = change_delivery_status(trip, d.delivery_id, DeliveryStatus.REJECTED)
        assert len(get_failed_deliveries(trip)) == 1

    def test_get_summary(self):
        trip = create_trip(origin=_origin())
        summary = get_summary(trip)
        assert summary["total"] == 0
        assert summary["trip_id"] == trip.trip_id

    def test_summary_consistency_with_rescheduled(self):
        """BUG-5: El resumen debe ser consistente con reprogramados."""
        trip = create_trip(origin=_origin())
        trip = add_delivery(trip, _delivery("A"))
        trip = add_delivery(trip, _delivery("B"))

        # Uno entregado, uno reprogramado
        trip = change_delivery_status(trip, trip.deliveries[0].delivery_id, DeliveryStatus.DELIVERED)
        trip = change_delivery_status(trip, trip.deliveries[1].delivery_id, DeliveryStatus.RESCHEDULED)

        summary = get_summary(trip)
        assert summary["total"] == 2
        assert summary["completed"] == 1
        assert summary["rescheduled"] == 1
        assert summary["pending"] == 0
        assert summary["failed"] == 0
        # Invariante: total = comp + pend + failed + resched
        assert summary["total"] == summary["completed"] + summary["pending"] + summary["failed"] + summary["rescheduled"]
