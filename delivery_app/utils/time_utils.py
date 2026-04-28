"""Utilidades para manejo de tiempo y zonas horarias."""

from datetime import datetime, timezone, timedelta

# México Central Time (Aguascalientes) es UTC-6. 
# Nota: México abolió el horario de verano en 2022 para la mayoría del país.
MEXICO_CENTRAL_OFFSET = -6
MX_TZ = timezone(timedelta(hours=MEXICO_CENTRAL_OFFSET))

def now_mx() -> datetime:
    """Retorna la fecha y hora actual en la zona horaria de México Central."""
    return datetime.now(MX_TZ)
