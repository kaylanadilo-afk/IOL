from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.dtos.auth_dto import LoginDTO, TokenDTO
from src.dtos.broker_dto import InversorDTO, SesionDTO
from src.schemas.auth_schema import LoginSchema, TokenSchema
from src.schemas.broker_schema import IngresarSchema, OlvideCambiarSchema, OlvideSchema, OlvideVerificarSchema
from src.services.auth_service import AuthService
from src.services.inversor_service import InversorService
from src.utils import limites

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenSchema)
def login(payload: LoginSchema, db: Session = Depends(get_db)):
    dto = LoginDTO(**payload.model_dump())
    token: TokenDTO = AuthService(db).login(dto)
    return TokenSchema(**token.model_dump())


# ---------- Sesión del broker (inversores) ----------
@router.post("/ingresar", response_model=SesionDTO, tags=["Sesión"],
             summary="Ingresar con email y contraseña. Devuelve un token de sesión")
def ingresar(payload: IngresarSchema, db: Session = Depends(get_db)):
    return InversorService(db).ingresar(payload.email, payload.password)


class VerificarEmailSchema(BaseModel):
    email: str
    codigo: str


class ReenviarCodigoSchema(BaseModel):
    email: str


@router.post("/verificar-email", response_model=SesionDTO, tags=["Sesión"],
             summary="Confirma el correo con el código de 6 dígitos y abre la sesión")
def verificar_email(payload: VerificarEmailSchema, db: Session = Depends(get_db)):
    return InversorService(db).verificar_email(payload.email, payload.codigo)


@router.post("/reenviar-codigo", tags=["Sesión"], summary="Manda otro código de verificación (uno por minuto)")
def reenviar_codigo(payload: ReenviarCodigoSchema, db: Session = Depends(get_db)):
    return InversorService(db).reenviar_codigo(payload.email)


# ---------- Olvidé mi contraseña (sin sesión) ----------
@router.post("/olvide", tags=["Sesión"],
             summary="Olvidé mi contraseña, paso 1: manda un código al correo (si tiene cuenta)")
def olvide(payload: OlvideSchema, request: Request, db: Session = Depends(get_db)):
    limites.OLVIDE_IP.consumir(request.client.host if request.client else "?")
    return InversorService(db).olvide_pedir_codigo(payload.email)


@router.post("/olvide/verificar", tags=["Sesión"],
             summary="Olvidé mi contraseña, paso 2: confirma el código y devuelve un permiso para elegir la nueva")
def olvide_verificar(payload: OlvideVerificarSchema, db: Session = Depends(get_db)):
    return InversorService(db).olvide_verificar_codigo(payload.email, payload.codigo)


@router.post("/olvide/cambiar", response_model=SesionDTO, tags=["Sesión"],
             summary="Olvidé mi contraseña, paso 3: guarda la nueva con el permiso y abre la sesión")
def olvide_cambiar(payload: OlvideCambiarSchema, db: Session = Depends(get_db)):
    return InversorService(db).olvide_cambiar(payload.email, payload.permiso, payload.nueva)


@router.get("/yo", response_model=InversorDTO, tags=["Sesión"],
            summary="Inversor de la sesión actual (header Authorization: Bearer <token>)")
def yo(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    token = (authorization or "").removeprefix("Bearer ").strip()
    return InversorService(db).de_token(token)
