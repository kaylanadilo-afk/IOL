"""Panel de inversiones: atajos que juntan en una sola llamada lo que una pantalla necesita
(los mismos que trae el backend InitialStructure). Usan los mismos servicios que el resto de la API."""
from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.dtos.broker_dto import ActivoDTO, DividendoDTO, InversorDTO, MovimientoDTO, OperacionDTO
from src.mappers.broker_mapper import to_json
from src.schemas.broker_schema import CreateDividendoSchema, CreateInversorSchema
from src.schemas.registros_schema import OrdenPanelSchema, TransferenciaPanelSchema
from src.services.activo_service import ActivoService
from src.services.cuenta_service import CuentaService
from src.services.inversor_service import InversorService
from src.services.operacion_service import OperacionService
from src.services.registros_service import RegistrosService
from src.utils.autorizacion import solo_admin
from src.utils.mercado import estado_mercado, get_ahora

router = APIRouter(prefix="/panel", tags=["Panel de inversiones"])


@router.get("/mercado", summary="Si el mercado está abierto y el horario de operación")
def mercado(ahora: datetime = Depends(get_ahora)):
    return to_json(estado_mercado(ahora))


@router.get("/inversores/{inversor_id}", response_model=InversorDTO, summary="Inversor con su cuenta comitente")
def perfil(inversor_id: int, db: Session = Depends(get_db)):
    return InversorService(db).obtener(inversor_id)


@router.post("/inversores", response_model=InversorDTO, status_code=status.HTTP_201_CREATED,
             summary="Alta de inversor (igual que POST /inversores)")
def alta(payload: CreateInversorSchema, db: Session = Depends(get_db)):
    return InversorService(db).crear(**payload.model_dump())


@router.post("/inversores/{inversor_id}/cuenta", response_model=InversorDTO,
             summary="Abrir la cuenta comitente si el inversor no tiene (admin)")
def abrir_cuenta(inversor_id: int, db: Session = Depends(get_db), _=Depends(solo_admin)):
    RegistrosService(db).crear_cuenta(inversor_id)
    return InversorService(db).obtener(inversor_id)


@router.get("/activos", response_model=list[ActivoDTO])
def activos(db: Session = Depends(get_db)):
    return ActivoService(db).listar(None, None)


@router.get("/cuentas/{cuenta_id}/cartera")
def cartera(cuenta_id: int, db: Session = Depends(get_db)):
    return CuentaService(db).cartera(cuenta_id)


@router.get("/cuentas/{cuenta_id}/actividad", summary="Movimientos de dinero y operaciones de la cuenta")
def actividad(cuenta_id: int, db: Session = Depends(get_db)):
    return to_json({
        "movimientos": CuentaService(db).movimientos(cuenta_id),
        "operaciones": OperacionService(db).historial(cuenta_id, None, None, None, None),
    })


@router.post("/cuentas/{cuenta_id}/movimientos", response_model=MovimientoDTO, status_code=status.HTTP_201_CREATED)
def transferir(cuenta_id: int, payload: TransferenciaPanelSchema, db: Session = Depends(get_db)):
    return RegistrosService(db).crear_movimiento(cuenta_id, payload.tipo, payload.moneda, payload.monto)


@router.post("/cuentas/{cuenta_id}/operaciones", response_model=OperacionDTO, status_code=status.HTTP_201_CREATED)
def operar(cuenta_id: int, payload: OrdenPanelSchema, db: Session = Depends(get_db),
           ahora: datetime = Depends(get_ahora)):
    return RegistrosService(db).crear_operacion(cuenta_id, payload.tipo, payload.cantidad, ahora,
                                                payload.activo_id, payload.ticker)


@router.post("/dividendos", response_model=DividendoDTO, status_code=status.HTTP_201_CREATED,
             summary="Pagar un dividendo (igual que POST /dividendos)")
def pagar_dividendo(payload: CreateDividendoSchema, db: Session = Depends(get_db)):
    return ActivoService(db).registrar_dividendo(payload.activo_id, payload.monto_por_unidad, payload.fecha_pago)


@router.get("/rankings", summary="Más operados de la semana y más elegidos como favoritos")
def rankings(db: Session = Depends(get_db), ahora: datetime = Depends(get_ahora)):
    servicio = ActivoService(db)
    return to_json({"mas_operados": servicio.mas_operados(ahora), "mas_favoritos": servicio.mas_favoritos()})
