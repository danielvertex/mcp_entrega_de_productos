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
    latitude: str = Field(
        title="Latitud",
        description="Coordenada de latitud (ej: -34.6037)",
    )
    longitude: str = Field(
        title="Longitud",
        description="Coordenada de longitud (ej: -58.3816)",
    )


class OriginInput(BaseModel):
    """Datos para configurar el punto de origen (bodega)."""

    name: str = Field(
        title="Nombre del Origen",
        min_length=1,
        description="Ej: Bodega Central, Almacén Norte",
    )
    latitude: str = Field(
        title="Latitud",
        description="Coordenada de latitud del punto de salida (ej: -34.6037)",
    )
    longitude: str = Field(
        title="Longitud",
        description="Coordenada de longitud del punto de salida (ej: -58.3816)",
    )


class FuelConfigInput(BaseModel):
    """Datos para configurar el rendimiento y precio de combustible."""

    km_per_liter: str = Field(
        title="Rendimiento (km/litro)",
        description="Kilómetros por litro del vehículo (ej: 12.5)",
    )
    price_per_liter: str = Field(
        title="Precio por Litro ($)",
        description="Precio actual del combustible por litro (ej: 23.50)",
    )
