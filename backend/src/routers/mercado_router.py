from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.mappers.broker_mapper import to_json
from src.services import historial_service, precios_service
from src.services.activo_service import tipo_cambio_mep
from src.utils.errors import AppError
from src.utils.mercado import estado_mercado, get_ahora

router = APIRouter(prefix="/mercado", tags=["Mercado"])


@router.get("/estado")
def mercado_estado(ahora: datetime = Depends(get_ahora)):
    """Si el mercado está abierto y cómo está la sincronización de precios e historial."""
    return to_json({**estado_mercado(ahora), "precios": precios_service.resumen(),
                    "historial": historial_service.estado_historial})


@router.post("/sincronizar", summary="Traer ya los precios reales de data912.com (admin)")
def mercado_sincronizar(db: Session = Depends(get_db)):
    res = precios_service.sincronizar(db)
    if res["error"]:
        raise AppError(f"No se pudieron obtener los precios reales: {res['error']}", 502)
    return to_json(res)


@router.get("/dolares", summary="Cotizaciones del dólar (oficial, blue, MEP, CCL...) de dolarapi.com")
def mercado_dolares(db: Session = Depends(get_db)):
    try:
        lista = precios_service.dolares()
    except Exception as exc:
        raise AppError(f"No se pudo consultar dolarapi.com: {type(exc).__name__}", 502)
    return to_json({"cotizaciones": lista, "mep_broker_al30": tipo_cambio_mep(db)})


@router.post("/historial", tags=["Gráficos"],
             summary="Cargar ya el historial de cierres (data912) e intradiario (Yahoo) (admin)")
def cargar_historial(db: Session = Depends(get_db)):
    res = historial_service.cargar_y_registrar(db)
    if res["error"]:
        raise AppError(f"No se pudo cargar el historial: {res['error']}", 502)
    return to_json(res)
