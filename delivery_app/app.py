"""MCP App para repartidor de productos de limpieza.

Define la FastMCPApp con 6 @app.ui (entry points visibles al modelo)
y 10 @app.tool (backend tools con visibility=app).

# prefab-ui pinned: prefab-ui==0.19.1
"""

from __future__ import annotations

import uuid
from typing import Any

from prefab_ui.actions import SetState, ShowToast  # noqa: F401
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
    Row,
    Separator,
    Text,
)
from prefab_ui.components.control_flow import ForEach, If
from prefab_ui.rx import RESULT

from fastmcp import FastMCPApp

from .schemas import DeliveryPointInput, FuelConfigInput, OriginInput
from .services import fuel_calculator, persistence
from .services.route_optimizer import optimize_route as _optimize_route

app = FastMCPApp("DeliveryApp")

# ─── Estado global en memoria (cargado desde JSON al inicio) ──────────
_state: dict[str, Any] = persistence.load_state()


def _get_state() -> dict[str, Any]:
    """Retorna una copia del estado actual."""
    return dict(_state)


def _save() -> None:
    """Persiste el estado actual en JSON."""
    persistence.save_state(_state)


# ═══════════════════════════════════════════════════════════════════════
# @app.tool — Backend tools (visibility=app, invisibles al modelo)
# ═══════════════════════════════════════════════════════════════════════


@app.tool()
def add_point(client_name: str, latitude: float, longitude: float) -> list[dict]:
    """Agrega un nuevo punto de entrega a la ruta del día.

    Usa esta tool cuando el repartidor llene el formulario
    de nuevo punto de entrega.

    Args:
        client_name: Nombre del negocio o persona.
        latitude: Coordenada de latitud (-90 a 90).
        longitude: Coordenada de longitud (-180 a 180).

    Returns:
        Lista completa actualizada de puntos de entrega.
    """
    point = {
        "id": str(uuid.uuid4()),
        "client_name": client_name,
        "latitude": latitude,
        "longitude": longitude,
        "status": "pending",
    }
    _state["delivery_points"].append(point)
    _save()
    return list(_state["delivery_points"])


@app.tool()
def remove_point(point_id: str) -> list[dict]:
    """Elimina un punto de entrega de la ruta.

    Args:
        point_id: ID del punto a eliminar.

    Returns:
        Lista actualizada sin el punto eliminado.
    """
    _state["delivery_points"] = [
        p for p in _state["delivery_points"] if p["id"] != point_id
    ]
    _save()
    return list(_state["delivery_points"])


@app.tool()
def mark_delivered(point_id: str) -> list[dict]:
    """Marca un punto de entrega como entregado.

    Args:
        point_id: ID del punto a marcar.

    Returns:
        Lista actualizada con el punto marcado como 'delivered'.
    """
    for p in _state["delivery_points"]:
        if p["id"] == point_id:
            p["status"] = "delivered"
            break
    _save()
    return list(_state["delivery_points"])


@app.tool()
def mark_pending(point_id: str) -> list[dict]:
    """Revierte un punto de entrega a pendiente.

    Usa cuando el repartidor marcó un punto por error.

    Args:
        point_id: ID del punto a revertir.

    Returns:
        Lista actualizada con el punto marcado como 'pending'.
    """
    for p in _state["delivery_points"]:
        if p["id"] == point_id:
            p["status"] = "pending"
            break
    _save()
    return list(_state["delivery_points"])


@app.tool()
async def optimize_route_tool() -> dict[str, Any]:
    """Calcula la ruta más óptima entre los puntos pendientes.

    Usa OSRM Trip API para distancias reales por calles.
    Si OSRM no está disponible, usa haversine + nearest-neighbor.

    Returns:
        {
            "optimized_order": lista de puntos en orden óptimo,
            "total_distance_km": distancia total en km,
            "total_duration_min": duración estimada en minutos,
            "method": "osrm" o "haversine_fallback"
        }
    """
    result = await _optimize_route(
        origin=_state["origin"],
        points=_state["delivery_points"],
    )
    _state["optimized_route"] = result
    _save()
    return result


@app.tool()
def update_origin(name: str, latitude: float, longitude: float) -> dict[str, Any]:
    """Actualiza el punto de origen (bodega) del repartidor.

    Args:
        name: Nombre del punto de origen.
        latitude: Coordenada de latitud.
        longitude: Coordenada de longitud.

    Returns:
        Datos actualizados del origen.
    """
    _state["origin"] = {
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
    }
    _save()
    return dict(_state["origin"])


