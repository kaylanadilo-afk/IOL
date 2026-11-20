from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.dtos.broker_dto import ActivoDTO, InversorDTO, PasswordCambiadaDTO
from src.schemas.broker_schema import CambiarPasswordSchema, CreateInversorSchema, UpdatePerfilSchema
from src.services.inversor_service import InversorService
from src.utils.validaciones import validar_email

router = APIRouter(prefix="/inversores", tags=["Inversores"])


@router.post("", response_model=InversorDTO, status_code=status.HTTP_201_CREATED)
def alta_inversor(payload: CreateInversorSchema, db: Session = Depends(get_db)):
    """HU1: alta de inversor + cuenta comitente con saldos en 0."""
    return InversorService(db).crear(**payload.model_dump())


class ValidarEmailSchema(BaseModel):
    email: str


@router.post("/validar-email", summary="Revisa si un correo tiene formato válido y un dominio que recibe emails")
def validar_email_alta(payload: ValidarEmailSchema):
    """Lo usa el formulario de alta para avisar del error apenas se completa el campo."""
    try:
        return {"valido": True, "email": validar_email(payload.email), "mensaje": None}
    except ValueError as e:
        return {"valido": False, "email": payload.email, "mensaje": str(e)}


@router.get("/{inversor_id}", response_model=InversorDTO)
def ver_inversor(inversor_id: int, db: Session = Depends(get_db)):
    return InversorService(db).obtener(inversor_id)


@router.patch("/{inversor_id}/perfil", response_model=InversorDTO)
def actualizar_perfil(inversor_id: int, payload: UpdatePerfilSchema, db: Session = Depends(get_db)):
    """HU5: cambia el perfil de riesgo."""
    return InversorService(db).actualizar_perfil(inversor_id, payload.perfil_riesgo)


@router.post("/{inversor_id}/password", response_model=PasswordCambiadaDTO, tags=["Sesión"],
             summary="Cambiar la contraseña (pide la actual). Devuelve un token nuevo")
def cambiar_password(inversor_id: int, payload: CambiarPasswordSchema, db: Session = Depends(get_db)):
    return InversorService(db).cambiar_password(inversor_id, payload.actual, payload.nueva)


@router.get("/{inversor_id}/favoritos", response_model=list[ActivoDTO], tags=["Favoritos"])
def ver_favoritos(inversor_id: int, db: Session = Depends(get_db)):
    return InversorService(db).favoritos(inversor_id)


@router.post("/{inversor_id}/favoritos/{activo_id}", response_model=list[ActivoDTO], tags=["Favoritos"])
def marcar_favorito(inversor_id: int, activo_id: int, db: Session = Depends(get_db)):
    return InversorService(db).agregar_favorito(inversor_id, activo_id)


@router.delete("/{inversor_id}/favoritos/{activo_id}", response_model=list[ActivoDTO], tags=["Favoritos"])
def desmarcar_favorito(inversor_id: int, activo_id: int, db: Session = Depends(get_db)):
    return InversorService(db).quitar_favorito(inversor_id, activo_id)
