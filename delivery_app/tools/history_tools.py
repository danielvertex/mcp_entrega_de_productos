"""Tools para el historial de jornadas."""

from __future__ import annotations

import logging
import json
from pathlib import Path

from fastmcp import FastMCPApp

from delivery_app.services.trip_service import TripService
from delivery_app.domain.trip_manager import get_summary
from delivery_app.utils.time_utils import now_mx

logger = logging.getLogger(__name__)


def register_history_tools(app: FastMCPApp, trip_service: TripService) -> None:
    """Registra los tools del historial en la app."""

    @app.tool()
    def export_route(trip_id: str, format: str = "full") -> dict:
        """Exporta los datos de una jornada archivada en formato JSON.

        Args:
            trip_id: ID de la jornada a exportar. Usa list_history para
                     obtener los IDs disponibles.
            format: Nivel de detalle del export.
                    - "full": todos los campos del Trip (default)
                    - "summary": solo métricas y resumen general
                    - "route": solo la ruta optimizada y coordenadas
                    - "deliveries": solo la lista de entregas con sus estados

        Returns:
            dict con:
              - "trip_id": str
              - "exported_at": str (ISO 8601)
              - "format": str (el formato solicitado)
              - "data": dict con los datos según el formato elegido
        """
        valid_formats = {"full", "summary", "route", "deliveries"}
        if format not in valid_formats:
            raise ValueError(f"❌ Formato '{format}' no válido. Usa: full, summary, route, deliveries.")

        trip = trip_service.load_archived_trip(trip_id)
        if not trip:
            raise ValueError(f"❌ Jornada '{trip_id}' no encontrada en el historial.")

        exported_at = now_mx().isoformat()
        
        if format == "full":
            data = trip.model_dump(mode="json")
        elif format == "summary":
            data = get_summary(trip)
            data["trip_date"] = trip.created_at.isoformat()
            data["closed_at"] = trip.closed_at.isoformat() if trip.closed_at else None
            data["status"] = trip.status.value
        elif format == "route":
            if not trip.route_plan:
                raise ValueError("❌ Esta jornada no tiene ruta calculada. Exporta con format='deliveries' o format='full'.")
            
            ordered_ids = trip.route_plan.optimized_order
            deliveries_by_id = {d.delivery_id: d for d in trip.deliveries}
            
            stops = []
            for i, did in enumerate(ordered_ids):
                d = deliveries_by_id.get(did)
                if d:
                    stops.append({
                        "sequence": i + 1,
                        "delivery_id": d.delivery_id,
                        "client_name": d.client_name,
                        "latitude": d.coordinates.latitude,
                        "longitude": d.coordinates.longitude,
                        "status": d.status.value,
                    })
                    
            data = {
                "origin": {
                    "name": trip.origin.name,
                    "latitude": trip.origin.coordinates.latitude,
                    "longitude": trip.origin.coordinates.longitude,
                },
                "stops": stops,
                "total_distance_km": trip.route_plan.total_distance_km,
                "total_duration_min": trip.route_plan.total_duration_min,
                "return_mode": trip.return_mode.value,
                "method": trip.route_plan.method.value,
            }
        elif format == "deliveries":
            data = {
                "total": len(trip.deliveries),
                "deliveries": [
                    {
                        "delivery_id": d.delivery_id,
                        "client_name": d.client_name,
                        "latitude": d.coordinates.latitude,
                        "longitude": d.coordinates.longitude,
                        "status": d.status.value,
                        "note": d.note,
                        "reason": d.reason,
                        "completed_at": d.completed_at.isoformat() if d.completed_at else None,
                    }
                    for d in trip.deliveries
                ]
            }

        result = {
            "trip_id": trip_id,
            "exported_at": exported_at,
            "format": format,
            "data": data,
        }
        
        # Guardar en disco para que el usuario pueda encontrarlo
        exports_dir = Path("data/exports")
        exports_dir.mkdir(parents=True, exist_ok=True)
        export_file = exports_dir / f"export_{trip_id}_{format}.json"
        export_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        
        return result