@app.tool()
def update_fuel_config(
    km_per_liter: float, price_per_liter: float
) -> dict[str, float]:
    """Actualiza la configuración de combustible del vehículo.

    Args:
        km_per_liter: Rendimiento del vehículo en km/litro.
        price_per_liter: Precio actual del combustible por litro.

    Returns:
        Configuración actualizada.
    """
    _state["fuel_config"] = {
        "km_per_liter": km_per_liter,
        "price_per_liter": price_per_liter,
    }
    _save()
    return dict(_state["fuel_config"])


@app.tool()
def get_day_summary() -> dict[str, Any]:
    """Calcula y retorna el resumen del día actual.

    Returns:
        {
            "completed": int,
            "pending": int,
            "total_km": float,
            "total_duration_min": float,
            "fuel_liters": float,
            "fuel_cost": float,
            "optimized_order": list[dict]
        }
    """
    points = _state["delivery_points"]
    completed = sum(1 for p in points if p["status"] == "delivered")
    pending = sum(1 for p in points if p["status"] == "pending")

    route = _state.get("optimized_route", {})
    total_km = route.get("total_distance_km", 0.0)
    total_duration = route.get("total_duration_min", 0.0)

    fuel_config = _state.get("fuel_config", {})
    km_per_liter = fuel_config.get("km_per_liter", 0.0)
    price_per_liter = fuel_config.get("price_per_liter", 0.0)

    fuel_data = {"fuel_liters": 0.0, "fuel_cost": 0.0}
    if km_per_liter > 0 and price_per_liter > 0 and total_km > 0:
        fuel_data = fuel_calculator.calculate_fuel(
            total_km, km_per_liter, price_per_liter
        )

    summary = {
        "completed": completed,
        "pending": pending,
        "total_km": total_km,
        "total_duration_min": total_duration,
        "fuel_liters": fuel_data["fuel_liters"],
        "fuel_cost": fuel_data["fuel_cost"],
        "optimized_order": route.get("optimized_order", []),
    }
    _state["summary"] = summary
    _save()
    return summary


@app.tool()
def archive_day() -> dict[str, str]:
    """Cierra el día actual y guarda el viaje en el historial.

    Guarda un snapshot del estado completo en data/history/{fecha}.json.
    Luego limpia los puntos de entrega y ruta, pero mantiene el origen
    y la configuración de combustible.

    Returns:
        {"archived_date": "YYYY-MM-DD", "message": "Día cerrado..."}
    """
    # Calcular resumen antes de archivar
    get_day_summary()

    archived_date = persistence.archive_day(_state)

    # Recargar el estado limpio
    new_state = persistence.load_state()
    _state.clear()
    _state.update(new_state)

    return {
        "archived_date": archived_date,
        "message": f"Día {archived_date} cerrado y archivado correctamente.",
    }


@app.tool()
def get_trip_detail(date: str) -> dict[str, Any]:
    """Carga el detalle de un viaje archivado por fecha.

    Args:
        date: Fecha del viaje en formato YYYY-MM-DD.

    Returns:
        Estado completo del viaje archivado.

    Raises:
        ValueError: Si no se encuentra el viaje para esa fecha.
    """
    trip = persistence.load_trip(date)
    if trip is None:
        raise ValueError(f"No se encontró un viaje para la fecha {date}")
    return trip


# ═══════════════════════════════════════════════════════════════════════
# @app.ui — Entry points (visibles al modelo)
# ═══════════════════════════════════════════════════════════════════════


