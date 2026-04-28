"""Modelos Pydantic para formularios de la app de entregas.

Estos modelos se usan con Form.from_model() de prefab-ui para
generar formularios automáticamente. Usan campos str para evitar
problemas de validación de coma flotante en el frontend,
pero validan estrictamente su contenido.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CoordinateFormBase(BaseModel):
    """Base para formularios con coordenadas."""

    latitude: str = Field(
        title="Latitud",
        description="Coordenada de latitud (ej: 21.8664)",
    )
    longitude: str = Field(
        title="Longitud",
        description="Coordenada de longitud (ej: -102.2991)",
    )

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: str) -> str:
        try:
            val = float(str(v).replace(",", "."))
        except ValueError:
            raise ValueError("La latitud debe ser un número válido")
        if not (-90.0 <= val <= 90.0):
            raise ValueError("La latitud debe estar entre -90 y 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: str) -> str:
        try:
            val = float(str(v).replace(",", "."))
        except ValueError:
            raise ValueError("La longitud debe ser un número válido")
        if not (-180.0 <= val <= 180.0):
            raise ValueError("La longitud debe estar entre -180 y 180")
        return v


class DeliveryPointInput(CoordinateFormBase):
    """Datos para agregar un nuevo punto de entrega."""

    client_name: str = Field(
        title="Nombre del Cliente",
        min_length=1,
        description="Nombre del negocio o persona",
    )


class OriginInput(CoordinateFormBase):
    """Datos para configurar el punto de origen (bodega)."""

    name: str = Field(
        title="Nombre del Origen",
        min_length=1,
        description="Ej: Bodega Central, Almacén Norte",
    )


class ReturnPointInput(CoordinateFormBase):
    """Datos para configurar un punto de retorno personalizado."""

    name: str = Field(
        title="Nombre del Punto de Retorno",
        min_length=1,
        description="Ej: Casa, Oficina, Otro Almacén",
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

    @field_validator("km_per_liter")
    @classmethod
    def validate_km(cls, v: str) -> str:
        try:
            val = float(str(v).replace(",", "."))
            if val <= 0:
                raise ValueError("El rendimiento debe ser mayor a 0")
        except ValueError:
            raise ValueError("El rendimiento debe ser un número válido mayor a 0")
        return v

    @field_validator("price_per_liter")
    @classmethod
    def validate_price(cls, v: str) -> str:
        try:
            val = float(str(v).replace(",", "."))
            if val < 0:
                raise ValueError("El precio no puede ser negativo")
        except ValueError:
            raise ValueError("El precio debe ser un número válido")
        return v


class DeliveryStatusInput(BaseModel):
    """Datos para cambiar el estado de una entrega con motivos."""

    note: str = Field(
        title="Nota (opcional)",
        default="",
        description="Información adicional sobre la entrega",
    )
    reason: str = Field(
        title="Motivo (opcional)",
        default="",
        description="Motivo en caso de no entregado o rechazado",
    )
