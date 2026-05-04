"""Constructor de la interfaz de usuario.

Define las páginas y ensambla el PrefabApp usando el estado del TripService.
"""

from __future__ import annotations

from typing import Any

from prefab_ui.actions import SetState, ShowToast
from prefab_ui.actions.mcp import CallTool
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge,
    Button,
    Card,
    CardContent,
    CardFooter,
    CardHeader,
    Column,
    Form,
    Grid,
    Heading,
    Page,
    Pages,
    Row,
    Separator,
    Text,
)
from prefab_ui.components.control_flow import ForEach, If
from prefab_ui.rx import RESULT

from delivery_app.schemas import (
    DeliveryPointInput,
    DeliveryStatusInput,
    FuelConfigInput,
    OriginInput,
    ReturnPointInput,
)
from delivery_app.services.trip_service import TripService
from delivery_app.ui.components import back_button, nav_button
from delivery_app.ui.state_mapper import map_trip_to_state

# Nombres de herramientas (deben coincidir con el nombre de la función en Python)
TOOL_ADD_POINT = "add_delivery_point"
TOOL_REMOVE_POINT = "remove_delivery_point"
TOOL_MARK_STATUS = "mark_delivery_status"
TOOL_OPTIMIZE = "optimize_route"
TOOL_ORIGIN = "update_origin"
TOOL_RETURN = "update_return_config"
TOOL_FUEL = "update_fuel_config"
TOOL_CLOSE_DAY = "close_day"
TOOL_EXPORT = "export_route"

PAGE_DASHBOARD = "dashboard"
PAGE_ADD_POINT = "add_point"
PAGE_ORIGIN = "origin"
PAGE_FUEL = "fuel"
PAGE_SUMMARY = "summary"
PAGE_HISTORY = "history"
PAGE_RETURN = "return_config"


