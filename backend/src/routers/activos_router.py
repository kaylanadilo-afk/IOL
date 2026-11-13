from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.dtos.broker_dto import ActivoDTO, DividendoDTO
from src.schemas.broker_schema import (CreateActivoSchema, CreateDividendoSchema, Moneda, TipoActivo,
                                       UpdateEstadoSchema, UpdatePrecioSchema)
from src.services import historial_service
from src.services.activo_service import ActivoService
from src.utils.mercado import get_ahora

router = APIRouter(prefix="/activos", tags=["Activos"])
dividendos_router = APIRouter(prefix="/dividendos", tags=["Activos (admin)"])


# ---------- HU2: catálogo ----------
@router.post("", response_model=ActivoDTO, status_code=status.HTTP_201_CREATED, tags=["Activos (admin)"])
def alta_activo(payload: CreateActivoSchema, db: Session = Depends(get_db)):
    return ActivoService(db).crear(**payload.model_dump())


@router.get("", response_model=list[ActivoDTO])
def listar_activos(tipo: TipoActivo | None = None, moneda: Moneda | None = None, db: Session = Depends(get_db)):
    return ActivoService(db).listar(tipo, moneda)


# Las rutas fijas van antes de /activos/{activo_id}
@router.get("/sparklines", tags=["Gráficos"], summary="Cierres recientes de todos los activos (mini gráficos)")
def ver_sparklines(dias: int = Query(30, ge=5, le=120), db: Session = Depends(get_db),
                   ahora: datetime = Depends(get_ahora)):
    return historial_service.sparklines(db, dias, historial_service.fecha_ar(ahora))


@router.get("/mas-operados", tags=["Rankings"])
def ranking_operados(db: Session = Depends(get_db), ahora: datetime = Depends(get_ahora)):
    """HU12: activos con más volumen operado en los últimos 7 días."""
    return ActivoService(db).mas_operados(ahora)


@router.get("/mas-favoritos", tags=["Rankings"])
def ranking_favoritos(db: Session = Depends(get_db)):
    return ActivoService(db).mas_favoritos()


@router.get("/{activo_id}", response_model=ActivoDTO)
def ver_activo(activo_id: int, db: Session = Depends(get_db)):
    return ActivoService(db).obtener(activo_id)


@router.get("/{activo_id}/historial", tags=["Gráficos"],
            summary="Cierres diarios de los últimos N días (por defecto 3 meses)")
def ver_historial(activo_id: int, dias: int = Query(90, ge=1, le=400), db: Session = Depends(get_db),
                  ahora: datetime = Depends(get_ahora)):
    return historial_service.historial_diario(db, activo_id, dias, historial_service.fecha_ar(ahora))


@router.get("/{activo_id}/intradia", tags=["Gráficos"],
            summary="Precio a lo largo de un día (por defecto, el último día con datos)")
def ver_intradia(activo_id: int, fecha: date | None = None, db: Session = Depends(get_db)):
    return historial_service.intradia(db, activo_id, fecha)


# ---------- HU8: precio y suspensión ----------
@router.patch("/{activo_id}/precio", response_model=ActivoDTO, tags=["Activos (admin)"])
def actualizar_precio(activo_id: int, payload: UpdatePrecioSchema, db: Session = Depends(get_db),
                      ahora: datetime = Depends(get_ahora)):
    return ActivoService(db).actualizar_precio(activo_id, payload.precio, ahora)


@router.patch("/{activo_id}/estado", response_model=ActivoDTO, tags=["Activos (admin)"],
              summary="Suspender (activo=false) o habilitar un activo")
def actualizar_estado(activo_id: int, payload: UpdateEstadoSchema, db: Session = Depends(get_db)):
    return ActivoService(db).actualizar_estado(activo_id, payload.activo)


# ---------- HU9: dividendos ----------
@dividendos_router.post("", response_model=DividendoDTO, status_code=status.HTTP_201_CREATED)
def pagar_dividendo(payload: CreateDividendoSchema, db: Session = Depends(get_db)):
    return ActivoService(db).registrar_dividendo(payload.activo_id, payload.monto_por_unidad, payload.fecha_pago)
