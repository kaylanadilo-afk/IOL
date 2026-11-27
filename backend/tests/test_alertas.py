"""Alertas de precio: configuración, disparo automático, un solo aviso por cruce y catálogo ampliado."""
from decimal import Decimal

import pytest

from src.app import app
from src.db.connection import get_db
from src.services import catalogo_service
from src.services.alertas_service import AlertasService
from src.utils import correo
from tests.conftest import PASSWORD, nuevo_activo, nuevo_inversor


@pytest.fixture
def mails(monkeypatch):
    enviados = []
    def despachar(destino, asunto, texto, html, al_enviar=None):
        enviados.append((destino, asunto, texto))
        if al_enviar:  # el correo "salió": se marca como enviado
            al_enviar()
    monkeypatch.setattr(correo, "despachar", despachar)
    return enviados


def sesion(client, inv=None):
    inv = inv or nuevo_inversor(client)
    token = client.post("/auth/ingresar", json={"email": inv["email"], "password": PASSWORD}).json()["token"]
    return inv, {"Authorization": f"Bearer {token}"}


def precio(client, activo_id, valor):
    r = client.patch(f"/activos/{activo_id}/precio", json={"precio": valor}, headers=client.admin)
    assert r.status_code == 200, r.text


def test_alertas_requieren_sesion_y_son_de_cada_uno(client):
    act = nuevo_activo(client, "YPFD", precio=1000)
    assert client.get("/alertas").status_code == 401
    _, h1 = sesion(client)
    _, h2 = sesion(client)
    al = client.post("/alertas", json={"activo_id": act["id"], "tipo": "baja_pct", "valor": 20}, headers=h1).json()
    assert client.get("/alertas", headers=h2).json() == []
    assert client.put(f"/alertas/{al['id']}", json={"valor": 10}, headers=h2).status_code == 404
    assert client.delete(f"/alertas/{al['id']}", headers=h2).status_code == 404


def test_objetivo_se_calcula_desde_el_precio_al_crearla(client):
    act = nuevo_activo(client, "GGAL", precio=1000)
    _, h = sesion(client)
    baja = client.post("/alertas", json={"activo_id": act["id"], "tipo": "baja_pct", "valor": 20}, headers=h).json()
    sube = client.post("/alertas", json={"activo_id": act["id"], "tipo": "sube_pct", "valor": 31}, headers=h).json()
    fijo = client.post("/alertas", json={"activo_id": act["id"], "tipo": "precio", "valor": 900}, headers=h).json()
    assert (baja["precio_referencia"], baja["precio_objetivo"], baja["direccion"]) == (1000, 800, "baja")
    assert (sube["precio_objetivo"], sube["direccion"]) == (1310, "sube")
    assert (fijo["precio_objetivo"], fijo["direccion"]) == (900, "baja")
    r = client.post("/alertas", json={"activo_id": act["id"], "tipo": "baja_pct", "valor": 100}, headers=h)
    assert r.status_code == 422
    r = client.post("/alertas", json={"activo_id": act["id"], "tipo": "precio", "valor": 1000}, headers=h)
    assert r.status_code == 422 and "campos" in r.json()
    r = client.post("/alertas", json={"activo_id": act["id"], "tipo": "precio", "valor": 5, "aviso_email": False,
                                      "aviso_app": False}, headers=h)
    assert r.status_code == 422


def test_dispara_una_sola_vez_con_mail_y_aviso(client, mails):
    act = nuevo_activo(client, "YPFD", precio=1000)
    inv, h = sesion(client)
    al = client.post("/alertas", json={"activo_id": act["id"], "tipo": "baja_pct", "valor": 20}, headers=h).json()
    precio(client, act["id"], 850)  # todavía no llega
    assert mails == [] and client.get("/notificaciones", headers=h).json()["no_leidas"] == 0
    precio(client, act["id"], 790)
    precio(client, act["id"], 700)  # sigue abajo: no se repite
    assert len(mails) == 1
    destino, asunto, texto = mails[0]
    assert destino == inv["email"] and asunto == "Alerta de precio: YPFD" and "bajó un 21 %" in texto
    alerta = client.get("/alertas", headers=h).json()[0]
    assert alerta["id"] == al["id"] and alerta["estado"] == "ejecutada" and alerta["veces_disparada"] == 1
    avisos = client.get("/notificaciones", headers=h).json()
    assert avisos["no_leidas"] == 1 and avisos["items"][0]["precio"] == 790 and avisos["items"][0]["email_enviado"]
    assert client.post("/notificaciones/leidas", headers=h).status_code == 204
    assert client.get("/notificaciones", headers=h).json()["no_leidas"] == 0


def test_revisiones_simultaneas_no_duplican(client, mails):
    act = nuevo_activo(client, "BMA", precio=100)
    _, h = sesion(client)
    client.post("/alertas", json={"activo_id": act["id"], "tipo": "precio", "valor": 120}, headers=h)
    db = next(app.dependency_overrides[get_db]())
    from src.db.models.activo_model import Activo
    db.get(Activo, act["id"]).precio_actual = Decimal("125")
    db.commit()
    assert AlertasService(db).evaluar() == 1
    assert AlertasService(db).evaluar() == 0
    db.close()
    assert len(mails) == 1