class UIBuilder:
    def __init__(self, trip_service: TripService) -> None:
        self._service = trip_service

    def build_app(self, initial_page: str = PAGE_DASHBOARD) -> PrefabApp:
        trip = self._service.load_active_trip()
        past_trips = self._service.list_archived_trips()
        state = map_trip_to_state(trip, past_trips)
        state["page"] = initial_page

        if initial_page == PAGE_SUMMARY and trip:
            state["summary"] = self._service.get_summary(trip)

        with Column(gap=6, css_class="p-6") as view:
            with Pages(name="page", value=initial_page):
                with Page(PAGE_DASHBOARD, value=PAGE_DASHBOARD):
                    self._build_dashboard()
                with Page(PAGE_ADD_POINT, value=PAGE_ADD_POINT):
                    self._build_add_point()
                with Page(PAGE_ORIGIN, value=PAGE_ORIGIN):
                    self._build_origin()
                with Page(PAGE_FUEL, value=PAGE_FUEL):
                    self._build_fuel()
                with Page(PAGE_SUMMARY, value=PAGE_SUMMARY):
                    self._build_summary()
                with Page(PAGE_HISTORY, value=PAGE_HISTORY):
                    self._build_history()
                with Page(PAGE_RETURN, value=PAGE_RETURN):
                    self._build_return()

        return PrefabApp(view=view, state=state)

    def _build_dashboard(self) -> None:
        Heading("🚚 Mis Entregas del Día")

        with Row(gap=2, align="center"):
            Badge("{{ _pending }} pendientes", variant="secondary")
            Badge("{{ _completed }} completados", variant="success")

        with If("origin.name"):
            Text("📍 Origen: {{ origin.name }}")

        # Lista de entregas
        with ForEach("delivery_points") as point:
            with Card():
                with CardHeader():
                    with Row(gap=2, align="center"):
                        Text(point.client_name, css_class="font-semibold")
                        with If(f"{point.status.key} == 'delivered'"):
                            Badge("Entregado", variant="success")
                        with If(f"{point.status.key} == 'pending'"):
                            Badge("Pendiente", variant="secondary")
                        with If(f"{point.status.key} == 'not_found'"):
                            Badge("No encontrado", variant="destructive")
                with CardFooter():
                    with Row(gap=2):
                        Button(
                            "✅ Entregado",
                            size="sm",
                            on_click=CallTool(
                                TOOL_MARK_STATUS,
                                arguments={"delivery_id": point.id, "status": "delivered"},
                                on_success=[
                                    ShowToast("{{ $result.message }}", variant="success"),
                                    SetState("delivery_points", "{{ $result.points }}"),
                                    SetState("gmaps_link", "{{ $result.gmaps_link }}"),
                                    SetState("_pending", "{{ $result._pending }}"),
                                    SetState("_completed", "{{ $result._completed }}"),
                                    SetState("summary", "{{ $result.summary }}"),
                                ],
                            ),
                        )
                        Button(
                            "❌ Fallido",
                            size="sm",
                            variant="destructive",
                            on_click=CallTool(
                                TOOL_MARK_STATUS,
                                arguments={"delivery_id": point.id, "status": "not_found"},
                                on_success=[
                                    ShowToast("{{ $result.message }}", variant="error"),
                                    SetState("delivery_points", "{{ $result.points }}"),
                                    SetState("gmaps_link", "{{ $result.gmaps_link }}"),
                                    SetState("_pending", "{{ $result._pending }}"),
                                    SetState("_completed", "{{ $result._completed }}"),
                                    SetState("summary", "{{ $result.summary }}"),
                                ],
                            ),
                        )
                        Button(
                            "🗑 Eliminar",
                            size="sm",
                            variant="outline",
                            on_click=CallTool(
                                TOOL_REMOVE_POINT,
                                arguments={"delivery_id": point.id},
                                on_success=[
                                    ShowToast("{{ $result.message }}", variant="success"),
                                    SetState("delivery_points", "{{ $result.points }}"),
                                    SetState("gmaps_link", "{{ $result.gmaps_link }}"),
                                    SetState("_pending", "{{ $result._pending }}"),
                                    SetState("_completed", "{{ $result._completed }}"),
                                    SetState("summary", "{{ $result.summary }}"),
                                ],
                            ),
                        )

        with If("gmaps_link.has_next"):
            Separator()
            Heading("🧭 Ir al Siguiente Punto", level=3)
            with Card():
                with CardContent():
                    Text("📍 Desde: {{ gmaps_link.from_name }}", css_class="text-sm")
                    with If("gmaps_link.is_return"):
                        Text("🏠 Hacia: {{ gmaps_link.next_stop.client_name }} (retorno)", css_class="text-sm font-semibold text-green-600")
                    with If("!gmaps_link.is_return"):
                        Text("➡ Hacia: {{ gmaps_link.next_stop.client_name }}", css_class="text-sm font-semibold")
            Text("URL del Mapa: {{ gmaps_link.url }}", css_class="text-blue-500 underline text-sm break-all")

        # Ruta Optimizada
        with If("optimized_route.total_distance_km > 0"):
            Separator()
            Heading("🗺 Ruta Optimizada", level=3)
            with Row(gap=2):
                Badge("{{ optimized_route.total_distance_km }} km", variant="outline")
                Badge("{{ optimized_route.total_duration_min }} min", variant="outline")
                Badge("Método: {{ optimized_route.method }}", variant="secondary")

            with If("optimized_route.return_info.mode == 'origin'"):
                Text("🔄 Regreso al origen: {{ optimized_route.return_info.point_name }}", css_class="text-sm text-green-600")
            with If("optimized_route.return_info.mode == 'custom'"):
                Text("🔄 Regreso a: {{ optimized_route.return_info.point_name }}", css_class="text-sm text-blue-600")
            with If("optimized_route.return_info.mode == 'none'"):
                Text("↗ Ruta abierta (sin regreso)", css_class="text-sm text-muted-foreground")

            with ForEach("optimized_route.optimized_order") as stop:
                with Row(gap=2, align="center"):
                    Badge("{{ $index + 1 }}", variant="default")
                    Text(stop.id) # Para mostrar el nombre necesitamos lookup, el array solo tiene ids.
                    # Asumiremos que el frontend no necesita el nombre aquí o que refactorizaremos esto más adelante

        Separator()

        with Grid(columns=2, gap=3):
            nav_button("➕ Agregar Punto", PAGE_ADD_POINT)
            Button(
                "🗺 Optimizar Ruta",
                on_click=CallTool(
                    TOOL_OPTIMIZE,
                    on_success=ShowToast(RESULT, variant="success"),
                    on_error=ShowToast("{{ $error }}", variant="error"),
                ),
            )
            nav_button("📍 Punto de Origen", PAGE_ORIGIN, variant="outline")
            nav_button("⛽ Combustible", PAGE_FUEL, variant="outline")
            nav_button("🔄 Configurar Retorno", PAGE_RETURN, variant="outline")
            nav_button("📊 Resumen", PAGE_SUMMARY, variant="outline")
            nav_button("📂 Historial", PAGE_HISTORY, variant="outline")

        Separator()
        Button(
            "📦 Cerrar Día",
            variant="destructive",
            css_class="w-full",
            on_click=CallTool(
                TOOL_CLOSE_DAY,
                on_success=[
                    ShowToast("{{ $result.message }}", variant="success"),
                    SetState("delivery_points", "{{ $result.state.delivery_points }}"),
                    SetState("origin", "{{ $result.state.origin }}"),
                    SetState("summary", "{{ $result.state.summary }}"),
                    SetState("_pending", "{{ $result.state._pending }}"),
                    SetState("_completed", "{{ $result.state._completed }}"),
                    SetState("gmaps_link", "{{ $result.state.gmaps_link }}"),
                    SetState("optimized_route", "{{ $result.state.optimized_route }}"),
                    SetState("past_trips", "{{ $result.state.past_trips }}"),
                ],
                on_error=ShowToast("{{ $error }}", variant="error"),
            ),
        )

    def _build_add_point(self) -> None:
        Heading("➕ Nuevo Punto")
        Form.from_model(
            DeliveryPointInput,
            submit_label="Agregar",
            on_submit=CallTool(
                TOOL_ADD_POINT,
                arguments={"client_name": "{{ client_name }}", "latitude": "{{ latitude }}", "longitude": "{{ longitude }}"},
                on_success=[
                    ShowToast("{{ $result.message }}", variant="success"),
                    SetState("delivery_points", "{{ $result.points }}"),
                    SetState("gmaps_link", "{{ $result.gmaps_link }}"),
                    SetState("_pending", "{{ $result._pending }}"),
                    SetState("_completed", "{{ $result._completed }}"),
                    SetState("summary", "{{ $result.summary }}"),
                    SetState("page", PAGE_DASHBOARD),
                ],
                on_error=ShowToast("{{ $error }}", variant="error")
            ),
        )
        back_button()

    def _build_origin(self) -> None:
        Heading("📍 Origen")
        with If("origin.name"):
            Text("Actual: {{ origin.name }} ({{ origin.latitude }}, {{ origin.longitude }})")
        Form.from_model(
            OriginInput,
            submit_label="Guardar",
            on_submit=CallTool(
                TOOL_ORIGIN,
                arguments={"name": "{{ name }}", "latitude": "{{ latitude }}", "longitude": "{{ longitude }}"},
                on_success=[
                    ShowToast("{{ $result.message }}", variant="success"),
                    SetState("origin", "{{ $result.origin }}"),
                    SetState("delivery_points", "{{ $result.delivery_points }}"),
                    SetState("gmaps_link", "{{ $result.gmaps_link }}"),
                    SetState("_pending", "{{ $result._pending }}"),
                    SetState("_completed", "{{ $result._completed }}"),
                    SetState("summary", "{{ $result.summary }}"),
                    SetState("page", PAGE_DASHBOARD),
                ],
                on_error=ShowToast("{{ $error }}", variant="error")
            ),
        )
        back_button()

    def _build_fuel(self) -> None:
        Heading("⛽ Combustible")
        with If("fuel_config.km_per_liter > 0"):
            Text("Actual: {{ fuel_config.km_per_liter }} km/l a ${{ fuel_config.price_per_liter }}")
        Form.from_model(
            FuelConfigInput,
            submit_label="Guardar",
            on_submit=CallTool(
                TOOL_FUEL,
                arguments={"km_per_liter": "{{ km_per_liter }}", "price_per_liter": "{{ price_per_liter }}"},
                on_success=[
                    ShowToast("{{ $result.message }}", variant="success"),
                    SetState("fuel_config", "{{ $result.fuel_config }}"),
                    SetState("summary", "{{ $result.summary }}"),
                    SetState("page", PAGE_DASHBOARD),
                ],
                on_error=ShowToast("{{ $error }}", variant="error")
            ),
        )
        back_button()

    def _build_summary(self) -> None:
        Heading("📊 Resumen del Día")
        with Grid(columns=2, gap=4):
            with Card():
                with CardContent():
                    Text("Completados")
                    Text("{{ summary.completed }}", css_class="text-2xl font-bold")
            with Card():
                with CardContent():
                    Text("Pendientes")
                    Text("{{ summary.pending }}", css_class="text-2xl font-bold")
            with Card():
                with CardContent():
                    Text("KM")
                    Text("{{ summary.planned_km }}", css_class="text-2xl font-bold")
            with Card():
                with CardContent():
                    Text("Costo")
                    Text("${{ summary.estimated_fuel_cost }}", css_class="text-2xl font-bold")
        back_button()

    def _build_history(self) -> None:
        Heading("📂 Historial")
        with If("past_trips.length == 0"):
            Text("No hay viajes registrados.")
        with ForEach("past_trips") as trip:
            with Card():
                with CardHeader():
                    with Row(gap=2, align="center"):
                        Text("📅")
                        Text(trip.trip_date)
                with CardContent():
                    Heading(trip.display_title, level=4, css_class="mb-2")
                    with Row(gap=2):
                        Badge(f"{trip.completed} entregas", variant="success")
                        Badge(f"${trip.estimated_fuel_cost}", variant="outline")
                with CardFooter():
                    Button(
                        "📥 Exportar",
                        size="sm",
                        variant="outline",
                        on_click=CallTool(
                            TOOL_EXPORT,
                            arguments={"trip_id": trip.trip_id, "format": "full"},
                            on_success=ShowToast("Guardado en data/exports/", variant="success"),
                            on_error=ShowToast("{{ $error }}", variant="error")
                        )
                    )
        back_button()

    def _build_return(self) -> None:
        Heading("🔄 Retorno")
        with Row(gap=2):
            Button("🏠 Al Origen", on_click=CallTool(TOOL_RETURN, arguments={"mode": "origin"},                 on_success=[
                    ShowToast("{{ $result.message }}", variant="success"),
                    SetState("return_config", "{{ $result.return_config }}"),
                    SetState("gmaps_link", "{{ $result.gmaps_link }}"),
                ]))
            Button("↗ Sin Regreso", variant="outline", on_click=CallTool(TOOL_RETURN, arguments={"mode": "none"},                 on_success=[
                    ShowToast("{{ $result.message }}", variant="success"),
                    SetState("return_config", "{{ $result.return_config }}"),
                    SetState("gmaps_link", "{{ $result.gmaps_link }}"),
                ]))
        Separator()
        Form.from_model(
            ReturnPointInput,
            submit_label="Punto Personalizado",
            on_submit=CallTool(
                TOOL_RETURN,
                arguments={"mode": "custom", "custom_name": "{{ name }}", "custom_lat": "{{ latitude }}", "custom_lon": "{{ longitude }}"},
                on_success=[
                    ShowToast("{{ $result.message }}", variant="success"),
                    SetState("return_config", "{{ $result.return_config }}"),
                    SetState("gmaps_link", "{{ $result.gmaps_link }}"),
                ],
            ),
        )
        back_button()
