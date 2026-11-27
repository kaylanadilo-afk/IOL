"""Permisos de los endpoints de administración (editar y borrar registros a mano)."""
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.dtos.broker_dto import InversorDTO
from src.services.inversor_service import InversorService
from src.utils.errors import ForbiddenError


def solo_admin(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> InversorDTO:
    """Exige la sesión de un administrador (header Authorization: Bearer <token>)."""
    inversor = InversorService(db).de_token((authorization or "").removeprefix("Bearer ").strip())
    if not inversor.es_admin:
        raise ForbiddenError("Solo un administrador puede hacer este cambio.")
    return inversor


def usuario_actual(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> InversorDTO:
    """Inversor de la sesión (header Authorization: Bearer <token>). Cada uno ve solo lo suyo."""
    return InversorService(db).de_token((authorization or "").removeprefix("Bearer ").strip())
