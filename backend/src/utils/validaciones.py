"""Validaciones de datos personales para el alta de cuentas (email y CUIT)."""
import os
import re
import secrets
import smtplib

from email_validator import EmailNotValidError, EmailUndeliverableError, validate_email

# Prefijos de CUIT/CUIL que asigna AFIP: personas (20, 23, 24, 27) y empresas (30, 33, 34)
PREFIJOS_CUIT = {"20", "23", "24", "27", "30", "33", "34"}
PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
NOMBRE_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'´ .-]*$")


def validar_dns() -> bool:
    """Por defecto se consulta el DNS para saber si el dominio del correo existe y recibe emails.
    Con VALIDAR_EMAIL_DNS=0 (tests, sin internet) solo se revisa el formato."""
    return os.getenv("VALIDAR_EMAIL_DNS", "1") != "0"


def validar_email(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Ingresá tu correo electrónico")
    dns = validar_dns()
    try:
        r = validate_email(v, check_deliverability=dns, test_environment=not dns, timeout=5)
    except EmailUndeliverableError as e:
        texto = str(e)
        if "does not exist" in texto:
            raise ValueError("El dominio de este correo no existe. Revisá lo que va después del @") from None
        if "does not accept email" in texto or "does not send" in texto:
            raise ValueError("Ese dominio no recibe correos. Usá una dirección real") from None
        raise ValueError("No pudimos verificar que este correo exista") from None
    except EmailNotValidError as e:
        if "special-use or reserved" in str(e):
            raise ValueError("Ese dominio no se puede usar para correos. Usá una dirección real") from None
        raise ValueError("Ingresá un correo válido, por ejemplo nombre@gmail.com") from None
    email = r.normalized.lower()
    if dns and casilla_existe(email, [mx for _, mx in (getattr(r, "mx", None) or [])]) is False:
        raise ValueError("Esta casilla de correo no existe. Revisá que esté bien escrita")
    return email


def _rcpt(servidor: smtplib.SMTP, email: str) -> int:
    return servidor.rcpt(email)[0]


def casilla_existe(email: str, mx: list[str]) -> bool | None:
    """Le pregunta al servidor de correo del dominio si la casilla existe, sin mandar ningún mensaje.

    True: el servidor la acepta. False: responde que no existe (por ejemplo Gmail con 550 5.1.1).
    None: no se puede saber (no contesta, bloquea la consulta o acepta cualquier dirección); en ese
    caso no se rechaza y la confirmación queda a cargo del código que se manda por email.
    """
    if not mx:
        return None
    dominio = email.rsplit("@", 1)[1]
    try:
        with smtplib.SMTP(mx[0].rstrip("."), 25, timeout=8, local_hostname="mail.zeno.investments") as s:
            s.ehlo()
            if s.mail("")[0] != 250:
                return None
            codigo, texto = s.rcpt(email)
            texto = texto.decode(errors="ignore").lower()
            # Solo cuenta como "no existe" un rechazo del destinatario (5.1.x), no un bloqueo por spam (5.7.x)
            if codigo in (550, 551, 553) and ("5.1." in texto or "does not exist" in texto or "no such user" in texto
                                              or "unknown user" in texto or "user unknown" in texto):
                return False
            if codigo == 250:
                # Algunos servidores aceptan cualquier dirección: así no se puede saber
                inventada = f"zeno-{secrets.token_hex(6)}@{dominio}"
                return None if _rcpt(s, inventada) == 250 else True
    except (OSError, smtplib.SMTPException):
        return None
    return None


def digito_verificador_cuit(base: str) -> int | None:
    """Dígito verificador de los 10 primeros dígitos (módulo 11). None si esa combinación no es válida."""
    resto = 11 - sum(int(c) * p for c, p in zip(base, PESOS_CUIT)) % 11
    return 0 if resto == 11 else None if resto == 10 else resto


def validar_cuit(v: str) -> str:
    v = re.sub(r"[-\s.]", "", v or "")
    if not v:
        raise ValueError("Ingresá tu CUIT")
    if not re.fullmatch(r"\d{11}", v):
        raise ValueError("El CUIT tiene que tener 11 dígitos")
    if v[:2] not in PREFIJOS_CUIT:
        raise ValueError("El CUIT no es válido: tiene que empezar con 20, 23, 24, 27, 30, 33 o 34")
    if digito_verificador_cuit(v[:10]) != int(v[10]):
        raise ValueError("El CUIT no es válido: revisá los números (el dígito verificador no coincide)")
    return v


def validar_nombre(v: str) -> str:
    v = " ".join((v or "").split())
    if not v:
        raise ValueError("Ingresá tu nombre y apellido")
    if len(v) > 120:
        raise ValueError("El nombre puede tener hasta 120 caracteres")
    if not NOMBRE_RE.match(v):
        raise ValueError("El nombre solo puede tener letras y espacios")
    if len(v.split(" ")) < 2:
        raise ValueError("Ingresá nombre y apellido")
    return v
