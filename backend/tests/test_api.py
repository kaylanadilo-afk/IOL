from datetime import datetime, timedelta

import pytest

from src.utils import mercado as sv
from tests.conftest import EN_HORARIO, depositar, nuevo_activo, nuevo_inversor


# ---------- HU1 ----------
def test_alta_crea_cuenta_con_saldos_en_cero(client):
    inv = nuevo_inversor(client, "moderado")
    c = inv["cuenta"]
    assert c["saldo_ars"] == 0 and c["saldo_usd"] == 0
    assert c["numero_comitente"] > 0
    otro = nuevo_inversor(client)
    assert otro["cuenta"]["numero_comitente"] != c["numero_comitente"]


def test_email_y_cuit_unicos(client):
    inv = nuevo_inversor(client, email="a@test.com")
    r = client.post("/inversores", json={"email": "A@test.com", "nombre": "x", "cuit": "20999999990", "perfil_riesgo": "moderado", "password": "clave-segura"})
    assert r.status_code == 409 and "email" in r.json()["detail"]
    r = client.post("/inversores", json={"email": "b@test.com", "nombre": "x", "cuit": inv["cuit"], "perfil_riesgo": "moderado", "password": "clave-segura"})
    assert r.status_code == 409 and "CUIT" in r.json()["detail"]


@pytest.mark.parametrize("cuit", ["123", "2011111111A", "201111111123"])
def test_cuit_11_digitos(client, cuit):
    r = client.post("/inversores", json={"email": "c@test.com", "nombre": "x", "cuit": cuit, "perfil_riesgo": "moderado", "password": "clave-segura"})
    assert r.status_code == 422 and "11 dígitos" in r.json()["detail"]


def test_cuit_con_guiones_se_normaliza(client):
    r = client.post("/inversores", json={"email": "d@test.com", "nombre": "x", "cuit": "20-11111111-2", "perfil_riesgo": "moderado", "password": "clave-segura"})
    assert r.status_code == 201 and r.json()["cuit"] == "20111111112"


def test_alta_nunca_crea_administradores(client):
    r = client.post("/inversores", json={"email": "x@test.com", "nombre": "x", "cuit": "20999999991",
                                         "perfil_riesgo": "moderado", "es_admin": True, "password": "clave-segura"})
    assert r.status_code == 201 and r.json()["es_admin"] is False


def test_perfil_invalido(client):
    r = client.post("/inversores", json={"email": "e@test.com", "nombre": "x", "cuit": "20111111112", "perfil_riesgo": "temerario", "password": "clave-segura"})
    assert r.status_code == 422


# ---------- HU2 ----------
def test_catalogo_y_filtros(client):
    nuevo_activo(client, "GGAL")
    nuevo_activo(client, "AAPL", tipo="cedear")
    nuevo_activo(client, "GD30", tipo="bono", moneda="USD", precio=0.9)
    assert client.post("/activos", json={"ticker": "ggal", "nombre": "x", "tipo": "accion", "moneda": "ARS",
                                         "precio_actual": 1, "nivel_riesgo": 1}).status_code == 409
    assert [a["ticker"] for a in client.get("/activos?tipo=cedear").json()] == ["AAPL"]
    assert [a["ticker"] for a in client.get("/activos?moneda=USD").json()] == ["GD30"]
    assert [a["ticker"] for a in client.get("/activos?tipo=bono&moneda=ARS").json()] == []


@pytest.mark.parametrize("campo,valor", [("precio_actual", 0), ("precio_actual", -5), ("nivel_riesgo", 0),
                                         ("nivel_riesgo", 6), ("tipo", "fondo"), ("moneda", "EUR")])
def test_activo_validaciones(client, campo, valor):
    datos = {"ticker": "X", "nombre": "x", "tipo": "accion", "moneda": "ARS", "precio_actual": 10, "nivel_riesgo": 3}
    datos[campo] = valor
    assert client.post("/activos", json=datos).status_code == 422


# ---------- HU3 ----------
def test_depositos_y_extracciones(client):
    c = nuevo_inversor(client)["cuenta"]["id"]
    depositar(client, c, 1000)
    depositar(client, c, 50, "USD")
    r = client.post(f"/cuentas/{c}/extracciones", json={"moneda": "USD", "monto": 60})
    assert r.status_code == 422 and "Saldo insuficiente" in r.json()["detail"]
    assert client.post(f"/cuentas/{c}/extracciones", json={"moneda": "ARS", "monto": 400}).status_code == 201
    cuenta = client.get(f"/cuentas/{c}").json()
    assert cuenta["saldo_ars"] == 600 and cuenta["saldo_usd"] == 50
    movs = client.get(f"/cuentas/{c}/movimientos").json()
    assert [(m["tipo"], m["moneda"]) for m in movs] == [("extraccion", "ARS"), ("deposito", "USD"), ("deposito", "ARS")]


