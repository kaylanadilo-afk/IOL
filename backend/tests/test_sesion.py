"""Contraseñas y sesión."""
from src.utils import seguridad
from tests.conftest import PASSWORD, nuevo_inversor


def ingresar(client, email, password):
    return client.post("/auth/ingresar", json={"email": email, "password": password})


def test_la_contrasena_se_guarda_hasheada():
    h = seguridad.hashear("mi-clave-123")
    assert h.startswith("scrypt$") and "mi-clave-123" not in h
    assert seguridad.verificar("mi-clave-123", h) and not seguridad.verificar("otra", h)
    assert seguridad.hashear("mi-clave-123") != h  # sal distinta cada vez


def test_alta_exige_contrasena_de_8_caracteres(client):
    base = {"email": "p@test.com", "nombre": "Ana Test", "cuit": "20411111130", "perfil_riesgo": "moderado"}
    r = client.post("/inversores", json=base)
    assert r.status_code == 422
    r = client.post("/inversores", json={**base, "password": "corta"})
    assert r.status_code == 422 and "8 caracteres" in r.json()["detail"]
    r = client.post("/inversores", json={**base, "password": "larga-y-segura"})
    assert r.status_code == 201 and "password" not in r.text and "hash" not in r.text


def test_ingresar_con_email_y_contrasena(client):
    inv = nuevo_inversor(client, email="ana@test.com")
    r = ingresar(client, "ANA@test.com ", PASSWORD)
    assert r.status_code == 200 and r.json()["inversor"]["id"] == inv["id"]
    token = r.json()["token"]
    yo = client.get("/auth/yo", headers={"Authorization": f"Bearer {token}"})
    assert yo.status_code == 200 and yo.json()["email"] == "ana@test.com"


def test_ingresar_mal_no_revela_si_el_email_existe(client):
    nuevo_inversor(client, email="ana@test.com")
    mal_clave = ingresar(client, "ana@test.com", "incorrecta")
    no_existe = ingresar(client, "nadie@test.com", PASSWORD)
    assert mal_clave.status_code == no_existe.status_code == 401
    assert mal_clave.json()["detail"] == no_existe.json()["detail"] == "Email o contraseña incorrectos."


def test_token_invalido(client):
    assert client.get("/auth/yo").status_code == 401
    assert client.get("/auth/yo", headers={"Authorization": "Bearer abc.def"}).status_code == 401


def test_cambiar_contrasena_con_codigo_por_mail(client, monkeypatch):
    import re

    from src.utils import correo
    mails = []
    monkeypatch.setattr(correo, "despachar", lambda destino, asunto, texto, html, al_enviar=None: mails.append((destino, asunto, texto)))
    inv = nuevo_inversor(client, email="ana@test.com")
    viejo = ingresar(client, "ana@test.com", PASSWORD).json()["token"]
    url = f"/inversores/{inv['id']}/password"
    assert client.post(url, json={"actual": "incorrecta", "nueva": "nueva-clave-1"}).status_code == 401
    assert client.post(url, json={"actual": PASSWORD, "nueva": "corta"}).status_code == 422
    assert client.post(url, json={"actual": PASSWORD, "nueva": PASSWORD}).status_code == 422

    # Paso 1: se manda el código; la contraseña todavía es la de antes
    r = client.post(url, json={"actual": PASSWORD, "nueva": "nueva-clave-1"})
    assert r.status_code == 200 and r.json()["pendiente"] is True and r.json()["email"] == "a*a@test.com"
    assert mails[-1][0] == "ana@test.com" and "cambiar la contraseña" in mails[-1][1]
    codigo = re.search(r"\b(\d{6})\b", mails[-1][2]).group(1)
    assert ingresar(client, "ana@test.com", PASSWORD).status_code == 200

    # Un código equivocado no cambia nada
    malo = "000000" if codigo != "000000" else "111111"
    r = client.post(f"{url}/confirmar", json={"codigo": malo})
    assert r.status_code == 422 and "codigo" in r.json()["campos"]

    # Paso 2: con el código se aplica, se avisa por mail y las otras sesiones se cierran
    r = client.post(f"{url}/confirmar", json={"codigo": codigo})
    assert r.status_code == 200 and r.json()["token"]
    assert "cambió" in mails[-1][1]
    assert ingresar(client, "ana@test.com", PASSWORD).status_code == 401
    assert ingresar(client, "ana@test.com", "nueva-clave-1").status_code == 200
    assert client.get("/auth/yo", headers={"Authorization": f"Bearer {viejo}"}).status_code == 401
    assert client.get("/auth/yo", headers={"Authorization": f"Bearer {r.json()['token']}"}).status_code == 200
    # El código no se puede usar dos veces
    assert client.post(f"{url}/confirmar", json={"codigo": codigo}, headers={"Authorization": f"Bearer {r.json()['token']}"}).status_code == 422
