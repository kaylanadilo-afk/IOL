"""Contraseñas y sesiones, solo con la biblioteca estándar.

- Contraseñas: scrypt con sal aleatoria. En la base se guarda "scrypt$<sal>$<hash>", nunca el texto.
- Sesión: al ingresar se entrega un token firmado (HMAC-SHA256) con el id del inversor y el
  vencimiento. El front lo guarda y con él recupera la sesión sin volver a pedir la contraseña.

La clave para firmar sale de la variable de entorno SECRET_KEY. Si no está, se genera una al
arrancar: funciona igual, pero al reiniciar la API todos tienen que volver a ingresar.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
DURACION_SESION = 7 * 24 * 3600  # una semana
_CLAVE = (os.getenv("SECRET_KEY") or secrets.token_hex(32)).encode()


def hashear(password: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=sal, **SCRYPT)
    return f"scrypt${sal.hex()}${h.hex()}"


def verificar(password: str, guardado: str | None) -> bool:
    if not guardado or not guardado.startswith("scrypt$"):
        return False
    _, sal_hex, h_hex = guardado.split("$", 2)
    h = hashlib.scrypt(password.encode(), salt=bytes.fromhex(sal_hex), **SCRYPT)
    return hmac.compare_digest(h.hex(), h_hex)


def hash_codigo(inversor_id: int, codigo: str) -> str:
    """Hash del código de verificación (atado al inversor, para que no sirva en otra cuenta)."""
    return hmac.new(_CLAVE, f"{inversor_id}:{codigo}".encode(), hashlib.sha256).hexdigest()


# Para el login con un email inexistente: se compara igual contra esto y tarda lo mismo
HASH_FALSO = hashear(secrets.token_hex(16))


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def crear_token(inversor_id: int, password_hash: str | None) -> str:
    # Incluye un pedacito del hash: si se cambia la contraseña, las sesiones viejas dejan de valer
    datos = {"id": inversor_id, "exp": int(time.time()) + DURACION_SESION, "v": (password_hash or "")[-12:]}
    cuerpo = _b64(json.dumps(datos, separators=(",", ":")).encode())
    firma = _b64(hmac.new(_CLAVE, cuerpo.encode(), hashlib.sha256).digest())
    return f"{cuerpo}.{firma}"


def leer_token(token: str) -> dict | None:
    """Devuelve {"id", "exp", "v"} si el token es válido y no venció; si no, None."""
    try:
        cuerpo, firma = token.split(".", 1)
        esperada = _b64(hmac.new(_CLAVE, cuerpo.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(firma, esperada):
            return None
        datos = json.loads(_unb64(cuerpo))
        return datos if datos.get("exp", 0) > time.time() else None
    except (ValueError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError):
        return None
