"""Confirmación del correo con código y consulta al servidor de correo."""
import re

import pytest

from src.utils import correo, validaciones

ALTA = {"email": "nueva@test.com", "nombre": "Ana Test", "cuit": "20411111106", "perfil_riesgo": "moderado",
        "password": "clave-segura"}


@pytest.fixture
def mails(monkeypatch):
    """Activa la verificación y guarda los correos en vez de mandarlos."""
    enviados = []
    monkeypatch.setenv("VERIFICAR_EMAIL", "1")
    monkeypatch.setattr(correo, "enviar", lambda destino, asunto, texto, html: enviados.append((destino, texto)) or True)
    return enviados


def codigo(mails):
    return re.search(r"\b(\d{6})\b", mails[-1][1]).group(1)


def test_no_ingresa_hasta_confirmar_el_correo(client, mails):
    r = client.post("/inversores", json=ALTA)
    assert r.status_code == 201 and r.json()["email_verificado"] is False
    assert mails and mails[0][0] == "nueva@test.com"
    r = client.post("/auth/ingresar", json={"email": "nueva@test.com", "password": "clave-segura"})
    assert r.status_code == 403 and r.json()["error"] == "EmailNoVerificadoError"
    r = client.post("/auth/verificar-email", json={"email": "nueva@test.com", "codigo": codigo(mails)})
    assert r.status_code == 200 and r.json()["inversor"]["email_verificado"] is True and r.json()["token"]
    assert client.post("/auth/ingresar", json={"email": "nueva@test.com", "password": "clave-segura"}).status_code == 200


def test_codigo_incorrecto_y_limite_de_intentos(client, mails):
    client.post("/inversores", json=ALTA)
    bueno = codigo(mails)
    malo = "000000" if bueno != "000000" else "111111"
    for _ in range(5):
        r = client.post("/auth/verificar-email", json={"email": "nueva@test.com", "codigo": malo})
        assert r.status_code == 422 and "codigo" in r.json()["campos"]
    r = client.post("/auth/verificar-email", json={"email": "nueva@test.com", "codigo": bueno})
    assert r.status_code == 422 and "intentos" in r.json()["campos"]["codigo"]


def test_reenviar_codigo_espera_un_minuto(client, mails):
    client.post("/inversores", json=ALTA)
    r = client.post("/auth/reenviar-codigo", json={"email": "nueva@test.com"})
    assert r.json()["espera"] > 0 and len(mails) == 1
    # Un correo que no existe recibe la misma respuesta (no revela qué cuentas hay)
    assert client.post("/auth/reenviar-codigo", json={"email": "nadie@test.com"}).json()["ok"] is True


def test_casilla_inexistente_se_rechaza(client, monkeypatch):
    monkeypatch.setenv("VALIDAR_EMAIL_DNS", "1")

    class R:
        normalized = "inventada@gmail.com"
        mx = [(5, "gmail-smtp-in.l.google.com.")]

    monkeypatch.setattr(validaciones, "validate_email", lambda *a, **k: R())
    monkeypatch.setattr(validaciones, "casilla_existe", lambda email, mx: False)
    r = client.post("/inversores", json={**ALTA, "email": "inventada@gmail.com"})
    assert r.status_code == 422 and "no existe" in r.json()["campos"]["email"]
