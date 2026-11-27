"""Cada hallazgo de la revisión del backend (Revision_backend_IOL2) reproducido como test, ya corregido."""
from datetime import datetime, timedelta

import pytest

from src.utils.mercado import TZ_AR
from tests.conftest import PASSWORD, depositar, nuevo_activo, nuevo_inversor


@pytest.fixture
def dos(client):
    """Dos inversores con saldo: A es la sesión activa; B es la víctima."""
    nuevo_activo(client, "GGAL", precio=100)
    b = nuevo_inversor(client)
    depositar(client, b["cuenta"]["id"], 10000)
    a = nuevo_inversor(client)
    depositar(client, a["cuenta"]["id"], 10000)
    return a, b


# ---------- C1 + N1: nadie entra a la cuenta de otro ----------
@pytest.mark.parametrize("metodo,ruta,cuerpo", [
    ("get", "/cuentas/{c}", None),
    ("post", "/cuentas/{c}/depositos", {"moneda": "ARS", "monto": 5000}),
    ("post", "/cuentas/{c}/extracciones", {"moneda": "ARS", "monto": 100}),
    ("post", "/cuentas/{c}/compras", {"ticker": "GGAL", "cantidad": 3}),
    ("get", "/cuentas/{c}/cartera", None),
    ("get", "/cuentas/{c}/movimientos", None),
    ("get", "/inversores/{i}", None),
    ("patch", "/inversores/{i}/perfil", {"perfil_riesgo": "conservador"}),
    ("post", "/inversores/{i}/password/codigo", None),
    ("post", "/inversores/{i}/password", {"permiso": "x" * 20, "nueva": "otra-clave-123"}),
    ("get", "/panel/inversores/{i}", None),
    ("get", "/panel/cuentas/{c}/actividad", None),
    ("post", "/panel/cuentas/{c}/movimientos", {"tipo": "extraccion", "moneda": "ARS", "monto": 100}),
    ("post", "/movimientos", {"cuenta_id": "{c}", "tipo": "extraccion", "moneda": "ARS", "monto": 100}),
    ("post", "/operaciones", {"cuenta_id": "{c}", "tipo": "compra", "ticker": "GGAL", "cantidad": 1}),
    ("post", "/favoritos", {"inversor_id": "{i}", "activo_id": 1}),
])
def test_no_se_puede_tocar_la_cuenta_de_otro(client, dos, metodo, ruta, cuerpo):
    _, b = dos
    c, i = b["cuenta"]["id"], b["id"]
    url = ruta.format(c=c, i=i)
    datos = {k: (c if v == "{c}" else i if v == "{i}" else v) for k, v in cuerpo.items()} if cuerpo else None
    pedir = getattr(client, metodo)
    r = pedir(url, json=datos) if datos is not None else pedir(url)
    assert r.status_code == 403, r.text  # con sesión de A, sobre B
    client.como(None)
    r = pedir(url, json=datos) if datos is not None else pedir(url)
    assert r.status_code == 401  # sin sesión
    # y el saldo de B sigue intacto
    assert client.get(f"/cuentas/{c}", headers=b["headers"]).json()["saldo_ars"] == 10000


def test_ver_operacion_o_movimiento_de_otro_no(client, dos):
    a, b = dos
    op = client.post(f"/cuentas/{b['cuenta']['id']}/compras", json={"ticker": "GGAL", "cantidad": 1}, headers=b["headers"]).json()
    mov = client.get(f"/cuentas/{b['cuenta']['id']}/movimientos", headers=b["headers"]).json()[0]
    assert client.get(f"/operaciones/{op['id']}").status_code == 403
    assert client.get(f"/movimientos/{mov['id']}").status_code == 403
    assert client.get(f"/operaciones/{op['id']}", headers=b["headers"]).status_code == 200


# ---------- C2 + N2 + R19: administración ----------
@pytest.mark.parametrize("metodo,ruta,cuerpo", [
    ("post", "/activos", {"ticker": "XX", "nombre": "X", "tipo": "accion", "moneda": "ARS", "precio_actual": 1, "nivel_riesgo": 3}),
    ("patch", "/activos/1/precio", {"precio": 1}),
    ("patch", "/activos/1/estado", {"activo": False}),
    ("post", "/dividendos", {"activo_id": 1, "monto_por_unidad": 1000}),
    ("post", "/panel/dividendos", {"activo_id": 1, "monto_por_unidad": 1000}),
    ("post", "/mercado/sincronizar", None),
    ("post", "/mercado/historial", None),
    ("get", "/users/", None),
    ("delete", "/users/1", None),
])
def test_administracion_solo_para_admin(client, dos, metodo, ruta, cuerpo):
    pedir = getattr(client, metodo)
    r = pedir(ruta, json=cuerpo) if cuerpo is not None else pedir(ruta)
    assert r.status_code == 403, r.text
    client.como(None)
    r = pedir(ruta, json=cuerpo) if cuerpo is not None else pedir(ruta)
    assert r.status_code == 401