@pytest.mark.parametrize("monto", [0, -10])
def test_monto_mayor_a_cero(client, monto):
    c = nuevo_inversor(client)["cuenta"]["id"]
    assert client.post(f"/cuentas/{c}/depositos", json={"moneda": "ARS", "monto": monto}).status_code == 422


# ---------- HU4 ----------
def test_compra_descuenta_total_con_comision_y_promedia(client):
    c = nuevo_inversor(client)["cuenta"]["id"]
    a = nuevo_activo(client, "GGAL", precio=1000)
    depositar(client, c, 100000)
    r = client.post(f"/cuentas/{c}/compras", json={"activo_id": a["id"], "cantidad": 10})
    assert r.status_code == 201, r.text
    op = r.json()
    assert op["comision"] == 50 and op["total"] == 10050 and op["precio_unitario"] == 1000
    client.patch(f"/activos/{a['id']}/precio", json={"precio": 1300})
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 20})
    ten = client.get(f"/cuentas/{c}/cartera").json()["tenencias"][0]
    assert ten["cantidad"] == 30 and ten["precio_promedio"] == 1200  # (10*1000+20*1300)/30
    assert client.get(f"/cuentas/{c}").json()["saldo_ars"] == 100000 - 10050 - 26130


def test_compra_saldo_insuficiente(client):
    c = nuevo_inversor(client)["cuenta"]["id"]
    nuevo_activo(client, "GGAL", precio=1000)
    depositar(client, c, 10000)  # 10 x 1000 + 50 de comisión no alcanza
    r = client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 10})
    assert r.status_code == 422 and "Saldo insuficiente" in r.json()["detail"]


def test_compra_en_dolares_usa_saldo_usd(client):
    c = nuevo_inversor(client)["cuenta"]["id"]
    nuevo_activo(client, "GD30", tipo="bono", moneda="USD", precio=0.9)
    depositar(client, c, 1000000)
    r = client.post(f"/cuentas/{c}/compras", json={"ticker": "GD30", "cantidad": 100})
    assert r.status_code == 422  # tiene pesos pero no dólares
    depositar(client, c, 100, "USD")
    assert client.post(f"/cuentas/{c}/compras", json={"ticker": "GD30", "cantidad": 100}).status_code == 201
    assert client.get(f"/cuentas/{c}").json()["saldo_usd"] == pytest.approx(100 - 90.45)


@pytest.mark.parametrize("ahora", [
    datetime(2026, 11, 14, 12, 0, tzinfo=sv.TZ_AR),   # sábado
    datetime(2026, 11, 15, 12, 0, tzinfo=sv.TZ_AR),   # domingo
    datetime(2026, 11, 13, 10, 59, tzinfo=sv.TZ_AR),  # antes de abrir
    datetime(2026, 11, 13, 17, 0, tzinfo=sv.TZ_AR),   # al cierre
])
def test_fuera_de_horario_se_rechaza(client, reloj, ahora):
    c = nuevo_inversor(client)["cuenta"]["id"]
    nuevo_activo(client, "GGAL")
    depositar(client, c, 10000)
    reloj.ahora = ahora
    r = client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 1})
    assert r.status_code == 422 and "Mercado cerrado" in r.json()["detail"]


def test_horario_se_evalua_en_hora_argentina(client, reloj):
    c = nuevo_inversor(client)["cuenta"]["id"]
    nuevo_activo(client, "GGAL")
    depositar(client, c, 10000)
    reloj.ahora = datetime(2026, 11, 13, 14, 30).replace(tzinfo=sv.timezone.utc)  # 11:30 en Argentina
    assert client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 1}).status_code == 201


# ---------- HU5 ----------
@pytest.mark.parametrize("perfil,riesgo,ok", [
    ("conservador", 2, True), ("conservador", 3, False),
    ("moderado", 4, True), ("moderado", 5, False),
    ("agresivo", 5, True),
])
def test_perfil_de_riesgo(client, perfil, riesgo, ok):
    c = nuevo_inversor(client, perfil)["cuenta"]["id"]
    nuevo_activo(client, "X", riesgo=riesgo)
    depositar(client, c, 10000)
    r = client.post(f"/cuentas/{c}/compras", json={"ticker": "X", "cantidad": 1})
    assert (r.status_code == 201) == ok
    if not ok:
        assert "perfil" in r.json()["detail"]