def test_pausada_no_avisa_y_al_reactivarla_se_rearma(client, mails):
    act = nuevo_activo(client, "TXAR", precio=100)
    _, h = sesion(client)
    al = client.post("/alertas", json={"activo_id": act["id"], "tipo": "sube_pct", "valor": 10}, headers=h).json()
    assert client.patch(f"/alertas/{al['id']}/estado", json={"estado": "pausada"}, headers=h).json()["estado"] == "pausada"
    precio(client, act["id"], 115)
    assert mails == []
    r = client.patch(f"/alertas/{al['id']}/estado", json={"estado": "activa"}, headers=h).json()
    assert r["estado"] == "activa" and r["precio_objetivo"] == 110  # sigue con su referencia original
    precio(client, act["id"], 116)
    assert len(mails) == 1


def test_recurrente_por_porcentaje_se_mide_desde_el_ultimo_aviso(client, mails):
    act = nuevo_activo(client, "PAMP", precio=100)
    _, h = sesion(client)
    al = client.post("/alertas", json={"activo_id": act["id"], "tipo": "sube_pct", "valor": 10, "recurrente": True},
                     headers=h).json()
    precio(client, act["id"], 111)
    assert len(mails) == 1
    a = client.get("/alertas", headers=h).json()[0]
    assert a["estado"] == "activa" and a["precio_referencia"] == 111 and a["precio_objetivo"] == 122.1
    precio(client, act["id"], 123)
    assert len(mails) == 2 and client.get("/alertas", headers=h).json()[0]["veces_disparada"] == 2
    assert al["id"] == a["id"]


def test_editar_cambia_la_referencia_y_borrar(client):
    act = nuevo_activo(client, "CEPU", precio=100)
    _, h = sesion(client)
    al = client.post("/alertas", json={"activo_id": act["id"], "tipo": "baja_pct", "valor": 10}, headers=h).json()
    precio(client, act["id"], 95)
    r = client.put(f"/alertas/{al['id']}", json={"valor": 20}, headers=h).json()
    assert r["precio_referencia"] == 95 and r["precio_objetivo"] == 76
    assert client.delete(f"/alertas/{al['id']}", headers=h).status_code == 204
    assert client.get("/alertas", headers=h).json() == []


def test_catalogo_solo_agrega_activos_con_cotizacion_real(client):
    db = next(app.dependency_overrides[get_db]())
    cot = {"BBAR": {"precio": Decimal("5000"), "variacion_pct": Decimal("1.5")}, "TSLA": {"precio": Decimal("30000"), "variacion_pct": None}}
    assert sorted(catalogo_service.ampliar(db, cot)) == ["BBAR", "TSLA"]
    db.commit()
    assert catalogo_service.ampliar(db, cot) == []  # no se duplican
    db.close()
    tickers = {a["ticker"]: a for a in client.get("/activos").json()}
    assert tickers["BBAR"]["precio_actual"] == 5000 and tickers["BBAR"]["tipo"] == "accion"
    assert tickers["TSLA"]["tipo"] == "cedear" and "SUPV" not in tickers


def test_editar_una_pausada_la_deja_pausada(client):
    act = nuevo_activo(client, "LOMA", precio=100)
    _, h = sesion(client)
    al = client.post("/alertas", json={"activo_id": act["id"], "tipo": "baja_pct", "valor": 10}, headers=h).json()
    client.patch(f"/alertas/{al['id']}/estado", json={"estado": "pausada"}, headers=h)
    r = client.put(f"/alertas/{al['id']}", json={"valor": 25}, headers=h).json()
    assert r["estado"] == "pausada" and r["precio_objetivo"] == 75


def test_suma_todas_las_acciones_del_panel_sin_las_de_dolares(client):
    db = next(app.dependency_overrides[get_db]())
    cot = {t: {"precio": Decimal("100"), "variacion_pct": None, "panel": "arg_stocks"}
           for t in ("HAVA", "GGAL", "GGALD", "BMA.D", "TECO2", "TECOD", "EDLH")}
    cot["AAPL"] = {"precio": Decimal("500"), "variacion_pct": None, "panel": "arg_cedears"}
    nombres = {"HAVA": "Havanna Holding"}
    agregados = catalogo_service.ampliar(db, cot, buscar_nombre=nombres.get)
    db.commit()
    db.close()
    assert sorted(agregados) == ["EDLH", "GGAL", "HAVA", "TECO2"]
    activos = {a["ticker"]: a for a in client.get("/activos").json()}
    assert activos["HAVA"]["nombre"] == "Havanna Holding" and activos["HAVA"]["nivel_riesgo"] == 5
    assert activos["EDLH"]["nombre"] == "EDLH"  # sin nombre en la fuente: se muestra el ticker
    assert activos["GGAL"]["nivel_riesgo"] == 4 and "GGALD" not in activos and "TECOD" not in activos
