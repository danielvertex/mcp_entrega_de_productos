"""Tests para el servicio de navegación."""

from delivery_app.domain.enums import DeliveryStatus, ReturnMode, RouteMethod
from delivery_app.domain.models import (
    Coordinates,
    Delivery,
    NamedPoint,
    RouteResult,
    Trip,
)
from delivery_app.domain.trip_manager import (
    add_delivery,
    change_delivery_status,
    create_trip,
    update_route_plan,
)
from delivery_app.services.navigation_service import get_next_navigation


def _origin():
    return NamedPoint(
        name="Bodega",
        coordinates=Coordinates(latitude=21.86, longitude=-102.29),
    )


def _delivery(name, lat, lon):
    return Delivery(
        client_name=name,
        coordinates=Coordinates(latitude=lat, longitude=lon),
    )


def _trip_with_deliveries():
    """Trip con 3 entregas y ruta optimizada A→B→C."""
    trip = create_trip(origin=_origin(), return_mode=ReturnMode.ORIGIN)
    dA = _delivery("A", 21.87, -102.28)
    dB = _delivery("B", 21.88, -102.27)
    dC = _delivery("C", 21.89, -102.26)
    trip = add_delivery(trip, dA)
    trip = add_delivery(trip, dB)
    trip = add_delivery(trip, dC)

    route = RouteResult(
        optimized_order=[dA.delivery_id, dB.delivery_id, dC.delivery_id],
        total_distance_km=10.0,
        total_duration_min=20.0,
        method=RouteMethod.OSRM,
    )
    trip = update_route_plan(trip, route)
    return trip, dA, dB, dC


class TestNavigationChain:
    def test_first_stop_from_origin(self):
        """Sin entregas hechas: Origen → A."""
        trip, dA, _, _ = _trip_with_deliveries()
        nav = get_next_navigation(trip)
        assert nav.has_next
        assert not nav.is_return
        assert nav.from_name == "Bodega"
        assert nav.next_stop_name == "A"
        assert "google.com/maps" in nav.url

    def test_second_stop_from_delivered(self):
        """A entregado: A → B."""
        trip, dA, dB, _ = _trip_with_deliveries()
        trip = change_delivery_status(trip, dA.delivery_id, DeliveryStatus.DELIVERED)
        nav = get_next_navigation(trip)
        assert nav.has_next
        assert not nav.is_return
        assert nav.from_name == "A"
        assert nav.next_stop_name == "B"

    def test_third_stop(self):
        """A y B entregados: B → C."""
        trip, dA, dB, dC = _trip_with_deliveries()
        trip = change_delivery_status(trip, dA.delivery_id, DeliveryStatus.DELIVERED)
        trip = change_delivery_status(trip, dB.delivery_id, DeliveryStatus.DELIVERED)
        nav = get_next_navigation(trip)
        assert nav.from_name == "B"
        assert nav.next_stop_name == "C"

    def test_all_delivered_return_to_origin(self):
        """Todos entregados + retorno al origen."""
        trip, dA, dB, dC = _trip_with_deliveries()
        trip = change_delivery_status(trip, dA.delivery_id, DeliveryStatus.DELIVERED)
        trip = change_delivery_status(trip, dB.delivery_id, DeliveryStatus.DELIVERED)
        trip = change_delivery_status(trip, dC.delivery_id, DeliveryStatus.DELIVERED)
        nav = get_next_navigation(trip)
        assert nav.has_next
        assert nav.is_return
        assert nav.next_stop_name == "Bodega"

    def test_all_delivered_no_return(self):
        """Todos entregados + sin retorno."""
        trip, dA, dB, dC = _trip_with_deliveries()
        trip = trip.model_copy(update={"return_mode": ReturnMode.NONE})
        trip = change_delivery_status(trip, dA.delivery_id, DeliveryStatus.DELIVERED)
        trip = change_delivery_status(trip, dB.delivery_id, DeliveryStatus.DELIVERED)
        trip = change_delivery_status(trip, dC.delivery_id, DeliveryStatus.DELIVERED)
        nav = get_next_navigation(trip)
        assert not nav.has_next
        assert nav.url == ""

    def test_all_delivered_custom_return(self):
        """Todos entregados + retorno personalizado."""
        rp = NamedPoint(
            name="Casa",
            coordinates=Coordinates(latitude=22.0, longitude=-102.0),
        )
        trip, dA, dB, dC = _trip_with_deliveries()
        trip = trip.model_copy(
            update={"return_mode": ReturnMode.CUSTOM, "return_point": rp}
        )
        trip = change_delivery_status(trip, dA.delivery_id, DeliveryStatus.DELIVERED)
        trip = change_delivery_status(trip, dB.delivery_id, DeliveryStatus.DELIVERED)
        trip = change_delivery_status(trip, dC.delivery_id, DeliveryStatus.DELIVERED)
        nav = get_next_navigation(trip)
        assert nav.is_return
        assert nav.next_stop_name == "Casa"

    def test_manual_override(self):
        """Override manual de ubicación."""
        trip, dA, _, _ = _trip_with_deliveries()
        nav = get_next_navigation(trip, current_lat=21.90, current_lon=-102.25)
        assert nav.from_name == "Ubicación actual"
        assert "21.9,-102.25" in nav.url

    def test_out_of_order_delivery(self):
        """Si B se entrega antes que A, navega desde B hacia A."""
        trip, dA, dB, dC = _trip_with_deliveries()
        trip = change_delivery_status(trip, dB.delivery_id, DeliveryStatus.DELIVERED)
        nav = get_next_navigation(trip)
        # El primer pendiente en el orden optimizado es A
        assert nav.next_stop_name == "A"
        # Y el from debería ser B (el único entregado)
        assert nav.from_name == "B"

    def test_navigation_from_failed_status(self):
        """BUG-2: Navegar desde un punto que falló (CANCELLED)."""
        trip, dA, dB, _ = _trip_with_deliveries()
        # Marcar A como cancelado (en lugar de entregado)
        trip = change_delivery_status(trip, dA.delivery_id, DeliveryStatus.CANCELLED)

        nav = get_next_navigation(trip)
        assert nav.has_next
        # Debe navegar DESDE A (aunque falló) hacia B
        assert nav.from_name == "A"
        assert nav.next_stop_name == "B"
