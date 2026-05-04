"""Gestor de lógica de negocio para jornadas de entrega.

Funciones puras que operan sobre el modelo Trip sin efectos
secundarios (sin IO, sin persistencia, sin HTTP).
La capa de servicio (trip_service) se encarga de orquestar
estas funciones con persistencia y otros servicios.
"""

from __future__ import annotations

from datetime import datetime, timezone
from delivery_app.utils.time_utils import now_mx
from uuid import uuid4

from delivery_app.domain.enums import DeliveryStatus, ReturnMode, TripStatus
from delivery_app.domain.models import (
    Coordinates,
    Delivery,
    FuelConfig,
    Metrics,
    NamedPoint,
    RouteResult,
    Trip,
)


def create_trip(
    origin: NamedPoint,
    *,
    driver_id: str | None = None,
    return_mode: ReturnMode = ReturnMode.ORIGIN,
    return_point: NamedPoint | None = None,
    fuel_config: FuelConfig | None = None,
) -> Trip:
    """Crea una nueva jornada de entrega.

    Args:
        origin: Punto de origen (bodega).
        driver_id: ID del repartidor (opcional, para multi-user).
        return_mode: Modo de retorno al finalizar la ruta.
        return_point: Punto de retorno personalizado (solo si return_mode == CUSTOM).
        fuel_config: Configuración de combustible (opcional).

    Returns:
        Trip nuevo con status ACTIVE.
    """
    return Trip(
        origin=origin,
        driver_id=driver_id,
        return_mode=return_mode,
        return_point=return_point,
        fuel_config=fuel_config,
    )


def add_delivery(trip: Trip, delivery: Delivery) -> Trip:
    """Agrega una entrega a la jornada.

    Returns:
        Trip actualizado con la nueva entrega.

    Raises:
        ValueError: Si el trip ya está cerrado.
    """
    if trip.status == TripStatus.CLOSED:
        raise ValueError("No se pueden agregar entregas a una jornada cerrada.")

    updated_deliveries = list(trip.deliveries) + [delivery]
    return trip.model_copy(update={"deliveries": updated_deliveries})


def remove_delivery(trip: Trip, delivery_id: str) -> Trip:
    """Elimina una entrega de la jornada.

    Returns:
        Trip actualizado sin la entrega eliminada.

    Raises:
        ValueError: Si el trip está cerrado o la entrega no existe.
    """
    if trip.status == TripStatus.CLOSED:
        raise ValueError("No se pueden eliminar entregas de una jornada cerrada.")

    updated = [d for d in trip.deliveries if d.delivery_id != delivery_id]
    if len(updated) == len(trip.deliveries):
        raise ValueError(f"Entrega {delivery_id} no encontrada.")

    return trip.model_copy(update={"deliveries": updated})


def change_delivery_status(
    trip: Trip,
    delivery_id: str,
    new_status: DeliveryStatus,
    *,
    note: str | None = None,
    reason: str | None = None,
) -> Trip:
    """Cambia el estado de una entrega.

    Args:
        trip: Jornada actual.
        delivery_id: ID de la entrega a modificar.
        new_status: Nuevo estado.
        note: Nota opcional.
        reason: Motivo del cambio (útil para rechazos, reprogramaciones).

    Returns:
        Trip actualizado con el estado de entrega cambiado.

    Raises:
        ValueError: Si el trip está cerrado o la entrega no existe.
    """
    if trip.status == TripStatus.CLOSED:
        raise ValueError("No se pueden modificar entregas de una jornada cerrada.")

    now = now_mx()
    found = False
    updated_deliveries: list[Delivery] = []

    for d in trip.deliveries:
        if d.delivery_id == delivery_id:
            found = True
            updates: dict = {
                "status": new_status,
                "updated_at": now,
                "note": note if note is not None else d.note,
                "reason": reason if reason is not None else d.reason,
            }
            # Si es un estado terminal, registrar completed_at
            if new_status in (
                DeliveryStatus.DELIVERED,
                DeliveryStatus.CANCELLED,
                DeliveryStatus.REJECTED,
            ):
                updates["completed_at"] = now
            elif new_status == DeliveryStatus.PENDING:
                # Si se revierte a pendiente, limpiar completed_at
                updates["completed_at"] = None

            updated_deliveries.append(d.model_copy(update=updates))
        else:
            updated_deliveries.append(d)

    if not found:
        raise ValueError(f"Entrega {delivery_id} no encontrada.")

    # Actualizar current_location al punto de la entrega (si fue visitada)
    # BUG-4: Actualizar ubicación para todos los estados terminales/visitados
    visited_states = {
        DeliveryStatus.DELIVERED,
        DeliveryStatus.CANCELLED,
        DeliveryStatus.REJECTED,
        DeliveryStatus.NOT_FOUND,
        DeliveryStatus.RESCHEDULED,
    }

    update_fields: dict = {"deliveries": updated_deliveries}
    if new_status in visited_states:
        delivered = next(
            d for d in updated_deliveries if d.delivery_id == delivery_id
        )
        update_fields["current_location"] = delivered.coordinates

    return trip.model_copy(update=update_fields)


