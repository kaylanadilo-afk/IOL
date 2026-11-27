"""Validación de los endpoints de registros (alta, edición y baja de cada tabla) y del panel."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from src.schemas.broker_schema import MAXIMO, Moneda, OrdenSchema, Perfil, TipoActivo, TipoOperacion, _positivo
from src.utils.validaciones import validar_cuit, validar_email, validar_nombre

EstadoOperacion = Literal["ejecutada", "pendiente", "rechazada"]
TipoTransferencia = Literal["deposito", "extraccion"]


def sin_nulos(datos):
    """Un campo que se manda vacío (null) no significa "dejarlo igual": se rechaza con un mensaje claro."""
    if isinstance(datos, dict):
        vacios = [k for k, v in datos.items() if v is None]
        if vacios:
            raise ValueError(f"{', '.join(vacios)}: no puede ir vacío (si no querés cambiarlo, no lo mandes)")
    return datos


def _algo(modelo: BaseModel) -> BaseModel:
    if not modelo.model_dump(exclude_unset=True):
        raise ValueError("indicá al menos un campo para cambiar")
    return modelo


# ---------- Inversores ----------
class UpdateInversorSchema(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _sin_nulos(cls, datos):
        return sin_nulos(datos)

    email: str | None = None
    nombre: str | None = None
    cuit: str | None = None
    perfil_riesgo: Perfil | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return None if v is None else validar_email(v)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str | None) -> str | None:
        return None if v is None else validar_nombre(v)

    @field_validator("cuit")
    @classmethod
    def _cuit(cls, v: str | None) -> str | None:
        return None if v is None else validar_cuit(v)

    @model_validator(mode="after")
    def _alguno(self):
        return _algo(self)


# ---------- Cuentas ----------
class CreateCuentaSchema(BaseModel):
    inversor_id: int


class UpdateCuentaSchema(BaseModel):
    """Ajuste manual de saldos (corrección del administrador)."""

    @model_validator(mode="before")
    @classmethod
    def _sin_nulos(cls, datos):
        return sin_nulos(datos)

    saldo_ars: Decimal | None = None
    saldo_usd: Decimal | None = None

    @field_validator("saldo_ars", "saldo_usd")
    @classmethod
    def _saldo(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and (v < 0 or v.as_tuple().exponent < -2):
            raise ValueError("el saldo no puede ser negativo y admite hasta 2 decimales")
        if v is not None and v > MAXIMO:
            raise ValueError("el saldo es demasiado grande (máximo 1.000.000.000.000)")
        return v

    @model_validator(mode="after")
    def _alguno(self):
        return _algo(self)


# ---------- Activos ----------
class UpdateActivoSchema(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _sin_nulos(cls, datos):
        return sin_nulos(datos)

    nombre: str | None = None
    tipo: TipoActivo | None = None
    moneda: Moneda | None = None
    precio_actual: Decimal | None = None
    nivel_riesgo: int | None = None
    activo: bool | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str | None) -> str | None:
        if v is not None and not 1 <= len(v.strip()) <= 120:
            raise ValueError("el nombre es obligatorio")
        return v.strip() if v else v

    @field_validator("precio_actual")
    @classmethod
    def _precio(cls, v: Decimal | None) -> Decimal | None:
        return None if v is None else _positivo(v, "el precio", 4)

    @field_validator("nivel_riesgo")
    @classmethod
    def _riesgo(cls, v: int | None) -> int | None:
        if v is not None and not 1 <= v <= 5:
            raise ValueError("el nivel de riesgo va de 1 a 5")
        return v

    @model_validator(mode="after")
    def _alguno(self):
        return _algo(self)


# ---------- Operaciones ----------
class CreateOperacionSchema(OrdenSchema):
    """Compra o venta con las mismas reglas que /cuentas/{id}/compras y /ventas."""

    cuenta_id: int
    tipo: TipoOperacion


class UpdateOperacionSchema(BaseModel):
    estado: EstadoOperacion


# ---------- Movimientos ----------
class CreateMovimientoSchema(BaseModel):
    """Depósito o extracción con las mismas reglas que /cuentas/{id}/depositos y /extracciones."""

    cuenta_id: int
    tipo: TipoTransferencia
    moneda: Moneda
    monto: Decimal

    @field_validator("monto")
    @classmethod
    def _monto(cls, v: Decimal) -> Decimal:
        return _positivo(v, "el monto", 2)


class UpdateMovimientoSchema(BaseModel):
    descripcion: str

    @field_validator("descripcion")
    @classmethod
    def _desc(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 200:
            raise ValueError("la descripción es obligatoria (hasta 200 caracteres)")
        return v


# ---------- Tenencias ----------
class CreateTenenciaSchema(BaseModel):
    cuenta_id: int
    activo_id: int
    cantidad: int
    precio_promedio: Decimal

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, v: int) -> int:
        if not 1 <= v <= 10_000_000:
            raise ValueError("la cantidad tiene que ser un entero entre 1 y 10.000.000")
        return v

    @field_validator("precio_promedio")
    @classmethod
    def _precio(cls, v: Decimal) -> Decimal:
        if v < 0 or v > MAXIMO or v.as_tuple().exponent < -4:
            raise ValueError("el precio promedio tiene que estar entre 0 y 1.000.000.000.000, con hasta 4 decimales")
        return v


class UpdateTenenciaSchema(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _sin_nulos(cls, datos):
        return sin_nulos(datos)

    cantidad: int | None = None
    precio_promedio: Decimal | None = None

    @field_validator("cantidad")
    @classmethod
    def _cantidad(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("la cantidad tiene que ser un entero mayor a 0 (para sacarla, borrá la tenencia)")
        return v

    @field_validator("precio_promedio")
    @classmethod
    def _precio(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("el precio promedio no puede ser negativo")
        return v

    @model_validator(mode="after")
    def _alguno(self):
        return _algo(self)


# ---------- Dividendos ----------
class UpdateDividendoSchema(BaseModel):
    """Corrige el registro del dividendo (no vuelve a pagar ni descuenta lo ya acreditado)."""

    @model_validator(mode="before")
    @classmethod
    def _sin_nulos(cls, datos):
        return sin_nulos(datos)

    monto_por_unidad: Decimal | None = None
    fecha_pago: date | None = None

    @field_validator("monto_por_unidad")
    @classmethod
    def _monto(cls, v: Decimal | None) -> Decimal | None:
        return None if v is None else _positivo(v, "el monto por unidad", 4)

    @model_validator(mode="after")
    def _alguno(self):
        return _algo(self)


# ---------- Favoritos ----------
class FavoritoSchema(BaseModel):
    inversor_id: int
    activo_id: int


# ---------- Panel ----------
class TransferenciaPanelSchema(BaseModel):
    tipo: TipoTransferencia
    moneda: Moneda
    monto: Decimal

    @field_validator("monto")
    @classmethod
    def _monto(cls, v: Decimal) -> Decimal:
        return _positivo(v, "el monto", 2)


class OrdenPanelSchema(OrdenSchema):
    tipo: TipoOperacion
