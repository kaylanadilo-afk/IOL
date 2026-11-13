from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.dtos.auth_dto import LoginDTO, TokenDTO
from src.dtos.broker_dto import InversorDTO, SesionDTO
from src.schemas.auth_schema import LoginSchema, TokenSchema
from src.schemas.broker_schema import IngresarSchema
from src.services.auth_service import AuthService
from src.services.inversor_service import InversorService

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


@router.get("/yo", response_model=InversorDTO, tags=["Sesión"],
            summary="Inversor de la sesión actual (header Authorization: Bearer <token>)")
def yo(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    token = (authorization or "").removeprefix("Bearer ").strip()
    return InversorService(db).de_token(token)
