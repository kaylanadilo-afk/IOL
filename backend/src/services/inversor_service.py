import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models.cuenta_model import Cuenta
from src.db.models.inversor_model import Inversor
from src.dtos.broker_dto import ActivoDTO, InversorDTO, PasswordCambiadaDTO, SesionDTO
from src.mappers.broker_mapper import to_activos, to_inversor
from src.repositories.broker_repository import CuentaRepository, InversorRepository
from src.services.activo_service import obtener_activo
from src.utils import correo, seguridad
from src.utils.errors import BusinessError, ConflictError, EmailNoVerificadoError, UnauthorizedError, no_encontrado

MINUTOS_CODIGO = 15      # vigencia del código
ESPERA_REENVIO = 60      # segundos entre envíos
MAX_INTENTOS = 5


def _utc(d: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona horaria: se toman como UTC."""
    return d.replace(tzinfo=timezone.utc) if d and d.tzinfo is None else d


def verificacion_activada() -> bool:
    """Con VERIFICAR_EMAIL=0 (tests) las cuentas quedan confirmadas al crearse."""
    return os.getenv("VERIFICAR_EMAIL", "1") != "0"


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
                                     es_admin=es_admin, password_hash=seguridad.hashear(password),
                                     email_verificado=es_admin or not verificacion_activada()))
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
        if not inv.email_verificado:
            self._mandar_codigo(inv)
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
        if not inv.email_verificado:
            # Si el código anterior venció, se manda uno nuevo
            if not inv.codigo_expira or _utc(inv.codigo_expira) < datetime.now(timezone.utc):
                self._mandar_codigo(inv)
            raise EmailNoVerificadoError()
        return SesionDTO(token=seguridad.crear_token(inv.id, inv.password_hash), inversor=to_inversor(inv))

    # ---------- Confirmación del correo ----------
    def _mandar_codigo(self, inv: Inversor) -> None:
        codigo = f"{secrets.randbelow(10**6):06d}"
        ahora = datetime.now(timezone.utc)
        inv.codigo_hash = seguridad.hash_codigo(inv.id, codigo)
        inv.codigo_expira = ahora + timedelta(minutes=MINUTOS_CODIGO)
        inv.codigo_enviado = ahora
        inv.codigo_intentos = 0
        self.db.commit()
        asunto, texto, html = correo.mail_codigo(inv.nombre.split(" ")[0], codigo, MINUTOS_CODIGO)
        correo.despachar(inv.email, asunto, texto, html)

    def reenviar_codigo(self, email: str) -> dict:
        inv = self.repo.find_by_email(email.strip().lower())
        # Misma respuesta si la cuenta no existe o ya está confirmada: no revela qué correos hay
        if inv and not inv.email_verificado:
            if inv.codigo_enviado:
                pasaron = (datetime.now(timezone.utc) - _utc(inv.codigo_enviado)).total_seconds()
                if pasaron < ESPERA_REENVIO:
                    return {"ok": True, "espera": int(ESPERA_REENVIO - pasaron) + 1}
            self._mandar_codigo(inv)
        return {"ok": True, "espera": ESPERA_REENVIO}

    def verificar_email(self, email: str, codigo: str) -> SesionDTO:
        inv = self.repo.find_by_email(email.strip().lower())
        if not inv or inv.email_verificado or not inv.codigo_hash:
            raise BusinessError("El código no es válido. Pedí uno nuevo.", campo="codigo")
        if inv.codigo_intentos >= MAX_INTENTOS:
            raise BusinessError("Superaste los intentos. Pedí un código nuevo.", campo="codigo")
        if inv.codigo_expira and _utc(inv.codigo_expira) < datetime.now(timezone.utc):
            raise BusinessError("El código venció. Pedí uno nuevo.", campo="codigo")
        if not secrets.compare_digest(inv.codigo_hash, seguridad.hash_codigo(inv.id, codigo.strip())):
            inv.codigo_intentos += 1
            self.db.commit()
            quedan = MAX_INTENTOS - inv.codigo_intentos
            raise BusinessError("El código no es correcto." + (f" Te quedan {quedan} intentos." if quedan else " Pedí uno nuevo."),
                                campo="codigo")
        inv.email_verificado = True
        inv.codigo_hash = inv.codigo_expira = None
        inv.codigo_intentos = 0
        self.db.commit()
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
