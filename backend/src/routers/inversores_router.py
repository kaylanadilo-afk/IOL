from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.utils.autorizacion import inversor_autorizado
from src.dtos.broker_dto import ActivoDTO, InversorDTO, PasswordCambiadaDTO
from src.schemas.broker_schema import CambiarPasswordSchema, ConfirmarPasswordSchema, CreateInversorSchema, UpdatePerfilSchema
from src.services.inversor_service import InversorService
from src.utils import limites
from src.utils.validaciones import validar_email

router = APIRouter(prefix="/inversores", tags=["Inversores"])


@router.post("", response_model=InversorDTO, status_code=status.HTTP_201_CREATED)
def alta_inversor(payload: CreateInversorSchema, db: Session = Depends(get_db)):
    """HU1: alta de inversor + cuenta comitente con saldos en 0."""
    return InversorService(db).crear(**payload.model_dump())


class ValidarEmailSchema(BaseModel):
    email: str


@router.post("/validar-email", summary="Revisa si un correo tiene formato válido y un dominio que recibe emails")
def validar_email_alta(payload: ValidarEmailSchema, request: Request):
    """Lo usa el formulario de alta para avisar del error apenas se completa el campo."""
    # Consulta servidores de correo de terceros: tope por IP para que no se use para saturarlos
    limites.VALIDAR_EMAIL.consumir(request.client.host if request.client else "?")
    try:
        return {"valido": True, "email": validar_email(payload.email), "mensaje": None}
    except ValueError as e:
        return {"valido": False, "email": payload.email, "mensaje": str(e)}


@router.get("/{inversor_id}", response_model=InversorDTO)
def ver_inversor(inversor_id: int, db: Session = Depends(get_db), _yo=Depends(inversor_autorizado)):
    return InversorService(db).obtener(inversor_id)


@router.patch("/{inversor_id}/perfil", response_model=InversorDTO)
def actualizar_perfil(inversor_id: int, payload: UpdatePerfilSchema, db: Session = Depends(get_db), _yo=Depends(inversor_autorizado)):
    """HU5: cambia el perfil de riesgo."""
    return InversorService(db).actualizar_perfil(inversor_id, payload.perfil_riesgo)


@router.post("/{inversor_id}/password", tags=["Sesión"],
             summary="Paso 1: pedir el cambio de contraseña (pide la actual y manda un código al correo)")
def cambiar_password(inversor_id: int, payload: CambiarPasswordSchema, db: Session = Depends(get_db), _yo=Depends(inversor_autorizado)):
    return InversorService(db).solicitar_cambio_password(inversor_id, payload.actual, payload.nueva)


@router.post("/{inversor_id}/password/confirmar", response_model=PasswordCambiadaDTO, tags=["Sesión"],
             summary="Paso 2: confirmar el cambio de contraseña con el código del correo. Devuelve un token nuevo")
def confirmar_password(inversor_id: int, payload: ConfirmarPasswordSchema, db: Session = Depends(get_db),
                       _yo=Depends(inversor_autorizado)):
    return InversorService(db).confirmar_cambio_password(inversor_id, payload.codigo)


@router.get("/{inversor_id}/favoritos", response_model=list[ActivoDTO], tags=["Favoritos"])
def ver_favoritos(inversor_id: int, db: Session = Depends(get_db), _yo=Depends(inversor_autorizado)):
    return InversorService(db).favoritos(inversor_id)


@router.post("/{inversor_id}/favoritos/{activo_id}", response_model=list[ActivoDTO], tags=["Favoritos"])
def marcar_favorito(inversor_id: int, activo_id: int, db: Session = Depends(get_db), _yo=Depends(inversor_autorizado)):
    return InversorService(db).agregar_favorito(inversor_id, activo_id)


@router.delete("/{inversor_id}/favoritos/{activo_id}", response_model=list[ActivoDTO], tags=["Favoritos"])
def desmarcar_favorito(inversor_id: int, activo_id: int, db: Session = Depends(get_db), _yo=Depends(inversor_autorizado)):
    return InversorService(db).quitar_favorito(inversor_id, activo_id)
