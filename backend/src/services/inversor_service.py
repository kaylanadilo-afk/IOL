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
from src.utils import correo, limites, seguridad
from src.utils.errors import BusinessError, ConflictError, EmailNoVerificadoError, UnauthorizedError, no_encontrado

MINUTOS_CODIGO = 15      # vigencia del código
ESPERA_REENVIO = 60      # segundos entre envíos
MAX_INTENTOS = 5


def _utc(d: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona horaria: se toman como UTC."""
    return d.replace(tzinfo=timezone.utc) if d and d.tzinfo is None else d


def _ocultar_email(email: str) -> str:
    """ana.perez@gmail.com -> a*******z@gmail.com (para mostrar a dónde se mandó el código)."""
    usuario, _, dominio = email.partition("@")
    if len(usuario) <= 2:
        return f"{usuario[0]}*@{dominio}"
    return f"{usuario[0]}{'*' * (len(usuario) - 2)}{usuario[-1]}@{dominio}"


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
        try:
            inv = self.repo.add(Inversor(email=email, nombre=nombre, cuit=cuit, perfil_riesgo=perfil_riesgo,
                                         es_admin=es_admin, password_hash=seguridad.hashear(password),
                                         email_verificado=es_admin or not verificacion_activada()))
            siguiente = (self.cuentas.max_numero_comitente() or 100000) + 1
            self.cuentas.add(Cuenta(inversor_id=inv.id, numero_comitente=siguiente,
                                    saldo_ars=Decimal("0"), saldo_usd=Decimal("0")))
            self.cuentas.flush()
        except IntegrityError:  # carrera con otra alta simultánea: se dice qué dato quedó repetido
            self.db.rollback()
            if self.repo.find_by_email(email):
                raise ConflictError("Ya existe una cuenta con este correo", campo="email") from None
            if self.repo.find_by_cuit(cuit):
                raise ConflictError("Ya existe una cuenta con este CUIT", campo="cuit") from None
            raise ConflictError("No se pudo crear la cuenta, reintentá") from None
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
        clave = email.strip().lower()
        # Fuerza bruta: después de 5 errores seguidos la cuenta queda frenada un rato (aun con la clave correcta)
        limites.LOGIN.verificar(clave)
        inv = self.repo.find_by_email(clave)
        # Mismo mensaje y mismo tiempo (scrypt se calcula igual) si el email no existe: no revela qué cuentas hay
        ok = seguridad.verificar(password, inv.password_hash if inv else seguridad.HASH_FALSO)
        if not inv or not ok:
            limites.LOGIN.registrar(clave)
            raise UnauthorizedError("Email o contraseña incorrectos.")
        limites.LOGIN.limpiar(clave)
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
        clave = email.strip().lower()
        inv = self.repo.find_by_email(clave)
        # Misma respuesta si la cuenta no existe o ya está confirmada: no revela qué correos hay
        if inv and not inv.email_verificado:
            if inv.codigo_enviado:
                pasaron = (datetime.now(timezone.utc) - _utc(inv.codigo_enviado)).total_seconds()
                if pasaron < ESPERA_REENVIO:
                    return {"ok": True, "espera": int(ESPERA_REENVIO - pasaron) + 1}
            limites.REENVIO.consumir(clave)  # hasta 5 correos por hora a la misma cuenta
            self._mandar_codigo(inv)
        return {"ok": True, "espera": ESPERA_REENVIO}

    def verificar_email(self, email: str, codigo: str) -> SesionDTO:
        clave = email.strip().lower()
        # Además de los 5 intentos por código, 10 errores por hora aunque se pidan códigos nuevos
        limites.CODIGO.verificar(clave)
        inv = self.repo.find_by_email(clave)
        if not inv or inv.email_verificado or not inv.codigo_hash:
            raise BusinessError("El código no es válido. Pedí uno nuevo.", campo="codigo")
        if inv.codigo_intentos >= MAX_INTENTOS:
            raise BusinessError("Superaste los intentos. Pedí un código nuevo.", campo="codigo")
        if inv.codigo_expira and _utc(inv.codigo_expira) < datetime.now(timezone.utc):
            raise BusinessError("El código venció. Pedí uno nuevo.", campo="codigo")
        if not secrets.compare_digest(inv.codigo_hash, seguridad.hash_codigo(inv.id, codigo.strip())):
            limites.CODIGO.registrar(clave)
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

    # Cambio de contraseña en tres pasos: 1) se pide un código al correo, 2) se confirma el código
    # (devuelve un permiso de un solo uso), 3) con ese permiso se elige la contraseña nueva.
    # Sirve igual con la sesión abierta (Configuración) y sin sesión ("Olvidé mi contraseña").
    def _mandar_codigo_pwd(self, inv: Inversor) -> None:
        codigo = f"{secrets.randbelow(10**6):06d}"
        inv.pwd_nueva_hash = None
        inv.pwd_codigo_hash = seguridad.hash_codigo(inv.id, "pwd:" + codigo)
        inv.pwd_codigo_expira = datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_CODIGO)
        inv.pwd_intentos = 0
        self.db.commit()
        asunto, texto, html = correo.mail_cambio_password(inv.nombre.split(" ")[0], codigo, MINUTOS_CODIGO)
        correo.despachar(inv.email, asunto, texto, html)

    def _verificar_codigo_pwd(self, inv: Inversor, codigo: str, clave: str) -> dict:
        limites.CODIGO.verificar(clave)
        if not inv.pwd_codigo_hash or inv.pwd_nueva_hash:
            raise BusinessError("No hay un código pendiente. Pedí uno nuevo.", campo="codigo")
        if inv.pwd_intentos >= MAX_INTENTOS:
            raise BusinessError("Superaste los intentos. Pedí un código nuevo.", campo="codigo")
        if inv.pwd_codigo_expira and _utc(inv.pwd_codigo_expira) < datetime.now(timezone.utc):
            raise BusinessError("El código venció. Pedí uno nuevo.", campo="codigo")
        if not secrets.compare_digest(inv.pwd_codigo_hash, seguridad.hash_codigo(inv.id, "pwd:" + codigo.strip())):
            limites.CODIGO.registrar(clave)
            inv.pwd_intentos += 1
            self.db.commit()
            quedan = MAX_INTENTOS - inv.pwd_intentos
            raise BusinessError("El código no es correcto." + (f" Te quedan {quedan} intentos." if quedan else " Pedí uno nuevo."),
                                campo="codigo")
        # El código ya no sirve más: se reemplaza por el permiso (pwd_nueva_hash marca que el código se confirmó)
        permiso = secrets.token_urlsafe(24)
        inv.pwd_codigo_hash = None
        inv.pwd_nueva_hash = seguridad.hash_codigo(inv.id, "permiso:" + permiso)
        inv.pwd_codigo_expira = datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_CODIGO)
        inv.pwd_intentos = 0
        self.db.commit()
        return {"permiso": permiso, "minutos": MINUTOS_CODIGO}

    def _aplicar_password(self, inv: Inversor, permiso: str, nueva: str) -> str:
        """Guarda la contraseña nueva si el permiso es válido. Devuelve un token nuevo (las otras sesiones se cierran)."""
        if not inv.pwd_nueva_hash or not secrets.compare_digest(
                inv.pwd_nueva_hash, seguridad.hash_codigo(inv.id, "permiso:" + permiso)):
            raise BusinessError("Primero confirmá el código que te mandamos por correo.", campo="codigo")
        if inv.pwd_codigo_expira and _utc(inv.pwd_codigo_expira) < datetime.now(timezone.utc):
            inv.pwd_nueva_hash = inv.pwd_codigo_expira = None
            self.db.commit()
            raise BusinessError("Pasó demasiado tiempo. Pedí un código nuevo.", campo="codigo")
        if seguridad.verificar(nueva, inv.password_hash):
            raise BusinessError("La contraseña nueva tiene que ser distinta de la actual.", campo="nueva")
        inv.password_hash = seguridad.hashear(nueva)
        inv.pwd_nueva_hash = inv.pwd_codigo_hash = inv.pwd_codigo_expira = None
        inv.pwd_intentos = 0
        # El código llegó a su correo: eso también confirma el correo
        inv.email_verificado = True
        self.db.commit()
        limites.CAMBIO_PASSWORD.limpiar(str(inv.id))
        limites.LOGIN.limpiar(inv.email)
        asunto, texto, html = correo.mail_password_cambiada(inv.nombre.split(" ")[0])
        correo.despachar(inv.email, asunto, texto, html)
        return seguridad.crear_token(inv.id, inv.password_hash)

    # --- Con la sesión abierta ---
    def pedir_codigo_password(self, inversor_id: int) -> dict:
        """Paso 1: manda un código al correo del inversor. Todavía no se pide ninguna contraseña."""
        inv = obtener_inversor(self.db, inversor_id)
        limites.REENVIO.consumir(f"pwd:{inversor_id}")  # hasta 5 correos por hora
        self._mandar_codigo_pwd(inv)
        return {"enviado": True, "email": _ocultar_email(inv.email), "minutos": MINUTOS_CODIGO}

    def verificar_codigo_password(self, inversor_id: int, codigo: str) -> dict:
        """Paso 2: revisa el código. Si está bien devuelve un permiso de un solo uso para elegir la contraseña."""
        return self._verificar_codigo_pwd(obtener_inversor(self.db, inversor_id), codigo, f"pwd:{inversor_id}")

    def cambiar_password(self, inversor_id: int, permiso: str, nueva: str) -> PasswordCambiadaDTO:
        """Paso 3: con el permiso del paso 2 se guarda la contraseña nueva y se cierran las otras sesiones."""
        return PasswordCambiadaDTO(token=self._aplicar_password(obtener_inversor(self.db, inversor_id), permiso, nueva))

    # --- Sin sesión: "Olvidé mi contraseña" (no revela qué correos tienen cuenta) ---
    def olvide_pedir_codigo(self, email: str) -> dict:
        clave = email.strip().lower()
        limites.REENVIO.consumir(f"olvide:{clave}")
        inv = self.repo.find_by_email(clave)
        if inv:
            self._mandar_codigo_pwd(inv)
        return {"enviado": True, "email": _ocultar_email(clave), "minutos": MINUTOS_CODIGO}

    def olvide_verificar_codigo(self, email: str, codigo: str) -> dict:
        clave = email.strip().lower()
        inv = self.repo.find_by_email(clave)
        if not inv:
            limites.CODIGO.verificar(f"olvide:{clave}")
            limites.CODIGO.registrar(f"olvide:{clave}")
            raise BusinessError("No hay un código pendiente. Pedí uno nuevo.", campo="codigo")
        return self._verificar_codigo_pwd(inv, codigo, f"olvide:{clave}")

    def olvide_cambiar(self, email: str, permiso: str, nueva: str) -> SesionDTO:
        inv = self.repo.find_by_email(email.strip().lower())
        if not inv:
            raise BusinessError("Primero confirmá el código que te mandamos por correo.", campo="codigo")
        token = self._aplicar_password(inv, permiso, nueva)
        return SesionDTO(token=token, inversor=to_inversor(inv))

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