def test_actualizar_perfil_habilita_compra(client):
    inv = nuevo_inversor(client, "conservador")
    c = inv["cuenta"]["id"]
    nuevo_activo(client, "X", riesgo=4)
    depositar(client, c, 10000)
    assert client.post(f"/cuentas/{c}/compras", json={"ticker": "X", "cantidad": 1}).status_code == 422
    r = client.patch(f"/inversores/{inv['id']}/perfil", json={"perfil_riesgo": "moderado", "password": "clave-segura"})
    assert r.status_code == 200 and r.json()["perfil_riesgo"] == "moderado"
    assert client.post(f"/cuentas/{c}/compras", json={"ticker": "X", "cantidad": 1}).status_code == 201


# ---------- HU6 ----------
def test_venta_acredita_neto_y_guarda_ganancia(client):
    c = nuevo_inversor(client)["cuenta"]["id"]
    a = nuevo_activo(client, "GGAL", precio=1000)
    depositar(client, c, 20000)
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 10})  # paga 10050
    client.patch(f"/activos/{a['id']}/precio", json={"precio": 1200})
    r = client.post(f"/cuentas/{c}/ventas", json={"ticker": "GGAL", "cantidad": 4})
    op = r.json()
    assert r.status_code == 201
    assert op["total"] == 4800 - 24 and op["comision"] == 24
    assert op["ganancia_realizada"] == 4 * 200 - 24
    assert client.get(f"/cuentas/{c}").json()["saldo_ars"] == 20000 - 10050 + 4776


def test_no_vende_mas_de_lo_que_tiene_y_borra_tenencia_en_cero(client):
    c = nuevo_inversor(client)["cuenta"]["id"]
    nuevo_activo(client, "GGAL", precio=100)
    depositar(client, c, 10000)
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 5})
    r = client.post(f"/cuentas/{c}/ventas", json={"ticker": "GGAL", "cantidad": 6})
    assert r.status_code == 422 and "tenés 5" in r.json()["detail"]
    assert client.post(f"/cuentas/{c}/ventas", json={"ticker": "GGAL", "cantidad": 5}).status_code == 201
    assert client.get(f"/cuentas/{c}/cartera").json()["tenencias"] == []


# ---------- HU7 ----------
def _setup_mep(client, perfil="moderado"):
    c = nuevo_inversor(client, perfil)["cuenta"]["id"]
    al30 = nuevo_activo(client, "AL30", tipo="bono", precio=1200, riesgo=2)
    al30d = nuevo_activo(client, "AL30D", tipo="bono", moneda="USD", precio=0.8, riesgo=2)
    depositar(client, c, 1000000)
    return c, al30, al30d


def test_mep_registra_dos_operaciones(client):
    c, al30, _ = _setup_mep(client)
    r = client.post(f"/cuentas/{c}/mep", json={"monto_ars": 100000})
    assert r.status_code == 201, r.text
    res = r.json()
    assert res["tipo_cambio"] == 1500  # 1200 / 0.8
    n = res["cantidad_nominales"]
    assert n == 82  # floor(100000 / (1200 * 1.005))
    assert res["compra"]["ticker"] == "AL30" and res["venta"]["ticker"] == "AL30D"
    assert res["pesos_debitados"] == pytest.approx(round(n * 1200 * 1.005, 2))
    assert res["dolares_acreditados"] == pytest.approx(round(n * 0.8 * 0.995, 2))
    cuenta = client.get(f"/cuentas/{c}").json()
    assert cuenta["saldo_ars"] == pytest.approx(1000000 - res["pesos_debitados"])
    assert cuenta["saldo_usd"] == pytest.approx(res["dolares_acreditados"])
    assert client.get(f"/cuentas/{c}/cartera").json()["tenencias"] == []  # el AL30 se vendió como AL30D
    assert client.get(f"/cuentas/{c}/operaciones").json()["cantidad"] == 2


def test_mep_si_falla_una_pata_no_se_guarda_ninguna(client):
    c, _, al30d = _setup_mep(client)
    client.patch(f"/activos/{al30d['id']}/estado", json={"activo": False})  # la venta va a fallar
    r = client.post(f"/cuentas/{c}/mep", json={"monto_ars": 100000})
    assert r.status_code == 422 and "AL30D" in r.json()["detail"]
    assert client.get(f"/cuentas/{c}").json()["saldo_ars"] == 1000000
    assert client.get(f"/cuentas/{c}/operaciones").json()["cantidad"] == 0
    assert client.get(f"/cuentas/{c}/cartera").json()["tenencias"] == []


