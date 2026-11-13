"""Model ⇄ DTO del broker."""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from src.db.models.activo_model import Activo
from src.db.models.cuenta_model import Cuenta, Movimiento
from src.db.models.inversor_model import Inversor
from src.db.models.operacion_model import Operacion
from src.dtos.broker_dto import ActivoDTO, CuentaDTO, InversorDTO, MovimientoDTO, OperacionDTO


def to_inversor(inv: Inversor) -> InversorDTO:
    return InversorDTO.model_validate(inv)


def to_cuenta(cuenta: Cuenta) -> CuentaDTO:
    return CuentaDTO.model_validate(cuenta)


def to_activo(activo: Activo) -> ActivoDTO:
    return ActivoDTO.model_validate(activo)


def to_activos(activos: list[Activo]) -> list[ActivoDTO]:
    return [to_activo(a) for a in activos]


def to_movimiento(mov: Movimiento) -> MovimientoDTO:
    return MovimientoDTO.model_validate(mov)


def to_operacion(op: Operacion) -> OperacionDTO:
    return OperacionDTO(
        id=op.id, cuenta_id=op.cuenta_id, activo_id=op.activo_id, ticker=op.activo.ticker,
        moneda=op.activo.moneda, tipo=op.tipo, cantidad=op.cantidad, precio_unitario=op.precio_unitario,
        comision=op.comision, total=op.total, fecha=op.fecha, estado=op.estado,
        ganancia_realizada=op.ganancia_realizada,
    )


def to_json(obj):
    """Respuestas armadas como dict (reportes): Decimal -> float, fechas -> ISO, DTOs -> dict."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_json(v) for v in obj]
    return obj
