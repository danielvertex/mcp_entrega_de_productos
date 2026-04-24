"""Modelos Pydantic para formularios de la app de entregas.

Estos modelos se usan con Form.from_model() de prefab-ui para
generar formularios automáticamente.
"""

from pydantic import BaseModel, Field


class DeliveryPointInput(BaseModel):
    """Datos para agregar un nuevo punto de entrega."""

    client_name: str = Field(
        title="Nombre del Cliente",
        min_length=1,
        description="Nombre del negocio o persona",
    )
    latitude: float = Field(
        title="Latitud",
        ge=-90,
        le=90,
        description="Coordenada de latitud",
    )
    longitude: float = Field(
        title="Longitud",
        ge=-180,
        le=180,
        description="Coordenada de longitud",
    )


class OriginInput(BaseModel):
    """Datos para configurar el punto de origen (bodega)."""

    name: str = Field(
        title="Nombre del Origen",
        min_length=1,
        description="Ej: Bodega Central, Almacén Norte",
    )
    latitude: float = Field(
        title="Latitud",
        ge=-90,
        le=90,
        description="Coordenada de latitud del punto de salida",
    )
    longitude: float = Field(
        title="Longitud",
        ge=-180,
        le=180,
        description="Coordenada de longitud del punto de salida",
    )


class FuelConfigInput(BaseModel):
    """Datos para configurar el rendimiento y precio de combustible."""

    km_per_liter: float = Field(
        title="Rendimiento (km/litro)",
        gt=0,
        le=100,
        description="Kilómetros por litro del vehículo",
    )
    price_per_liter: float = Field(
        title="Precio por Litro ($)",
        gt=0,
        description="Precio actual del combustible por litro",
    )
