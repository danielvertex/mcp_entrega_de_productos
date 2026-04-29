"""Tests de integración para RoutingService.

OSRM se mockea siempre — estos tests no dependen de la red.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from delivery_app.domain.enums import ReturnMode, RouteMethod
from delivery_app.domain.models import Coordinates, Delivery, NamedPoint
from delivery_app.services.routing_service import RoutingService


def _origin():
    return NamedPoint(
        name="Bodega",
        coordinates=Coordinates(latitude=21.86, longitude=-102.29),
    )


def _deliveries():
    return [
        Delivery(
            delivery_id="d1",
            client_name="A",
            coordinates=Coordinates(latitude=21.87, longitude=-102.28),
        ),
        Delivery(
            delivery_id="d2",
            client_name="B",
            coordinates=Coordinates(latitude=21.88, longitude=-102.27),
        ),
    ]


class TestOSRMSuccess:
    @pytest.mark.asyncio
    async def test_osrm_returns_route(self):
        mock_client = AsyncMock()
        mock_client.trip.return_value = {
            "code": "Ok",
            "trips": [{"distance": 5000, "duration": 600}],
            "waypoints": [
                {"waypoint_index": 0},  # origin
                {"waypoint_index": 1},  # d1
                {"waypoint_index": 2},  # d2
            ],
        }

        service = RoutingService(osrm_client=mock_client)
        result = await service.optimize(
            origin=_origin(),
            deliveries=_deliveries(),
            return_mode=ReturnMode.NONE,
        )

        assert result.method == RouteMethod.OSRM
        assert result.total_distance_km == 5.0
        assert result.total_duration_min == 10.0
        assert len(result.optimized_order) == 2

    @pytest.mark.asyncio
    async def test_osrm_with_return_origin(self):
        mock_client = AsyncMock()
        mock_client.trip.return_value = {
            "code": "Ok",
            "trips": [{"distance": 8000, "duration": 900}],
            "waypoints": [
                {"waypoint_index": 0},
                {"waypoint_index": 1},
                {"waypoint_index": 2},
            ],
        }

        service = RoutingService(osrm_client=mock_client)
        result = await service.optimize(
            origin=_origin(),
            deliveries=_deliveries(),
            return_mode=ReturnMode.ORIGIN,
        )

        assert result.return_info.mode == ReturnMode.ORIGIN
        assert result.return_info.point_name == "Bodega"
        # Verify OSRM was called with roundtrip=True
        mock_client.trip.assert_called_once()
        call_kwargs = mock_client.trip.call_args
        assert call_kwargs.kwargs["roundtrip"] is True

    @pytest.mark.asyncio
    async def test_bug3_osrm_roundtrip_params(self):
        """BUG-3: OSRM no acepta destination si roundtrip=True."""
        mock_client = AsyncMock()
        mock_client.trip.return_value = {
            "code": "Ok", "trips": [{"distance": 100, "duration": 10}],
            "waypoints": [{"waypoint_index": 0}]
        }
        service = RoutingService(osrm_client=mock_client)
        await service.optimize(
            origin=_origin(),
            deliveries=_deliveries(),
            return_mode=ReturnMode.ORIGIN,
        )
        # Verificar que destination es None cuando roundtrip es True
        mock_client.trip.assert_called_once()
        _, kwargs = mock_client.trip.call_args
        assert kwargs["roundtrip"] is True
        assert kwargs["destination"] is None


class TestFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_haversine(self):
        mock_client = AsyncMock()
        mock_client.trip.return_value = None  # OSRM failed

        service = RoutingService(osrm_client=mock_client)
        result = await service.optimize(
            origin=_origin(),
            deliveries=_deliveries(),
        )

        assert result.method == RouteMethod.HAVERSINE_FALLBACK
        assert result.total_distance_km > 0
        assert result.total_duration_min > 0
        assert len(result.optimized_order) == 2


class TestEmptyInput:
    @pytest.mark.asyncio
    async def test_empty_deliveries(self):
        mock_client = AsyncMock()
        service = RoutingService(osrm_client=mock_client)
        result = await service.optimize(
            origin=_origin(),
            deliveries=[],
        )
        assert result.optimized_order == []
        assert result.total_distance_km == 0.0
        mock_client.trip.assert_not_called()
