"""Envío de correos (código de verificación) por SMTP.

Se configura en el .env:
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=tu.cuenta@gmail.com
    SMTP_PASSWORD=<contraseña de aplicación de Google, 16 letras>
    SMTP_FROM=Zeno Investments <tu.cuenta@gmail.com>

Sin SMTP_HOST no se manda nada: el código se escribe en la consola de la API (sirve para probar en
desarrollo, pero nadie lo recibe por mail).
"""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

log = logging.getLogger("uvicorn.error")


def configurado() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def enviar(destino: str, asunto: str, texto: str, html: str) -> bool:
    """Manda el correo. Devuelve False si no hay SMTP configurado (queda solo en el log)."""
    if not configurado():
        log.warning("SMTP sin configurar: no se envió el correo a %s. Contenido:\n%s", destino, texto)
        return False
    host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
    usuario, clave = os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", "")
    nombre, remitente = parseaddr(os.getenv("SMTP_FROM") or usuario)
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = formataddr((nombre or "Zeno Investments", remitente))
    msg["To"] = destino
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    contexto = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=contexto, timeout=20) as s:
            if usuario:
                s.login(usuario, clave)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls(context=contexto)
            if usuario:
                s.login(usuario, clave)
            s.send_message(msg)
    return True


def mail_codigo(nombre: str, codigo: str, minutos: int) -> tuple[str, str, str]:
    """Asunto, texto y HTML del correo con el código de verificación."""
    asunto = f"{codigo} es tu código de verificación de Zeno Investments"
    texto = (f"Hola {nombre}:\n\nTu código para confirmar el correo en Zeno Investments es {codigo}.\n"
             f"Vence en {minutos} minutos.\n\nSi no creaste una cuenta, ignorá este mensaje.")
    html = f"""<!doctype html><html><body style="margin:0;background:#F4F6F3;font-family:Arial,Helvetica,sans-serif;color:#0E1A2B">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:460px;background:#fff;border:1px solid #E2E6E0;border-radius:16px">
<tr><td style="padding:28px 28px 8px"><b style="font-size:20px">Zeno</b> <span style="font-size:20px;color:#667085">Investments</span></td></tr>
<tr><td style="padding:8px 28px 0;font-size:15px;line-height:1.5">Hola {nombre}: usá este código para confirmar tu correo.</td></tr>
<tr><td align="center" style="padding:22px 28px"><div style="display:inline-block;font-size:34px;font-weight:bold;letter-spacing:10px;background:#EEF1EC;border-radius:12px;padding:14px 22px">{codigo}</div></td></tr>
<tr><td style="padding:0 28px 28px;font-size:13px;color:#667085;line-height:1.5">Vence en {minutos} minutos. Si no creaste una cuenta en Zeno Investments, ignorá este mensaje.</td></tr>
</table></td></tr></table></body></html>"""
    return asunto, texto, html
