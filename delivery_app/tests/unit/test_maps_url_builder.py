"""Tests para el generador de URLs de Google Maps."""

from delivery_app.infrastructure.maps_url_builder import build_gmaps_url


class TestBuildGmapsUrl:
    def test_basic_url(self):
        url = build_gmaps_url(21.86, -102.29, 21.87, -102.28)
        assert "google.com/maps/dir" in url
        assert "origin=21.86,-102.29" in url
        assert "destination=21.87,-102.28" in url
        assert "travelmode=driving" in url

    def test_custom_travel_mode(self):
        url = build_gmaps_url(0.0, 0.0, 1.0, 1.0, travel_mode="walking")
        assert "travelmode=walking" in url

    def test_negative_coords(self):
        url = build_gmaps_url(-34.6037, -58.3816, -34.5, -58.5)
        assert "origin=-34.6037,-58.3816" in url
        assert "destination=-34.5,-58.5" in url