@app.ui()
def delivery_dashboard() -> PrefabApp:
    """Abre el panel principal de entregas del día.

    Muestra la lista de puntos de entrega con su estado, acciones
    para marcar entregado/eliminar, y navegación a las demás vistas.
    """
    state = _get_state()
    points = state["delivery_points"]
    completed = sum(1 for p in points if p["status"] == "delivered")
    pending = sum(1 for p in points if p["status"] == "pending")

    with Column(gap=6, css_class="p-6") as view:
        Heading("🚚 Mis Entregas del Día")

        with Row(gap=2, align="center"):
            Badge(f"{pending} pendientes", variant="secondary")
            Badge(f"{completed} completados", variant="success")

        with If("origin.name"):
            Text("📍 Origen: {{ origin.name }}")

        with ForEach("delivery_points") as point:
            with Card():
                with CardHeader():
                    with Row(gap=2, align="center"):
                        Text(point.client_name, css_class="font-semibold")
                        with If(f"{point.status} == 'delivered'"):
                            Badge("Entregado", variant="success")
                        with If(f"{point.status} == 'pending'"):
                            Badge("Pendiente", variant="secondary")
                with CardFooter():
                    with Row(gap=2):
                        Button(
                            "✅ Entregado",
                            size="sm",
                            on_click=CallTool(
                                mark_delivered,
                                arguments={"point_id": point.id},
                                on_success=[
                                    SetState("delivery_points", RESULT),
                                    ShowToast("Punto marcado ✅", variant="success"),
                                ],
                            ),
                        )
                        Button(
                            "↩ Revertir",
                            size="sm",
                            variant="outline",
                            on_click=CallTool(
                                mark_pending,
                                arguments={"point_id": point.id},
                                on_success=[
                                    SetState("delivery_points", RESULT),
                                    ShowToast("Revertido a pendiente"),
                                ],
                            ),
                        )
                        Button(
                            "🗑",
                            size="sm",
                            variant="destructive",
                            on_click=CallTool(
                                remove_point,
                                arguments={"point_id": point.id},
                                on_success=[
                                    SetState("delivery_points", RESULT),
                                    ShowToast("Punto eliminado", variant="success"),
                                ],
                            ),
                        )

        # Ruta optimizada (si existe)
        with If("optimized_route.total_distance_km > 0"):
            Separator()
            Heading("🗺 Ruta Optimizada", level=3)
            with Row(gap=2):
                Badge(
                    "{{ optimized_route.total_distance_km }} km",
                    variant="outline",
                )
                Badge(
                    "{{ optimized_route.total_duration_min }} min",
                    variant="outline",
                )
                Badge(
                    "Método: {{ optimized_route.method }}",
                    variant="secondary",
                )
            with ForEach("optimized_route.optimized_order") as stop:
                with Row(gap=2, align="center"):
                    Badge("{{ $index + 1 }}", variant="default")
                    Text(stop.client_name)

        Separator()

        # Botones de acción
        with Grid(columns=2, gap=3):
            Button(
                "➕ Agregar Punto",
                on_click=CallTool(add_delivery_point),
            )
            Button(
                "🗺 Optimizar Ruta",
                on_click=CallTool(
                    optimize_route_tool,
                    on_success=[
                        SetState("optimized_route", RESULT),
                        ShowToast("Ruta optimizada ✅", variant="success"),
                    ],
                    on_error=ShowToast(
                        "Error al optimizar ruta", variant="error"
                    ),
                ),
            )
            Button(
                "📍 Punto de Origen",
                variant="outline",
                on_click=CallTool(origin_settings),
            )
            Button(
                "⛽ Combustible",
                variant="outline",
                on_click=CallTool(fuel_settings),
            )
            Button(
                "📊 Resumen del Día",
                variant="outline",
                on_click=CallTool(
                    get_day_summary,
                    on_success=[
                        SetState("summary", RESULT),
                        ShowToast("Resumen calculado", variant="success"),
                    ],
                ),
            )
            Button(
                "📂 Historial",
                variant="outline",
                on_click=CallTool(trip_history),
            )

        Separator()

        Button(
            "📦 Cerrar Día",
            variant="destructive",
            css_class="w-full",
            on_click=CallTool(
                archive_day,
                on_success=[
                    SetState("delivery_points", []),
                    SetState("optimized_route", {
                        "optimized_order": [],
                        "total_distance_km": 0.0,
                        "total_duration_min": 0.0,
                        "method": "",
                    }),
                    ShowToast("Día cerrado y archivado ✅", variant="success"),
                ],
                on_error=ShowToast("Error al cerrar el día", variant="error"),
            ),
        )

    return PrefabApp(view=view, state=state)


@app.ui()
def add_delivery_point() -> PrefabApp:
    """Abre el formulario para agregar un nuevo punto de entrega.

    Usa Form.from_model con el modelo DeliveryPointInput para
    generar automáticamente los campos de nombre, latitud y longitud.
    """
    state = _get_state()

    with Column(gap=6, css_class="p-6") as view:
        Heading("➕ Nuevo Punto de Entrega")

        Form.from_model(
            DeliveryPointInput,
            submit_label="Agregar Punto",
            on_submit=CallTool(
                add_point,
                on_success=[
                    SetState("delivery_points", RESULT),
                    ShowToast("Punto agregado ✅", variant="success"),
                ],
                on_error=ShowToast("Error al agregar punto", variant="error"),
            ),
        )

        Button(
            "← Volver al Dashboard",
            variant="outline",
            on_click=CallTool(delivery_dashboard),
        )

    return PrefabApp(view=view, state=state)


@app.ui()
def origin_settings() -> PrefabApp:
    """Abre el formulario para configurar el punto de origen (bodega).

    Permite cambiar la ubicación de partida del repartidor.
    La configuración se guarda y persiste entre sesiones.
    """
    state = _get_state()

    with Column(gap=6, css_class="p-6") as view:
        Heading("📍 Punto de Origen")
        Text("Configura la ubicación de la bodega o punto de salida")

        with If("origin.latitude != 0"):
            with Card():
                with CardContent():
                    Text("Origen actual: {{ origin.name }}")
                    Text("Lat: {{ origin.latitude }}, Lon: {{ origin.longitude }}")

        Form.from_model(
            OriginInput,
            submit_label="Guardar Origen",
            on_submit=CallTool(
                update_origin,
                on_success=[
                    SetState("origin", RESULT),
                    ShowToast("Origen actualizado ✅", variant="success"),
                ],
                on_error=ShowToast("Error al guardar", variant="error"),
            ),
        )

        Button(
            "← Volver al Dashboard",
            variant="outline",
            on_click=CallTool(delivery_dashboard),
        )

    return PrefabApp(view=view, state=state)


