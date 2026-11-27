"""Alertas de precio y avisos dentro de la app. Cada inversor maneja solo las suyas (con su sesión)."""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.dtos.broker_dto import InversorDTO
from src.mappers.broker_mapper import to_json
from src.schemas.alerta_schema import CreateAlertaSchema, EstadoAlertaSchema, UpdateAlertaSchema
from src.services.alertas_service import AlertasService
from src.utils.autorizacion import usuario_actual

router = APIRouter(prefix="/alertas", tags=["Alertas de precio"])


@router.get("", summary="Mis alertas (activas, pausadas y ejecutadas)")
def mis_alertas(db: Session = Depends(get_db), yo: InversorDTO = Depends(usuario_actual)):
    return to_json(AlertasService(db).listar(yo.id))


@router.post("", status_code=status.HTTP_201_CREATED,
             summary="Crear una alerta: sube o baja un porcentaje desde el precio actual, o llega a un precio")
def crear_alerta(payload: CreateAlertaSchema, db: Session = Depends(get_db), yo: InversorDTO = Depends(usuario_actual)):
    return to_json(AlertasService(db).crear(yo.id, payload.model_dump()))


@router.put("/{alerta_id}", summary="Editar una alerta (si cambia la condición, se toma el precio actual como referencia)")
def editar_alerta(alerta_id: int, payload: UpdateAlertaSchema, db: Session = Depends(get_db),
                  yo: InversorDTO = Depends(usuario_actual)):
    return to_json(AlertasService(db).actualizar(alerta_id, yo.id, payload.model_dump(exclude_unset=True)))


@router.patch("/{alerta_id}/estado", summary="Pausar o reactivar una alerta")
def estado_alerta(alerta_id: int, payload: EstadoAlertaSchema, db: Session = Depends(get_db),
                  yo: InversorDTO = Depends(usuario_actual)):
    return to_json(AlertasService(db).cambiar_estado(alerta_id, yo.id, payload.estado))


@router.delete("/{alerta_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def borrar_alerta(alerta_id: int, db: Session = Depends(get_db), yo: InversorDTO = Depends(usuario_actual)):
    AlertasService(db).borrar(alerta_id, yo.id)


notificaciones = APIRouter(prefix="/notificaciones", tags=["Alertas de precio"])


@notificaciones.get("", summary="Mis avisos (también es el historial de alertas cumplidas)")
def mis_notificaciones(db: Session = Depends(get_db), yo: InversorDTO = Depends(usuario_actual)):
    return to_json(AlertasService(db).notificaciones(yo.id))


@notificaciones.post("/leidas", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
                     summary="Marcar todos los avisos como leídos")
def leer_todas(db: Session = Depends(get_db), yo: InversorDTO = Depends(usuario_actual)):
    AlertasService(db).marcar_leidas(yo.id)


@notificaciones.post("/{notificacion_id}/leida", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def leer_una(notificacion_id: int, db: Session = Depends(get_db), yo: InversorDTO = Depends(usuario_actual)):
    AlertasService(db).marcar_leidas(yo.id, notificacion_id)