def update_route_plan(trip: Trip, route_result: RouteResult) -> Trip:
    """Actualiza el plan de ruta y las métricas asociadas.

    Args:
        trip: Jornada actual.
        route_result: Resultado de la optimización de ruta.

    Returns:
        Trip actualizado con ruta y métricas.
    """
    metrics_update = Metrics(
        planned_km=route_result.total_distance_km,
        planned_duration_min=route_result.total_duration_min,
        actual_km=trip.metrics.actual_km,
    )

    # Calcular combustible si hay configuración
    if trip.fuel_config and route_result.total_distance_km > 0:
        liters = route_result.total_distance_km / trip.fuel_config.km_per_liter
        cost = liters * trip.fuel_config.fuel_price
        metrics_update = metrics_update.model_copy(
            update={
                "estimated_fuel_liters": round(liters, 2),
                "estimated_fuel_cost": round(cost, 2),
            }
        )

    return trip.model_copy(
        update={
            "route_plan": route_result,
            "metrics": metrics_update,
        }
    )


def update_fuel_config(trip: Trip, fuel_config: FuelConfig) -> Trip:
    """Actualiza la configuración de combustible y recalcula los costos si hay ruta."""
    updated_trip = trip.model_copy(update={"fuel_config": fuel_config})
    
    if updated_trip.route_plan and updated_trip.route_plan.total_distance_km > 0:
        liters = updated_trip.route_plan.total_distance_km / fuel_config.km_per_liter
        cost = liters * fuel_config.fuel_price
        metrics_update = updated_trip.metrics.model_copy(
            update={
                "estimated_fuel_liters": round(liters, 2),
                "estimated_fuel_cost": round(cost, 2),
            }
        )
        updated_trip = updated_trip.model_copy(update={"metrics": metrics_update})
        
    return updated_trip


def close_day(trip: Trip) -> Trip:
    """Cierra la jornada de forma idempotente.

    Si el trip ya está cerrado, retorna el mismo trip sin cambios.
    Esto garantiza que doble clic, refresh o retry no dupliquen
    el cierre.

    Returns:
        Trip con status CLOSED y closed_at establecido.
    """
    if trip.status == TripStatus.CLOSED:
        return trip

    now = now_mx()
    return trip.model_copy(
        update={
            "status": TripStatus.CLOSED,
            "closed_at": now,
        }
    )


def get_pending_deliveries(trip: Trip) -> list[Delivery]:
    """Retorna las entregas pendientes de la jornada."""
    return [d for d in trip.deliveries if d.status == DeliveryStatus.PENDING]


def get_completed_deliveries(trip: Trip) -> list[Delivery]:
    """Retorna las entregas completadas (delivered) de la jornada."""
    return [d for d in trip.deliveries if d.status == DeliveryStatus.DELIVERED]


def get_failed_deliveries(trip: Trip) -> list[Delivery]:
    """Retorna las entregas fallidas (no_found, cancelled, rejected)."""
    failed_statuses = {
        DeliveryStatus.NOT_FOUND,
        DeliveryStatus.CANCELLED,
        DeliveryStatus.REJECTED,
    }
    return [d for d in trip.deliveries if d.status in failed_statuses]


def get_summary(trip: Trip) -> dict:
    """Calcula un resumen de la jornada actual.

    Returns:
        Dict con conteos, métricas y estado del viaje.
    """
    pending = get_pending_deliveries(trip)
    completed = get_completed_deliveries(trip)
    failed = get_failed_deliveries(trip)
    rescheduled = [
        d for d in trip.deliveries if d.status == DeliveryStatus.RESCHEDULED
    ]

    # BUG-5: Garantizar invariante total = pending + completed + failed + rescheduled
    # failed ya incluye NOT_FOUND, CANCELLED, REJECTED.
    total_count = len(trip.deliveries)
    sum_counts = len(pending) + len(completed) + len(failed) + len(rescheduled)
    if total_count != sum_counts:
        # Esto no debería pasar con los enums actuales, pero es una salvaguarda.
        pass

    # Determinar título: "DD/MM | Origen ➡ Última Entrega"
    date_str = trip.created_at.strftime("%d/%m")
    last_stop = "Sin entregas"
    if trip.deliveries:
        if trip.route_plan and trip.route_plan.optimized_order:
            last_id = trip.route_plan.optimized_order[-1]
            last_d = next((d for d in trip.deliveries if d.delivery_id == last_id), None)
            if last_d:
                last_stop = last_d.client_name
        else:
            last_stop = trip.deliveries[-1].client_name

    return {
        "trip_id": trip.trip_id,
        "display_title": f"{date_str} | {trip.origin.name} ➡ {last_stop}",
        "status": trip.status.value,
        "total": len(trip.deliveries),
        "completed": len(completed),
        "pending": len(pending),
        "failed": len(failed),
        "rescheduled": len(rescheduled),
        "planned_km": trip.metrics.planned_km,
        "planned_duration_min": trip.metrics.planned_duration_min,
        "estimated_fuel_liters": trip.metrics.estimated_fuel_liters,
        "estimated_fuel_cost": f"{trip.metrics.estimated_fuel_cost:.2f}",
        "route_method": (
            trip.route_plan.method.value if trip.route_plan else None
        ),
    }