@app.ui()
def fuel_settings() -> PrefabApp:
    """Abre el formulario de configuración de combustible.

    Permite ingresar rendimiento del vehículo (km/litro) y
    precio actual del combustible para calcular costos de ruta.
    """
    state = _get_state()

    with Column(gap=6, css_class="p-6") as view:
        Heading("⛽ Configuración de Combustible")

        with If("fuel_config.km_per_liter > 0"):
            with Card():
                with CardContent():
                    Text("Rendimiento: {{ fuel_config.km_per_liter }} km/litro")
                    Text("Precio: ${{ fuel_config.price_per_liter }} /litro")

        Form.from_model(
            FuelConfigInput,
            submit_label="Guardar Configuración",
            on_submit=CallTool(
                update_fuel_config,
                on_success=[
                    SetState("fuel_config", RESULT),
                    ShowToast("Configuración guardada ✅", variant="success"),
                ],
                on_error=ShowToast("Error al guardar", variant="error"),
            ),
        )

        Button(
            "← Volver al Dashboard",
            variant="outline",
            on_click=CallTool(delivery_dashboard),
        )

    return PrefabApp(view=view, state=state)


@app.ui()
def day_summary() -> PrefabApp:
    """Muestra el resumen completo del día actual.

    Incluye: puntos completados y pendientes, distancia total,
    duración estimada, litros necesarios y costo de combustible.
    """
    # Calcular resumen fresco
    summary = get_day_summary()
    state = {"summary": summary}

    with Column(gap=6, css_class="p-6") as view:
        Heading("📊 Resumen del Día")

        with Grid(columns=2, gap=4):
            with Card():
                with CardContent():
                    Text("Completados", css_class="text-muted-foreground text-sm")
                    Heading("{{ summary.completed }}", level=2)
            with Card():
                with CardContent():
                    Text("Pendientes", css_class="text-muted-foreground text-sm")
                    Heading("{{ summary.pending }}", level=2)
            with Card():
                with CardContent():
                    Text("Distancia Total", css_class="text-muted-foreground text-sm")
                    Heading("{{ summary.total_km }} km", level=2)
            with Card():
                with CardContent():
                    Text("Costo Combustible", css_class="text-muted-foreground text-sm")
                    Heading("${{ summary.fuel_cost }}", level=2)

        with If("summary.total_duration_min > 0"):
            with Card():
                with CardContent():
                    Text("Tiempo estimado de manejo")
                    Heading("{{ summary.total_duration_min }} min", level=3)

        with If("summary.optimized_order"):
            Separator()
            Heading("Orden de Ruta", level=3)
            with ForEach("summary.optimized_order") as stop:
                with Row(gap=2, align="center"):
                    Badge("{{ $index + 1 }}")
                    Text(stop.client_name)

        Separator()

        Button(
            "← Volver al Dashboard",
            variant="outline",
            on_click=CallTool(delivery_dashboard),
        )

    return PrefabApp(view=view, state=state)


@app.ui()
def trip_history() -> PrefabApp:
    """Muestra el historial de viajes cerrados.

    Lista los días anteriores con métricas resumidas y permite
    ver el detalle de cualquier viaje archivado.
    """
    past_trips = persistence.list_trips()
    state = {"past_trips": past_trips}

    with Column(gap=6, css_class="p-6") as view:
        Heading("📂 Historial de Viajes")

        with If("past_trips.length == 0"):
            Text("No hay viajes registrados aún", css_class="text-muted-foreground")

        with ForEach("past_trips") as trip:
            with Card():
                with CardHeader():
                    Text(f"📅 {trip.date}", css_class="font-semibold")
                with CardContent():
                    with Row(gap=2):
                        Badge(f"{trip.completed} entregas", variant="success")
                        Badge(f"{trip.total_km} km", variant="outline")
                        Badge(f"${trip.fuel_cost}", variant="outline")
                with CardFooter():
                    Button(
                        "Ver Detalle",
                        size="sm",
                        on_click=CallTool(
                            get_trip_detail,
                            arguments={"date": trip.date},
                            on_success=SetState("trip_detail", RESULT),
                            on_error=ShowToast(
                                "No se pudo cargar el viaje", variant="error"
                            ),
                        ),
                    )

        Separator()

        Button(
            "← Volver al Dashboard",
            variant="outline",
            on_click=CallTool(delivery_dashboard),
        )

    return PrefabApp(view=view, state=state)
