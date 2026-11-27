"""Endpoints sumados del backend InitialStructure: alta/edición/baja de cada tabla, panel y /health."""
from src.app import app
from src.db.connection import get_db
from src.db.models.inversor_model import Inversor
from tests.conftest import PASSWORD, depositar, nuevo_activo, nuevo_inversor


def sesion(client, inv):
    token = client.post("/auth/ingresar", json={"email": inv["email"], "password": PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def admin(client):
    inv = nuevo_inversor(client)
    db = next(app.dependency_overrides[get_db]())
    db.query(Inversor).filter_by(id=inv["id"]).update({"es_admin": True})
    db.commit()
    db.close()
    return inv, sesion(client, inv)


def test_editar_y_borrar_es_solo_para_administradores(client):
    act = nuevo_activo(client, "GGAL")
    assert client.put(f"/activos/{act['id']}", json={"nombre": "Galicia"}).status_code == 401
    comun = nuevo_inversor(client)
    r = client.put(f"/activos/{act['id']}", json={"nombre": "Galicia"}, headers=sesion(client, comun))
    assert r.status_code == 403
    _, h = admin(client)
    r = client.put(f"/activos/{act['id']}", json={"nombre": "Grupo Galicia", "nivel_riesgo": 5}, headers=h)
    assert r.status_code == 200 and r.json()["nombre"] == "Grupo Galicia" and r.json()["nivel_riesgo"] == 5


def test_borrar_activo_solo_si_nunca_se_opero(client):
    _, h = admin(client)
    nuevo = nuevo_activo(client, "NUEVO")
    operado = nuevo_activo(client, "OPER")
    inv = nuevo_inversor(client)
    depositar(client, inv["cuenta"]["id"], 10000)
    assert client.post(f"/cuentas/{inv['cuenta']['id']}/compras", json={"activo_id": operado["id"], "cantidad": 1}).status_code == 201
    assert client.delete(f"/activos/{operado['id']}", headers=h).status_code == 422
    assert client.delete(f"/activos/{nuevo['id']}", headers=h).status_code == 204
    assert client.get(f"/activos/{nuevo['id']}").status_code == 404


def test_editar_inversor_valida_y_no_repite_datos(client):
    _, h = admin(client)
    a, b = nuevo_inversor(client), nuevo_inversor(client)
    r = client.put(f"/inversores/{a['id']}", json={"email": b["email"]}, headers=h)
    assert r.status_code == 409 and "email" in r.json()["campos"]
    r = client.put(f"/inversores/{a['id']}", json={"cuit": "20111111113"}, headers=h)
    assert r.status_code == 422 and "cuit" in r.json()["campos"]
    r = client.put(f"/inversores/{a['id']}", json={"nombre": "Ana María Pérez", "perfil_riesgo": "conservador"}, headers=h)
    assert r.status_code == 200 and r.json()["nombre"] == "Ana María Pérez"


def test_borrar_inversor(client):
    yo, h = admin(client)
    sin_actividad, con_saldo = nuevo_inversor(client), nuevo_inversor(client)
    depositar(client, con_saldo["cuenta"]["id"], 500)
    assert client.delete(f"/inversores/{yo['id']}", headers=h).status_code == 422
    assert client.delete(f"/inversores/{con_saldo['id']}", headers=h).status_code == 422
    assert client.delete(f"/inversores/{sin_actividad['id']}", headers=h).status_code == 204
    assert client.get(f"/inversores/{sin_actividad['id']}", headers=h).status_code == 404


def test_cuentas_abrir_ajustar_y_borrar(client):
    _, h = admin(client)
    inv = nuevo_inversor(client)
    cid = inv["cuenta"]["id"]
    assert client.post("/cuentas", json={"inversor_id": inv["id"]}, headers=h).status_code == 409
    r = client.put(f"/cuentas/{cid}", json={"saldo_ars": 1234.5}, headers=h)
    assert r.status_code == 200 and r.json()["saldo_ars"] == 1234.5
    assert client.put(f"/cuentas/{cid}", json={"saldo_usd": -1}, headers=h).status_code == 422
    assert client.delete(f"/cuentas/{cid}", headers=h).status_code == 422  # tiene saldo
    client.put(f"/cuentas/{cid}", json={"saldo_ars": 0}, headers=h)
    assert client.delete(f"/cuentas/{cid}", headers=h).status_code == 204
    r = client.post("/cuentas", json={"inversor_id": inv["id"]}, headers=h)
    assert r.status_code == 201 and r.json()["saldo_ars"] == 0


def test_operaciones_y_movimientos_respetan_las_reglas_del_broker(client):
    _, h = admin(client)
    act = nuevo_activo(client, "YPFD", precio=1000)
    inv = nuevo_inversor(client)
    cid = inv["cuenta"]["id"]
    r = client.post("/movimientos", json={"cuenta_id": cid, "tipo": "deposito", "moneda": "ARS", "monto": 5000})
    assert r.status_code == 201
    mov = r.json()
    assert client.get(f"/cuentas/{cid}").json()["saldo_ars"] == 5000
    # Sin saldo suficiente no se puede comprar, igual que en /cuentas/{id}/compras
    r = client.post("/operaciones", json={"cuenta_id": cid, "tipo": "compra", "activo_id": act["id"], "cantidad": 10})
    assert r.status_code == 422
    r = client.post("/operaciones", json={"cuenta_id": cid, "tipo": "compra", "activo_id": act["id"], "cantidad": 2})
    assert r.status_code == 201
    op = r.json()
    assert client.get(f"/operaciones/{op['id']}").json()["ticker"] == "YPFD"
    r = client.put(f"/operaciones/{op['id']}", json={"estado": "rechazada"}, headers=h)
    assert r.status_code == 200 and r.json()["estado"] == "rechazada"
    assert client.put(f"/operaciones/{op['id']}", json={"estado": "inventado"}, headers=h).status_code == 422
    r = client.put(f"/movimientos/{mov['id']}", json={"descripcion": "Transferencia inicial"}, headers=h)
    assert r.status_code == 200 and r.json()["descripcion"] == "Transferencia inicial"
    assert client.delete(f"/movimientos/{mov['id']}", headers=h).status_code == 204
    assert client.get(f"/movimientos/{mov['id']}").status_code == 404


def test_tenencias(client):
    _, h = admin(client)
    act = nuevo_activo(client, "AL30")
    inv = nuevo_inversor(client)
    cid = inv["cuenta"]["id"]
    datos = {"cuenta_id": cid, "activo_id": act["id"], "cantidad": 10, "precio_promedio": 95.5}
    client.como(None)
    assert client.post("/tenencias", json=datos).status_code == 401  # sin sesión
    client.como(inv)
    assert client.post("/tenencias", json=datos).status_code == 403  # con sesión, pero no es administrador
    assert client.post("/tenencias", json=datos, headers=h).status_code == 201
    assert client.post("/tenencias", json=datos, headers=h).status_code == 409
    assert client.get(f"/tenencias/{cid}/{act['id']}").json()["cantidad"] == 10
    r = client.put(f"/tenencias/{cid}/{act['id']}", json={"cantidad": 15}, headers=h)
    assert r.status_code == 200 and r.json()["cantidad"] == 15
    assert client.put(f"/tenencias/{cid}/{act['id']}", json={"cantidad": 0}, headers=h).status_code == 422
    assert client.delete(f"/tenencias/{cid}/{act['id']}", headers=h).status_code == 204
    assert client.get(f"/tenencias/{cid}/{act['id']}").status_code == 404


def test_dividendos(client):
    _, h = admin(client)
    act = nuevo_activo(client, "KO")
    div = client.post("/dividendos", json={"activo_id": act["id"], "monto_por_unidad": 10}, headers=client.admin).json()
    assert client.get(f"/dividendos/{div['id']}").json()["monto_por_unidad"] == 10
    r = client.put(f"/dividendos/{div['id']}", json={"monto_por_unidad": 12.5}, headers=h)
    assert r.status_code == 200 and r.json()["monto_por_unidad"] == 12.5
    assert client.delete(f"/dividendos/{div['id']}", headers=h).status_code == 204
    assert client.get(f"/dividendos/{div['id']}").status_code == 404


def test_favoritos_con_fecha(client):
    act = nuevo_activo(client, "MELI")
    inv = nuevo_inversor(client)
    datos = {"inversor_id": inv["id"], "activo_id": act["id"]}
    r = client.post("/favoritos", json=datos)
    assert r.status_code == 201 and r.json()["fecha_agregado"]
    assert client.post("/favoritos", json=datos).status_code == 409
    assert client.get(f"/favoritos/{inv['id']}/{act['id']}").status_code == 200
    assert [a["ticker"] for a in client.get(f"/inversores/{inv['id']}/favoritos").json()] == ["MELI"]
    assert client.delete(f"/favoritos/{inv['id']}/{act['id']}").status_code == 204
    assert client.get(f"/favoritos/{inv['id']}/{act['id']}").status_code == 404


def test_panel(client):
    act = nuevo_activo(client, "TXAR", precio=100)
    inv = nuevo_inversor(client)
    cid = inv["cuenta"]["id"]
    assert client.get("/panel/mercado").json()["abierto"] in (True, False)
    assert client.get(f"/panel/inversores/{inv['id']}").json()["cuenta"]["id"] == cid
    r = client.post(f"/panel/cuentas/{cid}/movimientos", json={"tipo": "deposito", "moneda": "ARS", "monto": 1000})
    assert r.status_code == 201
    r = client.post(f"/panel/cuentas/{cid}/operaciones", json={"tipo": "compra", "activo_id": act["id"], "cantidad": 3})
    assert r.status_code == 201
    actividad = client.get(f"/panel/cuentas/{cid}/actividad").json()
    assert len(actividad["movimientos"]) == 1 and actividad["operaciones"]["cantidad"] == 1
    assert client.get(f"/panel/cuentas/{cid}/cartera").json()["tenencias"][0]["ticker"] == "TXAR"
    rankings = client.get("/panel/rankings").json()
    assert rankings["mas_operados"][0]["ticker"] == "TXAR" and "mas_favoritos" in rankings
    assert [a["ticker"] for a in client.get("/panel/activos").json()] == ["TXAR"]


def test_health():
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        assert c.get("/health").json() == {"status": "ok"}
