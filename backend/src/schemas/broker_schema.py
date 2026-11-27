"""Validación HTTP de entrada del broker (solo se usan en los routers). Mensajes en castellano."""
import re
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.utils.validaciones import validar_cuit, validar_email, validar_nombre

Perfil = Literal["conservador", "moderado", "agresivo"]
TipoActivo = Literal["accion", "cedear", "bono"]
Moneda = Literal["ARS", "USD"]
TipoOperacion = Literal["compra", "venta"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


MAXIMO = Decimal("1000000000000")  # un billón: mucho más que cualquier monto real, y entra en NUMERIC(18, 2)


def _positivo(v: Decimal, campo: str, decimales: int) -> Decimal:
    if v is None or v <= 0:
        raise ValueError(f"{campo} tiene que ser mayor a 0")
    if v > MAXIMO:
        raise ValueError(f"{campo} es demasiado grande (máximo 1.000.000.000.000)")
    if v.as_tuple().exponent < -decimales:
        raise ValueError(f"{campo} admite hasta {decimales} decimales")
    return v


def validar_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("La contraseña tiene que tener al menos 8 caracteres")
    if len(v) > 128:
        raise ValueError("La contraseña puede tener hasta 128 caracteres")
    if v.strip() != v:
        raise ValueError("La contraseña no puede empezar ni terminar con espacios")
    return v


# ---------- Inversores y sesión ----------
class CreateInversorSchema(BaseModel):
    email: str
    nombre: str
    cuit: str
    perfil_riesgo: Perfil
    password: str

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return validar_password(v)

    # El correo tiene que tener formato válido y un dominio que exista y reciba emails;
    # el CUIT, un prefijo de AFIP y el dígito verificador correcto
    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return validar_email(v)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        return validar_nombre(v)

    @field_validator("cuit")
    @classmethod
    def _cuit(cls, v: str) -> str:
        return validar_cuit(v)


class UpdatePerfilSchema(BaseModel):
    perfil_riesgo: Perfil


class IngresarSchema(BaseModel):
    email: str
    password: str


class CambiarPasswordSchema(BaseModel):
    permiso: str = Field(min_length=10, max_length=100)
    nueva: str

    @field_validator("nueva")
    @classmethod
    def _nueva(cls, v: str) -> str:
        return validar_password(v)


class ConfirmarPasswordSchema(BaseModel):
    codigo: str

    @field_validator("codigo")
    @classmethod
    def _codigo(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("El código tiene 6 dígitos")
        return v


# ---------- Activos ----------
class CreateActivoSchema(BaseModel):
    ticker: str
    nombre: str
    tipo: TipoActivo
    moneda: Moneda
    precio_actual: Decimal
    nivel_riesgo: int
    activo: bool = True

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9.]{1,12}", v):
            raise ValueError("ticker inválido (letras/números, hasta 12)")
        return v

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 120:
            raise ValueError("el nombre es obligatorio")
        return v

    @field_validator("precio_actual")
    @classmethod
    def _precio(cls, v: Decimal) -> Decimal:
        return _positivo(v, "el precio", 4)

    @field_validator("nivel_riesgo")
    @classmethod
    def _riesgo(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("el nivel de riesgo va de 1 a 5")
        return v


class UpdatePrecioSchema(BaseModel):
    precio: Decimal

    @field_validator("precio")
    @classmethod
    def _precio(cls, v: Decimal) -> Decimal:
        return _positivo(v, "el precio", 4)


class UpdateEstadoSchema(BaseModel):
    activo: bool


# ---------- Dinero y operaciones ----------
class MontoMonedaSchema(BaseModel):
    moneda: Moneda
    monto: Decimal

    @field_validator("monto")
    @classmethod
    def _monto(cls, v: Decimal) -> Decimal:
        return _positivo(v, "el monto", 2)


class OrdenSchema(BaseModel):
    """Se puede indicar el activo por id o por ticker."""

    activo_id: int | None = None
    ticker: str | None = None
    cantidad: int

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, v: int) -> int:
        if v < 1:
            raise ValueError("la cantidad tiene que ser un entero mayor a 0")
        if v > 10_000_000:
            raise ValueError("la cantidad máxima por orden es 10.000.000")
        return v

    @model_validator(mode="after")
    def _activo(self):
        if self.activo_id is None and not self.ticker:
            raise ValueError("indicá activo_id o ticker")
        return self


class MepSchema(BaseModel):
    monto_ars: Decimal

    @field_validator("monto_ars")
    @classmethod
    def _monto(cls, v: Decimal) -> Decimal:
        return _positivo(v, "el monto", 2)


class CreateDividendoSchema(BaseModel):
    activo_id: int
    monto_por_unidad: Decimal
    fecha_pago: date | None = None

    @field_validator("monto_por_unidad")
    @classmethod
    def _monto(cls, v: Decimal) -> Decimal:
        return _positivo(v, "el monto por unidad", 4)