def test_mep_monto_insuficiente(client):
    c, _, _ = _setup_mep(client)
    r = client.post(f"/cuentas/{c}/mep", json={"monto_ars": 1000})
    assert r.status_code == 422 and "no alcanza" in r.json()["detail"]


# ---------- HU8 ----------
def test_precio_y_suspension(client):
    c = nuevo_inversor(client)["cuenta"]["id"]
    a = nuevo_activo(client, "GGAL", precio=100)
    depositar(client, c, 10000)
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 2})
    assert client.patch(f"/activos/{a['id']}/precio", json={"precio": 0}).status_code == 422
    assert client.patch(f"/activos/{a['id']}/precio", json={"precio": 150}).json()["precio_actual"] == 150
    assert client.get(f"/cuentas/{c}/operaciones").json()["operaciones"][0]["precio_unitario"] == 100
    client.patch(f"/activos/{a['id']}/estado", json={"activo": False})
    for accion in ("compras", "ventas"):
        r = client.post(f"/cuentas/{c}/{accion}", json={"ticker": "GGAL", "cantidad": 1})
        assert r.status_code == 422 and "suspendido" in r.json()["detail"]


# ---------- HU9 ----------
def test_dividendo_acredita_a_cada_tenedor(client):
    a = nuevo_activo(client, "KO", tipo="cedear", precio=100)
    cuentas = []
    for cant in (10, 25):
        c = nuevo_inversor(client)["cuenta"]["id"]
        depositar(client, c, 10000)
        client.post(f"/cuentas/{c}/compras", json={"ticker": "KO", "cantidad": cant})
        cuentas.append(c)
    sin_tenencia = nuevo_inversor(client)["cuenta"]["id"]
    saldos = [client.get(f"/cuentas/{c}").json()["saldo_ars"] for c in cuentas]
    r = client.post("/dividendos", json={"activo_id": a["id"], "monto_por_unidad": 2.5})
    assert r.status_code == 201
    assert r.json()["cuentas_acreditadas"] == 2 and r.json()["total_pagado"] == 87.5
    for c, cant, antes in zip(cuentas, (10, 25), saldos):
        assert client.get(f"/cuentas/{c}").json()["saldo_ars"] == pytest.approx(antes + cant * 2.5)
        mov = client.get(f"/cuentas/{c}/movimientos").json()[0]
        assert mov["tipo"] == "dividendo" and mov["monto"] == cant * 2.5
    assert client.get(f"/cuentas/{sin_tenencia}/movimientos").json() == []


def test_bonos_no_pagan_dividendos(client):
    a = nuevo_activo(client, "AL30", tipo="bono")
    r = client.post("/dividendos", json={"activo_id": a["id"], "monto_por_unidad": 1})
    assert r.status_code == 422


# ---------- HU10 ----------
def test_cartera_valorizada(client):
    c = nuevo_inversor(client)["cuenta"]["id"]
    g = nuevo_activo(client, "GGAL", precio=1000)
    nuevo_activo(client, "AAPL", tipo="cedear", precio=500)
    nuevo_activo(client, "AL30", tipo="bono", precio=1500, riesgo=2)
    nuevo_activo(client, "AL30D", tipo="bono", moneda="USD", precio=1, riesgo=2)  # MEP = 1500
    depositar(client, c, 100000)
    depositar(client, c, 100, "USD")
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 10})
    client.post(f"/cuentas/{c}/compras", json={"ticker": "AAPL", "cantidad": 20})
    client.post(f"/cuentas/{c}/compras", json={"ticker": "AL30D", "cantidad": 20})
    client.patch(f"/activos/{g['id']}/precio", json={"precio": 1100})
    cart = client.get(f"/cuentas/{c}/cartera").json()
    ggal = next(t for t in cart["tenencias"] if t["ticker"] == "GGAL")
    assert ggal["valor_actual"] == 11000 and ggal["rendimiento_pct"] == 10
    assert cart["total_valorizado"] == {"ARS": 21000, "USD": 20}
    assert cart["saldos_disponibles"]["USD"] == pytest.approx(100 - 20.1)
    comp = {x["tipo"]: x["porcentaje"] for x in cart["composicion_por_tipo"]}
    # accion 11000, cedear 10000, bono 20 USD * 1500 = 30000 -> total 51000
    assert comp == {"bono": pytest.approx(58.82), "accion": pytest.approx(21.57), "cedear": pytest.approx(19.61)}