# ---------- C3: fuerza bruta ----------
def test_login_se_frena_despues_de_5_errores(client):
    inv = nuevo_inversor(client)
    for _ in range(5):
        assert client.post("/auth/ingresar", json={"email": inv["email"], "password": "mala-clave"}).status_code == 401
    r = client.post("/auth/ingresar", json={"email": inv["email"], "password": PASSWORD})
    assert r.status_code == 429 and "minutos" in r.json()["detail"]


def test_cambiar_password_tambien_se_frena(client, monkeypatch):
    from src.utils import correo
    monkeypatch.setattr(correo, "despachar", lambda *a, **k: None)
    inv = nuevo_inversor(client)
    url = f"/inversores/{inv['id']}/password"
    # Después de 5 códigos equivocados hay que pedir uno nuevo
    assert client.post(f"{url}/codigo").status_code == 200
    for _ in range(5):
        assert client.post(f"{url}/verificar", json={"codigo": "999999"}).status_code == 422
    r = client.post(f"{url}/verificar", json={"codigo": "999999"})
    assert r.status_code == 422 and "intentos" in r.json()["detail"]
    # Y no se pueden pedir más de 5 códigos por hora
    for _ in range(4):
        client.post(f"{url}/codigo")
    assert client.post(f"{url}/codigo").status_code == 429


# ---------- B5 + B6: errores inesperados ----------
def test_token_con_caracteres_raros_es_401(client):
    from src.utils import seguridad
    assert seguridad.leer_token("á.é") is None  # antes: TypeError en compare_digest -> 500
    r = client.get("/auth/yo", headers={"Authorization": "Bearer á.é".encode("latin-1")})
    assert r.status_code == 401


def test_error_inesperado_responde_json_con_cors(client, monkeypatch):
    from src.services import activo_service

    def falla(*a, **k):
        raise RuntimeError("algo no previsto")
    monkeypatch.setattr(activo_service.ActivoService, "listar", falla)
    r = client.get("/activos", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 500 and r.json()["error"] == "ErrorInterno"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


# ---------- B7, N4, N5: validaciones ----------
def test_montos_con_tope(client):
    inv = nuevo_inversor(client)
    r = client.post(f"/cuentas/{inv['cuenta']['id']}/depositos", json={"moneda": "ARS", "monto": "1e30"})
    assert r.status_code == 422 and "demasiado grande" in r.json()["detail"]
    r = client.put(f"/cuentas/{inv['cuenta']['id']}", json={"saldo_ars": "1e30"}, headers=client.admin)
    assert r.status_code == 422


def test_null_en_una_edicion_es_422(client):
    inv = nuevo_inversor(client)
    act = nuevo_activo(client, "YPFD", precio=100)
    r = client.put(f"/inversores/{inv['id']}", json={"nombre": None}, headers=client.admin)
    assert r.status_code == 422 and "vacío" in r.json()["detail"]
    al = client.post("/alertas", json={"activo_id": act["id"], "tipo": "sube_pct", "valor": 10}).json()
    assert client.put(f"/alertas/{al['id']}", json={"valor": None}).status_code == 422
    assert client.put(f"/alertas/{al['id']}", json={"recurrente": None}).status_code == 422
    assert client.put(f"/alertas/{al['id']}", json={"valor": 50000}).status_code == 422  # mismo tope que al crear


# ---------- N6: el MEP no toca el precio promedio ----------
def test_mep_no_cambia_el_promedio_de_al30(client):
    nuevo_activo(client, "AL30", tipo="bono", precio=1000, riesgo=2)
    nuevo_activo(client, "AL30D", tipo="bono", moneda="USD", precio=1, riesgo=2)
    inv = nuevo_inversor(client)
    c = inv["cuenta"]["id"]
    depositar(client, c, 1_000_000)
    client.post(f"/cuentas/{c}/compras", json={"ticker": "AL30", "cantidad": 100})
    client.patch("/activos/1/precio", json={"precio": 2000}, headers=client.admin)
    assert client.post(f"/cuentas/{c}/mep", json={"monto_ars": 201000}).status_code == 201
    ten = [t for t in client.get(f"/cuentas/{c}/cartera").json()["tenencias"] if t["ticker"] == "AL30"][0]
    assert ten["cantidad"] == 100 and ten["precio_promedio"] == 1000


# ---------- N7: una operación rechazada no cuenta ----------
def test_rechazada_no_suma_ganancia_ni_comision(client):
    nuevo_activo(client, "GGAL", precio=100)
    inv = nuevo_inversor(client)
    c = inv["cuenta"]["id"]
    depositar(client, c, 10000)
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 10})
    client.patch("/activos/1/precio", json={"precio": 200}, headers=client.admin)
    venta = client.post(f"/cuentas/{c}/ventas", json={"ticker": "GGAL", "cantidad": 10}).json()
    client.put(f"/operaciones/{venta['id']}", json={"estado": "rechazada"}, headers=client.admin)
    assert client.get(f"/cuentas/{c}/ganancias-realizadas").json()["por_anio"] == []
    hist = client.get(f"/cuentas/{c}/operaciones").json()
    assert hist["cantidad"] == 2 and hist["total_comisiones"]["ARS"] == 5  # solo la compra (1000 x 0,5 %)


