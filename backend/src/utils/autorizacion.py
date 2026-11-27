"""Permisos de la API.

- `usuario_actual`: exige una sesión válida (header Authorization: Bearer <token>).
- `cuenta_autorizada` / `inversor_autorizado`: además, el id del path tiene que ser del usuario de la sesión
  (o un administrador). Así nadie puede ver ni mover la plata de otra cuenta cambiando el número en la URL.
- `solo_admin`: endpoints de administración (precios, activos, dividendos, correcciones manuales).
"""
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.db.models.cuenta_model import Cuenta
from src.dtos.broker_dto import InversorDTO
from src.services.inversor_service import InversorService
from src.utils.errors import ForbiddenError, no_encontrado


def usuario_actual(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> InversorDTO:
    """Inversor de la sesión (header Authorization: Bearer <token>). Cada uno ve solo lo suyo."""
    return InversorService(db).de_token((authorization or "").removeprefix("Bearer ").strip())


def solo_admin(yo: InversorDTO = Depends(usuario_actual)) -> InversorDTO:
    """Exige la sesión de un administrador."""
    if not yo.es_admin:
        raise ForbiddenError("Solo un administrador puede hacer este cambio.")
    return yo


def verificar_cuenta(db: Session, cuenta_id: int, yo: InversorDTO) -> None:
    """La cuenta tiene que existir y ser del usuario de la sesión (o el usuario es administrador)."""
    cuenta = db.get(Cuenta, cuenta_id)
    if cuenta is None:
        raise no_encontrado("Cuenta")
    if cuenta.inversor_id != yo.id and not yo.es_admin:
        raise ForbiddenError("No tenés acceso a esta cuenta.")


def verificar_inversor(inversor_id: int, yo: InversorDTO) -> None:
    if inversor_id != yo.id and not yo.es_admin:
        raise ForbiddenError("No tenés acceso a los datos de otro inversor.")


def cuenta_autorizada(cuenta_id: int, yo: InversorDTO = Depends(usuario_actual),
                      db: Session = Depends(get_db)) -> InversorDTO:
    """Para rutas con {cuenta_id}: la cuenta es de quien llama."""
    verificar_cuenta(db, cuenta_id, yo)
    return yo


def inversor_autorizado(inversor_id: int, yo: InversorDTO = Depends(usuario_actual)) -> InversorDTO:
    """Para rutas con {inversor_id}: el inversor es quien llama."""
    verificar_inversor(inversor_id, yo)
    return yo