# ---------- HU11 ----------
def test_historial_filtros_orden_y_comisiones(client, reloj):
    c = nuevo_inversor(client)["cuenta"]["id"]
    nuevo_activo(client, "GGAL", precio=1000)
    nuevo_activo(client, "AAPL", tipo="cedear", precio=2000)
    depositar(client, c, 1000000)
    # EN_HORARIO es viernes 13: martes 3, martes 10 y jueves 12 son días hábiles
    for dias, tipo, ticker in ((10, "compras", "GGAL"), (3, "compras", "AAPL"), (1, "ventas", "GGAL")):
        reloj.ahora = EN_HORARIO - timedelta(days=dias)
        client.post(f"/cuentas/{c}/{tipo}", json={"ticker": ticker, "cantidad": 10})
    todas = client.get(f"/cuentas/{c}/operaciones").json()
    assert [o["ticker"] for o in todas["operaciones"]] == ["GGAL", "AAPL", "GGAL"]  # fecha descendente
    assert todas["total_comisiones"]["ARS"] == 50 + 100 + 50
    r = client.get(f"/cuentas/{c}/operaciones?ticker=ggal&tipo=compra").json()
    assert r["cantidad"] == 1 and r["total_comisiones"]["ARS"] == 50
    desde = (EN_HORARIO - timedelta(days=6)).date()
    r = client.get(f"/cuentas/{c}/operaciones?desde={desde}&hasta={EN_HORARIO.date()}").json()
    assert [o["ticker"] for o in r["operaciones"]] == ["GGAL", "AAPL"]
    assert client.get(f"/cuentas/{c}/operaciones?desde=2026-02-01&hasta=2026-01-01").status_code == 422


# ---------- HU12 ----------
def test_rankings(client, reloj):
    activos = {t: nuevo_activo(client, t, precio=100) for t in ("A", "B", "C")}
    inv = nuevo_inversor(client)
    c = inv["cuenta"]["id"]
    depositar(client, c, 1000000)
    reloj.ahora = EN_HORARIO - timedelta(days=10)  # fuera de los 7 días
    client.post(f"/cuentas/{c}/compras", json={"ticker": "C", "cantidad": 1000})
    reloj.ahora = EN_HORARIO
    client.post(f"/cuentas/{c}/compras", json={"ticker": "A", "cantidad": 10})
    client.post(f"/cuentas/{c}/compras", json={"ticker": "B", "cantidad": 30})
    assert [r["ticker"] for r in client.get("/activos/mas-operados").json()] == ["B", "A"]

    otro = nuevo_inversor(client)
    for i, t in ((inv["id"], "A"), (otro["id"], "A"), (otro["id"], "C")):
        assert client.post(f"/inversores/{i}/favoritos/{activos[t]['id']}").status_code == 200
    fav = client.get("/activos/mas-favoritos").json()
    assert [(f["ticker"], f["favoritos"]) for f in fav] == [("A", 2), ("C", 1)]
    client.delete(f"/inversores/{otro['id']}/favoritos/{activos['A']['id']}")
    assert client.get("/activos/mas-favoritos").json()[0]["favoritos"] == 1


def test_ganancias_realizadas_por_anio(client, reloj):
    c = nuevo_inversor(client)["cuenta"]["id"]
    a = nuevo_activo(client, "GGAL", precio=100)
    depositar(client, c, 100000)
    reloj.ahora = datetime(2025, 3, 3, 12, tzinfo=sv.TZ_AR)
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 100})
    client.patch(f"/activos/{a['id']}/precio", json={"precio": 200})
    client.post(f"/cuentas/{c}/ventas", json={"ticker": "GGAL", "cantidad": 50})  # 50*100 - 50 = 4950
    reloj.ahora = EN_HORARIO
    client.patch(f"/activos/{a['id']}/precio", json={"precio": 80})
    client.post(f"/cuentas/{c}/ventas", json={"ticker": "GGAL", "cantidad": 50})  # -50*20 - 20 = -1020
    r = client.get(f"/cuentas/{c}/ganancias-realizadas").json()
    assert [(x["anio"], x["ARS"]) for x in r["por_anio"]] == [(2026, -1020), (2025, 4950)]


def test_404(client):
    assert client.get("/cuentas/999/cartera").status_code == 404
    assert client.get("/activos/999").status_code == 404
    assert client.patch("/inversores/999/perfil", json={"perfil_riesgo": "moderado", "password": "clave-segura"}).status_code == 404
