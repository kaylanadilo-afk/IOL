"""DTOs de salida del broker: es lo único que llega al cliente (nunca un Model)."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer

# Los montos se manejan como Decimal y se devuelven como número en el JSON
Dinero = Annotated[Decimal, PlainSerializer(float, return_type=float)]
# Las fechas se guardan en UTC; si el driver las devuelve sin zona se la agregamos
Fecha = Annotated[datetime, AfterValidator(lambda d: d if d.tzinfo else d.replace(tzinfo=timezone.utc))]


class OrmDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CuentaDTO(OrmDTO):
    id: int
    inversor_id: int
    numero_comitente: int
    saldo_ars: Dinero
    saldo_usd: Dinero


class InversorDTO(OrmDTO):
    id: int
    email: str
    nombre: str
    cuit: str
    perfil_riesgo: str
    fecha_alta: Fecha
    es_admin: bool = False
    email_verificado: bool = True
    cuenta: CuentaDTO | None = None


class SesionDTO(BaseModel):
    token: str
    inversor: InversorDTO


class PasswordCambiadaDTO(BaseModel):
    ok: bool = True
    token: str


class ActivoDTO(OrmDTO):
    id: int
    ticker: str
    nombre: str
    tipo: str
    moneda: str
    precio_actual: Dinero
    nivel_riesgo: int
    activo: bool
    variacion_pct: Dinero | None = None
    precio_actualizado: Fecha | None = None


class MovimientoDTO(OrmDTO):
    id: int
    cuenta_id: int
    tipo: str
    moneda: str
    monto: Dinero
    fecha: Fecha
    descripcion: str


class OperacionDTO(BaseModel):
    id: int
    cuenta_id: int
    activo_id: int
    ticker: str
    moneda: str
    tipo: str
    cantidad: int
    precio_unitario: Dinero
    comision: Dinero
    total: Dinero
    fecha: Fecha
    estado: str
    ganancia_realizada: Dinero | None = None


class MepDTO(BaseModel):
    tipo_cambio: Dinero
    cantidad_nominales: int
    pesos_debitados: Dinero
    dolares_acreditados: Dinero
    compra: OperacionDTO
    venta: OperacionDTO


class DividendoDTO(BaseModel):
    id: int
    activo_id: int
    ticker: str
    moneda: str
    monto_por_unidad: Dinero
    fecha_pago: date
    cuentas_acreditadas: int
    total_pagado: Dinero


# ---------- Registros (alta, edición y baja de cada tabla) ----------
class TenenciaDTO(OrmDTO):
    cuenta_id: int
    activo_id: int
    cantidad: int
    precio_promedio: Dinero


class FavoritoDTO(BaseModel):
    inversor_id: int
    activo_id: int
    fecha_agregado: Fecha | None = None


class DividendoRegistroDTO(OrmDTO):
    id: int
    activo_id: int
    monto_por_unidad: Dinero
    fecha_pago: date
