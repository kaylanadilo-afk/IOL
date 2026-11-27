"""Validación de las alertas de precio."""
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

TipoAlerta = Literal["sube_pct", "baja_pct", "precio"]


def _valor(v: Decimal) -> Decimal:
    if v is None or v <= 0:
        raise ValueError("Ingresá un valor mayor a 0")
    if v > Decimal("100000000"):
        raise ValueError("El valor es demasiado grande")
    if v.as_tuple().exponent < -4:
        raise ValueError("Admite hasta 4 decimales")
    return v


class CreateAlertaSchema(BaseModel):
    activo_id: int
    tipo: TipoAlerta
    valor: Decimal  # porcentaje (sube/baja) o precio objetivo
    recurrente: bool = False
    aviso_email: bool = True
    aviso_app: bool = True

    @field_validator("valor")
    @classmethod
    def _v(cls, v: Decimal) -> Decimal:
        return _valor(v)

    @model_validator(mode="after")
    def _reglas(self):
        if self.tipo == "baja_pct" and self.valor >= 100:
            raise ValueError("Una baja tiene que ser menor al 100 %")
        if self.tipo != "precio" and self.valor > 1000:
            raise ValueError("El porcentaje puede ser de hasta 1000 %")
        if not (self.aviso_email or self.aviso_app):
            raise ValueError("Elegí al menos una forma de aviso")
        return self


class UpdateAlertaSchema(BaseModel):
    tipo: TipoAlerta | None = None
    valor: Decimal | None = None
    recurrente: bool | None = None
    aviso_email: bool | None = None
    aviso_app: bool | None = None

    @field_validator("valor")
    @classmethod
    def _v(cls, v: Decimal | None) -> Decimal | None:
        return None if v is None else _valor(v)

    @model_validator(mode="after")
    def _alguno(self):
        if not self.model_dump(exclude_unset=True):
            raise ValueError("indicá al menos un campo para cambiar")
        return self


class EstadoAlertaSchema(BaseModel):
    estado: Literal["activa", "pausada"]
