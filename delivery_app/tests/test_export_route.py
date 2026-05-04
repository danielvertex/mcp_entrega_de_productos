"""Tests para la tool export_route."""

from datetime import datetime

import pytest

from delivery_app.domain.enums import DeliveryStatus, ReturnMode, RouteMethod, TripStatus
from delivery_app.domain.models import Coordinates, Delivery, NamedPoint, RouteResult, Trip
from delivery_app.services.trip_service import TripService
from delivery_app.tools.history_tools import register_history_tools

class MockTripRepository:
    def __init__(self):
        self.trips = {}

    def load_archived_trip(self, trip_id: str) -> Trip | None:
        return self.trips.get(trip_id)

@pytest.fixture
def mock_trip_service():
    repo = MockTripRepository()
    # TripService expects a real repository, but duck typing is fine for load_archived_trip
    # We can pass the MockTripRepository if it has the right methods
    class FakeService:
        def load_archived_trip(self, trip_id: str):
            return repo.load_archived_trip(trip_id)
    return FakeService(), repo

class MockApp:
    def __init__(self):
        self.tools = {}
    
    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator

@pytest.fixture
def dummy_app():
    return MockApp()

@pytest.fixture
def sample_trip():
    d1 = Delivery(
        client_name="Client 1",
        coordinates=Coordinates(latitude=1.0, longitude=1.0),
    )
    d1.delivery_id = "d1"
    d1.status = DeliveryStatus.DELIVERED
    d1.completed_at = datetime.now()

    d2 = Delivery(
        client_name="Client 2",
        coordinates=Coordinates(latitude=2.0, longitude=2.0),
    )
    d2.delivery_id = "d2"
    d2.status = DeliveryStatus.PENDING

    trip = Trip(
        trip_id="trip_123",
        origin=NamedPoint(name="Base", coordinates=Coordinates(latitude=0.0, longitude=0.0)),
        deliveries=[d1, d2],
        status=TripStatus.CLOSED,
        created_at=datetime.now(),
        closed_at=datetime.now()
    )
    return trip

@pytest.fixture
def sample_trip_with_route(sample_trip):
    trip = sample_trip.model_copy()
    trip.route_plan = RouteResult(
        method=RouteMethod.OSRM,
        optimized_order=["d2", "d1"],
        total_distance_km=10.0,
        total_duration_min=15.0
    )
    trip.return_mode = ReturnMode.ORIGIN
    return trip

def test_export_full(dummy_app, mock_trip_service, sample_trip):
    service, repo = mock_trip_service
    repo.trips["trip_123"] = sample_trip
    register_history_tools(dummy_app, service) # type: ignore
    
    export_route = dummy_app.tools["export_route"]
    result = export_route(trip_id="trip_123", format="full")
    
    assert result["trip_id"] == "trip_123"
    assert result["format"] == "full"
    assert "data" in result
    assert result["data"]["trip_id"] == "trip_123"
    assert "exported_at" in result

def test_export_summary(dummy_app, mock_trip_service, sample_trip):
    service, repo = mock_trip_service
    repo.trips["trip_123"] = sample_trip
    register_history_tools(dummy_app, service) # type: ignore
    
    export_route = dummy_app.tools["export_route"]
    result = export_route(trip_id="trip_123", format="summary")
    
    assert result["format"] == "summary"
    data = result["data"]
    assert "completed" in data
    assert "pending" in data
    assert "failed" in data
    assert data["completed"] == 1
    assert data["pending"] == 1

def test_export_route_with_plan(dummy_app, mock_trip_service, sample_trip_with_route):
    service, repo = mock_trip_service
    repo.trips["trip_123"] = sample_trip_with_route
    register_history_tools(dummy_app, service) # type: ignore
    
    export_route = dummy_app.tools["export_route"]
    result = export_route(trip_id="trip_123", format="route")
    
    assert result["format"] == "route"
    data = result["data"]
    assert "stops" in data
    assert len(data["stops"]) == 2
    assert data["stops"][0]["delivery_id"] == "d2"
    assert data["stops"][1]["delivery_id"] == "d1"

def test_export_route_without_plan(dummy_app, mock_trip_service, sample_trip):
    service, repo = mock_trip_service
    repo.trips["trip_123"] = sample_trip
    register_history_tools(dummy_app, service) # type: ignore
    
    export_route = dummy_app.tools["export_route"]
    with pytest.raises(ValueError, match="Esta jornada no tiene ruta calculada"):
        export_route(trip_id="trip_123", format="route")

def test_export_deliveries(dummy_app, mock_trip_service, sample_trip):
    service, repo = mock_trip_service
    repo.trips["trip_123"] = sample_trip
    register_history_tools(dummy_app, service) # type: ignore
    
    export_route = dummy_app.tools["export_route"]
    result = export_route(trip_id="trip_123", format="deliveries")
    
    assert result["format"] == "deliveries"
    data = result["data"]
    assert data["total"] == 2
    dels = data["deliveries"]
    assert len(dels) == 2
    assert dels[0]["delivery_id"] == "d1"
    assert "completed_at" in dels[0]
    assert dels[1]["delivery_id"] == "d2"
    assert dels[1]["completed_at"] is None

def test_export_invalid_trip_id(dummy_app, mock_trip_service):
    service, repo = mock_trip_service
    register_history_tools(dummy_app, service) # type: ignore
    
    export_route = dummy_app.tools["export_route"]
    with pytest.raises(ValueError, match="no encontrada en el historial"):
        export_route(trip_id="no_existe", format="full")

def test_export_invalid_format(dummy_app, mock_trip_service, sample_trip):
    service, repo = mock_trip_service
    repo.trips["trip_123"] = sample_trip
    register_history_tools(dummy_app, service) # type: ignore
    
    export_route = dummy_app.tools["export_route"]
    with pytest.raises(ValueError, match="no válido"):
        export_route(trip_id="trip_123", format="pdf")
