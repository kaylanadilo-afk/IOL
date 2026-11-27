"""Precios reales: se prueban sin red, reemplazando las respuestas de data912 y dolarapi."""
from decimal import Decimal

import httpx
import pytest

from src.services import precios_service as precios
from tests.conftest import depositar, nuevo_activo, nuevo_inversor

DATA912 = {
    "arg_stocks": [
        {"symbol": "GGAL", "c": 4855.0, "px_bid": 4850.0, "px_ask": 4855.0, "pct_change": -2.46},
        {"symbol": "YPFD", "c": 0.0, "px_bid": 6200.0, "px_ask": 6240.0, "pct_change": 0.0},  # sin operar
    ],
    "arg_cedears": [{"symbol": "AAPL", "c": 29620.0, "px_bid": 29620.0, "px_ask": 29720.0, "pct_change": -0.19}],
    "arg_bonds": [  # cotizan cada 100 nominales
        {"symbol": "AL30", "c": 81310.0, "px_bid": 81250.0, "px_ask": 81310.0, "pct_change": -0.01},
        {"symbol": "AL30D", "c": 51.66, "px_bid": 51.65, "px_ask": 51.79, "pct_change": 0.27},
    ],
}
DOLARAPI = [{"moneda": "USD", "casa": "bolsa", "nombre": "Bolsa", "compra": 1570.7, "venta": 1573.8,
             "fechaActualizacion": "2026-11-13T11:57:00.000Z"}]


@pytest.fixture()
def red_falsa(monkeypatch):
    """Intercepta las llamadas HTTP de httpx y responde con los datos de arriba."""
    llamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        llamadas.append(str(request.url))
        if request.url.host == "data912.com":
            return httpx.Response(200, json=DATA912[request.url.path.rsplit("/", 1)[-1]])
        if request.url.host == "dolarapi.com":
            return httpx.Response(200, json=DOLARAPI)
        return httpx.Response(404)

    transporte = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(precios.httpx, "Client", lambda **kw: real_client(transport=transporte, **kw))
    monkeypatch.setattr(precios.httpx, "get", lambda url, **kw: real_client(transport=transporte).get(url, **kw))
    precios._cache_dolares.update(t=0.0, datos=None)
    return llamadas


def test_cotizaciones_escalan_bonos_y_usan_punta_si_no_opero(red_falsa):
    cot = precios.obtener_cotizaciones()
    assert cot["GGAL"] == {"precio": Decimal("4855.0000"), "variacion_pct": Decimal("-2.46"), "panel": "arg_stocks"}
    assert cot["AL30"]["precio"] == Decimal("813.1000")    # 81310 / 100
    assert cot["AL30D"]["precio"] == Decimal("0.5166")     # 51.66 / 100
    assert cot["YPFD"]["precio"] == Decimal("6220.0000")   # punto medio de la punta


def test_sincronizar_actualiza_catalogo_sin_tocar_operaciones(client, red_falsa):
    c = nuevo_inversor(client)["cuenta"]["id"]
    nuevo_activo(client, "GGAL", precio=1000)
    nuevo_activo(client, "AL30", tipo="bono", precio=1200, riesgo=2)
    nuevo_activo(client, "AL30D", tipo="bono", moneda="USD", precio=0.8, riesgo=2)
    nuevo_activo(client, "INVENTADO", precio=50)
    depositar(client, c, 100000)
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 10})

    r = client.post("/mercado/sincronizar")
    assert r.status_code == 200, r.text
    # YPFD no estaba: cotiza en el panel de acciones, así que se suma al catálogo con su precio real
    assert r.json()["actualizados"] == 4 and r.json()["sin_dato"] == ["INVENTADO"]

    activos = {a["ticker"]: a for a in client.get("/activos").json()}
    assert activos["YPFD"]["tipo"] == "accion" and activos["YPFD"]["precio_actual"] == 6220
    assert activos["GGAL"]["precio_actual"] == 4855 and activos["GGAL"]["variacion_pct"] == -2.46
    assert activos["GGAL"]["precio_actualizado"] is not None
    assert activos["INVENTADO"]["precio_actual"] == 50  # sin dato, queda el anterior
    # La operación conserva su precio (HU8) y la cartera se valoriza al precio real
    assert client.get(f"/cuentas/{c}/operaciones").json()["operaciones"][0]["precio_unitario"] == 1000
    assert client.get(f"/cuentas/{c}/cartera").json()["tenencias"][0]["valor_actual"] == 48550
    # El MEP de la app pasa a ser el real: 813.10 / 0.5166
    assert client.get(f"/cuentas/{c}/cartera").json()["tipo_cambio_mep"] == pytest.approx(1573.94, abs=0.01)


def test_si_la_fuente_falla_quedan_los_ultimos_precios(client, monkeypatch):
    nuevo_activo(client, "GGAL", precio=1000)

    def caida():
        raise httpx.ConnectError("sin conexión")

    monkeypatch.setattr(precios, "obtener_cotizaciones", caida)
    r = client.post("/mercado/sincronizar")
    assert r.status_code == 502 and "precios reales" in r.json()["detail"]
    assert client.get("/activos").json()[0]["precio_actual"] == 1000
    assert "ConnectError" in client.get("/mercado/estado").json()["precios"]["error"]


def test_dolares(client, red_falsa):
    r = client.get("/mercado/dolares")
    assert r.status_code == 200
    assert r.json()["cotizaciones"][0]["casa"] == "bolsa" and r.json()["cotizaciones"][0]["venta"] == 1573.8
    client.get("/mercado/dolares")
    assert sum("dolarapi" in u for u in red_falsa) == 1  # la segunda vez sale de la caché
