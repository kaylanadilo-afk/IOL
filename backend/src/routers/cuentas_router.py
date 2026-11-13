from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.dtos.broker_dto import CuentaDTO, MepDTO, MovimientoDTO, OperacionDTO
from src.schemas.broker_schema import MepSchema, MontoMonedaSchema, OrdenSchema, TipoOperacion
from src.services import historial_service
from src.services.cuenta_service import CuentaService
from src.services.operacion_service import OperacionService
from src.utils.mercado import get_ahora

router = APIRouter(prefix="/cuentas", tags=["Cuentas"])


@router.get("/{cuenta_id}", response_model=CuentaDTO)
def ver_cuenta(cuenta_id: int, db: Session = Depends(get_db)):
    return CuentaService(db).obtener(cuenta_id)


# ---------- HU3: plata ----------
@router.post("/{cuenta_id}/depositos", response_model=MovimientoDTO, status_code=status.HTTP_201_CREATED)
def depositar(cuenta_id: int, payload: MontoMonedaSchema, db: Session = Depends(get_db)):
    return CuentaService(db).depositar(cuenta_id, payload.moneda, payload.monto)


@router.post("/{cuenta_id}/extracciones", response_model=MovimientoDTO, status_code=status.HTTP_201_CREATED)
def extraer(cuenta_id: int, payload: MontoMonedaSchema, db: Session = Depends(get_db)):
    return CuentaService(db).extraer(cuenta_id, payload.moneda, payload.monto)


@router.get("/{cuenta_id}/movimientos", response_model=list[MovimientoDTO])
def ver_movimientos(cuenta_id: int, db: Session = Depends(get_db)):
    return CuentaService(db).movimientos(cuenta_id)


# ---------- HU4 / HU5 / HU6 / HU7: operaciones ----------
@router.post("/{cuenta_id}/compras", response_model=OperacionDTO, status_code=status.HTTP_201_CREATED,
             tags=["Operaciones"])
def comprar(cuenta_id: int, orden: OrdenSchema, db: Session = Depends(get_db), ahora: datetime = Depends(get_ahora)):
    return OperacionService(db).comprar(cuenta_id, orden.cantidad, ahora, orden.activo_id, orden.ticker)


@router.post("/{cuenta_id}/ventas", response_model=OperacionDTO, status_code=status.HTTP_201_CREATED,
             tags=["Operaciones"])
def vender(cuenta_id: int, orden: OrdenSchema, db: Session = Depends(get_db), ahora: datetime = Depends(get_ahora)):
    return OperacionService(db).vender(cuenta_id, orden.cantidad, ahora, orden.activo_id, orden.ticker)


@router.post("/{cuenta_id}/mep", response_model=MepDTO, status_code=status.HTTP_201_CREATED, tags=["Operaciones"])
def mep(cuenta_id: int, payload: MepSchema, db: Session = Depends(get_db), ahora: datetime = Depends(get_ahora)):
    return OperacionService(db).dolar_mep(cuenta_id, payload.monto_ars, ahora)


# ---------- HU10 / HU11 / HU12: reportes ----------
@router.get("/{cuenta_id}/cartera")
def ver_cartera(cuenta_id: int, db: Session = Depends(get_db)):
    return CuentaService(db).cartera(cuenta_id)


@router.get("/{cuenta_id}/operaciones", tags=["Operaciones"])
def ver_operaciones(cuenta_id: int, desde: date | None = None, hasta: date | None = None,
                    tipo: TipoOperacion | None = None, ticker: str | None = Query(None, max_length=12),
                    db: Session = Depends(get_db)):
    return OperacionService(db).historial(cuenta_id, desde, hasta, tipo, ticker)


@router.get("/{cuenta_id}/ganancias-realizadas", tags=["Rankings"])
def ver_ganancias(cuenta_id: int, db: Session = Depends(get_db)):
    return CuentaService(db).ganancias_realizadas(cuenta_id)


@router.get("/{cuenta_id}/evolucion", tags=["Gráficos"],
            summary="Valor de las tenencias actuales en los últimos N días (con los cierres diarios)")
def ver_evolucion(cuenta_id: int, dias: int = Query(90, ge=7, le=400), db: Session = Depends(get_db),
                  ahora: datetime = Depends(get_ahora)):
    return historial_service.evolucion_cartera(db, cuenta_id, dias, historial_service.fecha_ar(ahora))
