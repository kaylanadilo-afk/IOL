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


def test_cambiar_contrasena_primero_pide_el_codigo(client, monkeypatch):
    import re

    from src.utils import correo
    mails = []
    monkeypatch.setattr(correo, "despachar", lambda destino, asunto, texto, html, al_enviar=None: mails.append((destino, asunto, texto)))
    inv = nuevo_inversor(client, email="ana@test.com")
    viejo = ingresar(client, "ana@test.com", PASSWORD).json()["token"]
    url = f"/inversores/{inv['id']}/password"

    # Sin confirmar un código no se puede elegir la contraseña nueva
    r = client.post(url, json={"permiso": "x" * 20, "nueva": "nueva-clave-1"})
    assert r.status_code == 422 and "codigo" in r.json()["campos"]

    # Paso 1: se pide el código (todavía no se escribe ninguna contraseña)
    r = client.post(f"{url}/codigo")
    assert r.status_code == 200 and r.json()["email"] == "a*a@test.com"
    assert mails[-1][0] == "ana@test.com" and "cambiar la contraseña" in mails[-1][1]
    codigo = re.search(r"\b(\d{6})\b", mails[-1][2]).group(1)

    # Un código equivocado no da permiso
    malo = "000000" if codigo != "000000" else "111111"
    r = client.post(f"{url}/verificar", json={"codigo": malo})
    assert r.status_code == 422 and "codigo" in r.json()["campos"]

    # Paso 2: con el código correcto llega el permiso; el código no se puede volver a usar
    r = client.post(f"{url}/verificar", json={"codigo": codigo})
    assert r.status_code == 200
    permiso = r.json()["permiso"]
    assert client.post(f"{url}/verificar", json={"codigo": codigo}).status_code == 422
    assert ingresar(client, "ana@test.com", PASSWORD).status_code == 200  # sigue la de antes

    # Paso 3: la nueva tiene que ser válida y distinta; un permiso inventado no sirve
    assert client.post(url, json={"permiso": permiso, "nueva": "corta"}).status_code == 422
    assert client.post(url, json={"permiso": permiso, "nueva": PASSWORD}).status_code == 422
    assert client.post(url, json={"permiso": "y" * 32, "nueva": "nueva-clave-1"}).status_code == 422
    r = client.post(url, json={"permiso": permiso, "nueva": "nueva-clave-1"})
    assert r.status_code == 200 and r.json()["token"]
    assert "cambió" in mails[-1][1]
    assert ingresar(client, "ana@test.com", PASSWORD).status_code == 401
    assert ingresar(client, "ana@test.com", "nueva-clave-1").status_code == 200
    assert client.get("/auth/yo", headers={"Authorization": f"Bearer {viejo}"}).status_code == 401
    nuevo = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/auth/yo", headers=nuevo).status_code == 200
    # El permiso es de un solo uso
    assert client.post(url, json={"permiso": permiso, "nueva": "otra-clave-22"}, headers=nuevo).status_code == 422




def test_olvide_mi_contrasena(client, monkeypatch):
    import re

    from src.utils import correo
    mails = []
    monkeypatch.setattr(correo, "despachar", lambda destino, asunto, texto, html, al_enviar=None: mails.append((destino, asunto, texto)))
    nuevo_inversor(client, email="olvido@test.com")
    client.como(None)  # sin sesión

    # Un correo sin cuenta recibe la misma respuesta y no se manda nada
    r = client.post("/auth/olvide", json={"email": "nadie@test.com"})
    assert r.status_code == 200 and r.json()["enviado"] is True and not mails
    assert client.post("/auth/olvide/verificar", json={"email": "nadie@test.com", "codigo": "123456"}).status_code == 422

    r = client.post("/auth/olvide", json={"email": "Olvido@test.com"})
    assert r.status_code == 200 and mails[-1][0] == "olvido@test.com"
    codigo = re.search(r"\b(\d{6})\b", mails[-1][2]).group(1)
    malo = "000000" if codigo != "000000" else "111111"
    assert client.post("/auth/olvide/verificar", json={"email": "olvido@test.com", "codigo": malo}).status_code == 422
    r = client.post("/auth/olvide/verificar", json={"email": "olvido@test.com", "codigo": codigo})
    assert r.status_code == 200
    permiso = r.json()["permiso"]

    # El permiso es de esa cuenta: no sirve con otro correo
    nuevo_inversor(client, email="otra@test.com")
    client.como(None)
    assert client.post("/auth/olvide/cambiar", json={"email": "otra@test.com", "permiso": permiso, "nueva": "recuperada-1"}).status_code == 422

    r = client.post("/auth/olvide/cambiar", json={"email": "olvido@test.com", "permiso": permiso, "nueva": "recuperada-1"})
    assert r.status_code == 200 and r.json()["token"] and r.json()["inversor"]["email"] == "olvido@test.com"
    assert "cambió" in mails[-1][1]
    assert ingresar(client, "olvido@test.com", PASSWORD).status_code == 401
    assert ingresar(client, "olvido@test.com", "recuperada-1").status_code == 200
    # Se usa una sola vez
    assert client.post("/auth/olvide/cambiar", json={"email": "olvido@test.com", "permiso": permiso, "nueva": "otra-mas-22"}).status_code == 422
