from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models.cuenta_model import Cuenta
from src.db.models.inversor_model import Inversor
from src.dtos.broker_dto import ActivoDTO, InversorDTO, PasswordCambiadaDTO, SesionDTO
from src.mappers.broker_mapper import to_activos, to_inversor
from src.repositories.broker_repository import CuentaRepository, InversorRepository
from src.services.activo_service import obtener_activo
from src.utils import seguridad
from src.utils.errors import BusinessError, ConflictError, UnauthorizedError, no_encontrado


def obtener_inversor(db: Session, inversor_id: int) -> Inversor:
    inv = InversorRepository(db).find_by_id(inversor_id)
    if not inv:
        raise no_encontrado("Inversor")
    return inv


class InversorService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InversorRepository(db)
        self.cuentas = CuentaRepository(db)

    # ---------- HU1: alta de inversor y cuenta comitente ----------
    def crear(self, email: str, nombre: str, cuit: str, perfil_riesgo: str, password: str,
              es_admin: bool = False) -> InversorDTO:
        if self.repo.find_by_email(email):
            raise ConflictError("Ya existe una cuenta con este correo", campo="email")
        if self.repo.find_by_cuit(cuit):
            raise ConflictError("Ya existe una cuenta con este CUIT", campo="cuit")
        inv = self.repo.add(Inversor(email=email, nombre=nombre, cuit=cuit, perfil_riesgo=perfil_riesgo,
                                     es_admin=es_admin, password_hash=seguridad.hashear(password)))
        siguiente = (self.cuentas.max_numero_comitente() or 100000) + 1
        self.cuentas.add(Cuenta(inversor_id=inv.id, numero_comitente=siguiente,
                                saldo_ars=Decimal("0"), saldo_usd=Decimal("0")))
        try:
            self.cuentas.flush()
        except IntegrityError:  # carrera con otra alta simultánea
            self.db.rollback()
            raise ConflictError("No se pudo crear la cuenta, reintentá")
        self.cuentas.refresh(inv)
        self.db.commit()
        return to_inversor(inv)

    def obtener(self, inversor_id: int) -> InversorDTO:
        return to_inversor(obtener_inversor(self.db, inversor_id))

    def actualizar_perfil(self, inversor_id: int, perfil_riesgo: str) -> InversorDTO:
        inv = obtener_inversor(self.db, inversor_id)
        inv.perfil_riesgo = perfil_riesgo
        self.db.commit()
        return to_inversor(inv)

    # ---------- Contraseñas y sesión ----------
    def ingresar(self, email: str, password: str) -> SesionDTO:
        inv = self.repo.find_by_email(email.strip().lower())
        # Mismo mensaje si el email no existe o la contraseña es incorrecta: no revela qué cuentas hay
        if not inv or not seguridad.verificar(password, inv.password_hash):
            raise UnauthorizedError("Email o contraseña incorrectos.")
        return SesionDTO(token=seguridad.crear_token(inv.id, inv.password_hash), inversor=to_inversor(inv))

    def de_token(self, token: str | None) -> InversorDTO:
        datos = seguridad.leer_token(token or "")
        inv = self.repo.find_by_id(datos["id"]) if datos else None
        if not inv or (inv.password_hash or "")[-12:] != datos.get("v"):
            raise UnauthorizedError("La sesión venció. Volvé a ingresar.")
        return to_inversor(inv)

    def cambiar_password(self, inversor_id: int, actual: str, nueva: str) -> PasswordCambiadaDTO:
        inv = obtener_inversor(self.db, inversor_id)
        if not seguridad.verificar(actual, inv.password_hash):
            raise UnauthorizedError("La contraseña actual no es correcta.")
        if actual == nueva:
            raise BusinessError("La contraseña nueva tiene que ser distinta de la actual.")
        inv.password_hash = seguridad.hashear(nueva)
        self.db.commit()
        # Las sesiones abiertas con la contraseña anterior dejan de valer; esta sigue con un token nuevo
        return PasswordCambiadaDTO(token=seguridad.crear_token(inv.id, inv.password_hash))

    # ---------- Favoritos ----------
    def favoritos(self, inversor_id: int) -> list[ActivoDTO]:
        return to_activos(obtener_inversor(self.db, inversor_id).favoritos)

    def agregar_favorito(self, inversor_id: int, activo_id: int) -> list[ActivoDTO]:
        inv = obtener_inversor(self.db, inversor_id)
        activo = obtener_activo(self.db, activo_id)
        if activo not in inv.favoritos:
            inv.favoritos.append(activo)
        self.db.commit()
        return to_activos(inv.favoritos)

    def quitar_favorito(self, inversor_id: int, activo_id: int) -> list[ActivoDTO]:
        inv = obtener_inversor(self.db, inversor_id)
        activo = obtener_activo(self.db, activo_id)
        if activo in inv.favoritos:
            inv.favoritos.remove(activo)
        self.db.commit()
        return to_activos(inv.favoritos)