# ---------- B8: dividendos ----------
def test_dividendo_sin_fecha_futura_ni_repetido(client):
    act = nuevo_activo(client, "KO", tipo="cedear", precio=100)
    futuro = (datetime.now(TZ_AR).date() + timedelta(days=30)).isoformat()
    r = client.post("/dividendos", json={"activo_id": act["id"], "monto_por_unidad": 5, "fecha_pago": futuro}, headers=client.admin)
    assert r.status_code == 422
    assert client.post("/dividendos", json={"activo_id": act["id"], "monto_por_unidad": 5}, headers=client.admin).status_code == 201
    assert client.post("/dividendos", json={"activo_id": act["id"], "monto_por_unidad": 5}, headers=client.admin).status_code == 409


# ---------- B11: feriados ----------
def test_no_se_opera_en_feriado(client, reloj):
    nuevo_activo(client, "GGAL", precio=100)
    inv = nuevo_inversor(client)
    depositar(client, inv["cuenta"]["id"], 10000)
    reloj.ahora = datetime(2026, 12, 25, 12, 0, tzinfo=TZ_AR)  # viernes, Navidad
    r = client.post(f"/cuentas/{inv['cuenta']['id']}/compras", json={"ticker": "GGAL", "cantidad": 1})
    assert r.status_code == 422 and "viernes 25/12" in r.json()["detail"]


# ---------- B12: sin tipo de cambio, los dólares no se suman como pesos ----------
def test_cartera_sin_tipo_de_cambio(client):
    nuevo_activo(client, "GGAL", precio=100)
    nuevo_activo(client, "GD30D", tipo="bono", moneda="USD", precio=100, riesgo=2)
    inv = nuevo_inversor(client)
    c = inv["cuenta"]["id"]
    depositar(client, c, 10000)
    depositar(client, c, 1000, "USD")
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 5})
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GD30D", "cantidad": 5})
    cart = client.get(f"/cuentas/{c}/cartera").json()
    assert cart["tipo_cambio_mep"] is None and cart["composicion_sin_dolares"] is True
    assert [(x["tipo"], x["porcentaje"]) for x in cart["composicion_por_tipo"]] == [("accion", 100)]


# ---------- B13: un precio manual un sábado no inventa un cierre ----------
def test_precio_manual_fuera_de_rueda_no_escribe_historial(client, reloj):
    act = nuevo_activo(client, "GGAL", precio=100)
    reloj.ahora = datetime(2026, 11, 14, 12, 0, tzinfo=TZ_AR)  # sábado
    client.patch(f"/activos/{act['id']}/precio", json={"precio": 150}, headers=client.admin)
    assert client.get(f"/activos/{act['id']}/historial?dias=30").json()["cierres"] == []


# ---------- N13: los códigos de verificación tienen tope aunque se pidan nuevos ----------
def test_codigo_tope_por_hora(client, monkeypatch):
    from src.utils import limites
    for _ in range(10):
        limites.CODIGO.registrar("nadie@test.com")
    r = client.post("/auth/verificar-email", json={"email": "nadie@test.com", "codigo": "123456"})
    assert r.status_code == 429


# ---------- B9 y B10 ----------
def test_ticker_se_normaliza_y_no_puede_contradecir_al_id(client):
    act = nuevo_activo(client, "GGAL", precio=100)
    nuevo_activo(client, "YPFD", precio=100)
    inv = nuevo_inversor(client)
    c = inv["cuenta"]["id"]
    depositar(client, c, 10000)
    assert client.post(f"/cuentas/{c}/compras", json={"ticker": " ggal ", "cantidad": 1}).status_code == 201
    r = client.post(f"/cuentas/{c}/compras", json={"activo_id": act["id"], "ticker": "YPFD", "cantidad": 1})
    assert r.status_code == 422 and "GGAL" in r.json()["detail"]


def test_health_con_la_base_caida_es_503(client, monkeypatch):
    from src import app as modulo

    class Caida:
        def connect(self):
            raise OSError("sin base")
    monkeypatch.setattr(modulo, "engine", Caida())
    r = client.get("http://testserver/health")
    assert r.status_code == 503 and r.json()["status"] == "error"
