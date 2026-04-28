"""Cliente HTTP para la API de OSRM.

Separado de la lógica de negocio para facilitar testing
(se puede mockear) y para encapsular timeout, retries y
manejo de errores HTTP.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from delivery_app.infrastructure.config import OSRMConfig

logger = logging.getLogger(__name__)


class OSRMClient:
    """Cliente para OSRM Trip API.

    Responsabilidad: hacer la petición HTTP y retornar datos crudos.
    No contiene lógica de negocio ni interpretación de resultados.
    """

    def __init__(self, config: OSRMConfig | None = None) -> None:
        self._config = config or OSRMConfig()

    async def trip(
        self,
        coordinates: list[tuple[float, float]],
        *,
        roundtrip: bool = True,
        source: str = "first",
        destination: str | None = None,
    ) -> dict[str, Any] | None:
        """Llama a OSRM Trip API.

        Args:
            coordinates: Lista de (longitude, latitude).
            roundtrip: Si la ruta es circular.
            source: "first" o "any".
            destination: "last", "any", o None.

        Returns:
            Respuesta JSON parseada de OSRM, o None si falla.
        """
        if len(coordinates) < 2:
            return None

        coords_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        url = f"{self._config.base_url}/trip/v1/driving/{coords_str}"

        params: dict[str, str] = {
            "roundtrip": str(roundtrip).lower(),
            "source": source,
            "overview": "false",
            "steps": "false",
        }
        if destination is not None:
            params["destination"] = destination

        try:
            async with httpx.AsyncClient(
                timeout=self._config.timeout_seconds
            ) as client:
                response = await client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(
                    "OSRM respondió con status %d para %s",
                    response.status_code,
                    url,
                )
                return None

            data = response.json()
            if data.get("code") != "Ok":
                logger.warning(
                    "OSRM retornó code=%s: %s",
                    data.get("code"),
                    data.get("message", ""),
                )
                return None

            return data

        except httpx.TimeoutException:
            logger.warning(
                "OSRM timeout después de %.1fs para %s",
                self._config.timeout_seconds,
                url,
            )
            return None
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning("OSRM error: %s", exc)
            return None
