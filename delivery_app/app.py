"""MCP App para repartidor de productos de limpieza.

Define la FastMCPApp principal. Delega la lógica a la capa
de servicios y la construcción de UI a UIBuilder.
"""

from __future__ import annotations

import logging
import sys
import os

# Asegurar que el cwd esté en sys.path para que fastmcp pueda resolver 'delivery_app'
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from fastmcp import FastMCPApp

# Se declara el app de inmediato para que el AST parser de fastmcp lo encuentre sin problemas
app = FastMCPApp("DeliveryApp")

from pathlib import Path

from delivery_app.infrastructure.config import default_config
from delivery_app.infrastructure.json_repository import JsonTripRepository
from delivery_app.infrastructure.osrm_client import OSRMClient
from delivery_app.services.routing_service import RoutingService
from delivery_app.services.trip_service import TripService
from delivery_app.tools.config_tools import register_config_tools
from delivery_app.tools.delivery_tools import register_delivery_tools
from delivery_app.tools.history_tools import register_history_tools
from delivery_app.tools.route_tools import register_route_tools
from delivery_app.tools.trip_tools import register_trip_tools
from delivery_app.ui.app_builder import (
    PAGE_ADD_POINT,
    PAGE_DASHBOARD,
    PAGE_FUEL,
    PAGE_HISTORY,
    PAGE_ORIGIN,
    PAGE_RETURN,
    PAGE_SUMMARY,
    UIBuilder,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── 1. Inicialización de la Aplicación y Dependencias ─────────

# Configurar persistencia
DATA_DIR = Path("data")
repo = JsonTripRepository(DATA_DIR)

# Configurar servicios
osrm_client = OSRMClient(default_config.osrm)
routing_service = RoutingService(osrm_client, default_config)
trip_service = TripService(repo)

# ─── 2. Registro de Herramientas (Tools) ──────────────────────

register_delivery_tools(app, trip_service)
register_config_tools(app, trip_service)
register_route_tools(app, trip_service, routing_service)
register_trip_tools(app, trip_service)
register_history_tools(app, trip_service)

# ─── 3. Constructor de Interfaz Gráfica (UI) ──────────────────

ui_builder = UIBuilder(trip_service)


@app.ui()
def ui_delivery_dashboard():
    """Abre el panel principal de entregas del día."""
    return ui_builder.build_app(PAGE_DASHBOARD)


@app.ui()
def ui_add_delivery_point():
    """Abre el formulario para agregar un nuevo punto de entrega."""
    return ui_builder.build_app(PAGE_ADD_POINT)


@app.ui()
def ui_origin_settings():
    """Abre el formulario para configurar el punto de origen (bodega)."""
    return ui_builder.build_app(PAGE_ORIGIN)


@app.ui()
def ui_fuel_settings():
    """Abre el formulario de configuración de combustible."""
    return ui_builder.build_app(PAGE_FUEL)


@app.ui()
def ui_day_summary():
    """Muestra el resumen completo del día actual."""
    return ui_builder.build_app(PAGE_SUMMARY)


@app.ui()
def ui_trip_history():
    """Muestra el historial de viajes cerrados."""
    return ui_builder.build_app(PAGE_HISTORY)


@app.ui()
def ui_return_settings():
    """Abre la configuración de retorno del repartidor."""
    return ui_builder.build_app(PAGE_RETURN)
