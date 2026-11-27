"""Historial de precios (cierres diarios e intradiario). Sin red: data912 y Yahoo se simulan."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest

from src.services import historial_service as historial
from src.services import precios_service as precios
from src.utils import mercado as sv
from src.db.connection import get_db
from src.app import app
from src.db.models.activo_model import CotizacionIntradia
from tests.conftest import EN_HORARIO, nuevo_activo

VIERNES = EN_HORARIO.date()          # 13/11/2026
JUEVES = VIERNES - timedelta(days=1)


def sesion():
    """Sesión de la misma base que usa el cliente de test."""
    gen = app.dependency_overrides[get_db]()
    return next(gen), gen


def patch_precio(client, reloj, activo_id, precio, cuando):
    reloj.ahora = cuando
    r = client.patch(f"/activos/{activo_id}/precio", json={"precio": precio}, headers=client.admin)
    assert r.status_code == 200, r.text


def a_las(d: date, h: int, m: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=sv.TZ_AR)


# ---------- registro en vivo ----------
def test_cambios_de_precio_arman_el_dia_y_el_cierre(client, reloj):
    a = nuevo_activo(client, "GGAL", precio=100)
    patch_precio(client, reloj, a["id"], 90, a_las(JUEVES, 16, 50))   # cierre del jueves
    patch_precio(client, reloj, a["id"], 100, a_las(VIERNES, 11, 0))
    patch_precio(client, reloj, a["id"], 120, a_las(VIERNES, 12, 0))
    patch_precio(client, reloj, a["id"], 95, a_las(VIERNES, 13, 0))
    patch_precio(client, reloj, a["id"], 110, a_las(VIERNES, 16, 59))

    dia = client.get(f"/activos/{a['id']}/intradia").json()
    assert dia["fecha"] == str(VIERNES)
    assert [p["precio"] for p in dia["puntos"]] == [100, 120, 95, 110]
    assert (dia["apertura"], dia["maximo"], dia["minimo"], dia["ultimo"]) == (100, 120, 95, 110)
    assert dia["cierre_anterior"] == 90 and dia["variacion_pct"] == pytest.approx(22.22, abs=0.01)
    assert dia["dias_disponibles"] == [str(VIERNES), str(JUEVES)]

    jueves = client.get(f"/activos/{a['id']}/intradia?fecha={JUEVES}").json()
    assert [p["precio"] for p in jueves["puntos"]] == [90]

    hist = client.get(f"/activos/{a['id']}/historial?dias=30").json()
    assert [(c["fecha"], c["cierre"]) for c in hist["cierres"]] == [(str(JUEVES), 90), (str(VIERNES), 110)]
    v = hist["cierres"][-1]
    assert (v["apertura"], v["maximo"], v["minimo"]) == (100, 120, 95)
    assert hist["variacion_pct"] == pytest.approx(22.22, abs=0.01)


def test_intradia_sin_datos(client):
    a = nuevo_activo(client, "GGAL")
    r = client.get(f"/activos/{a['id']}/intradia").json()
    assert r["puntos"] == [] and r["fecha"] is None and r["dias_disponibles"] == []
    assert client.get("/activos/999/intradia").status_code == 404
    assert client.get("/activos/999/historial").status_code == 404


def test_sincronizacion_solo_guarda_historial_en_horario_de_rueda(client):
    nuevo_activo(client, "GGAL", precio=100)
    db, gen = sesion()
    cot = {"GGAL": {"precio": Decimal("105"), "variacion_pct": Decimal("5")}}
    precios.aplicar_cotizaciones(db, cot, a_las(VIERNES, 9, 30))    # antes de abrir
    precios.aplicar_cotizaciones(db, cot, a_las(VIERNES, 11, 30))   # en rueda
    precios.aplicar_cotizaciones(db, cot, a_las(VIERNES, 18, 0))    # después del cierre
    db.commit()
    gen.close()
    assert len(client.get("/activos/1/intradia").json()["puntos"]) == 1


# ---------- carga de historial ----------
def _velas(dia: date, precios_: list[float]) -> dict:
    inicio = int(a_las(dia, 11, 0).timestamp())
    return {"chart": {"result": [{"timestamp": [inicio + 300 * i for i in range(len(precios_))],
                                  "indicators": {"quote": [{"close": precios_}]}}]}}


@pytest.fixture()
def red_historial(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "data912.com/historical/stocks/GGAL" in url:
            return httpx.Response(200, json=[
                {"date": "2025-01-02", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1},  # fuera de rango
                {"date": str(JUEVES - timedelta(days=1)), "o": 80, "h": 85, "l": 79, "c": 84, "v": 1000},
                {"date": str(JUEVES), "o": 84, "h": 92, "l": 83, "c": 90, "v": 2000}])
        if "data912.com/historical/bonds/AL30" in url:
            return httpx.Response(200, json=[{"date": str(JUEVES), "o": 81000, "h": 81500, "l": 80900, "c": 81310, "v": 5}])
        if "data912.com/historical/stocks/ROTO" in url:
            return httpx.Response(500)
        if "yahoo.com" in url and "GGAL.BA" in url:
            return httpx.Response(200, json=_velas(VIERNES, [91, 93, None, 95]))
        return httpx.Response(404)

    real = httpx.Client
    monkeypatch.setattr(historial.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def test_cargar_historial(client, reloj, red_historial):
    g = nuevo_activo(client, "GGAL", precio=100)
    b = nuevo_activo(client, "AL30", tipo="bono", precio=800, riesgo=2)
    nuevo_activo(client, "ROTO", precio=10)
    # Un punto propio a las 11:10: la vela de Yahoo de las 11:10 no se duplica
    patch_precio(client, reloj, g["id"], 92.5, a_las(VIERNES, 11, 10))
    # Un punto viejo que tiene que borrarse (más de 30 días)
    db, gen = sesion()
    db.add(CotizacionIntradia(activo_id=g["id"], fecha_hora=sv.a_utc(a_las(VIERNES - timedelta(days=45), 12)),
                              precio=Decimal("1")))
    db.commit()

    res = historial.cargar_historial(db, sv.a_utc(a_las(VIERNES, 12, 0)))
    gen.close()
    assert res["errores"] == ["ROTO (cierres): HTTPStatusError"]
    assert res["cierres"] == 3  # 2 de GGAL (el de 2025 queda afuera) + 1 de AL30

    hist = client.get(f"/activos/{g['id']}/historial?dias=30").json()["cierres"]
    assert [(c["fecha"], c["cierre"]) for c in hist] == [
        (str(JUEVES - timedelta(days=1)), 84), (str(JUEVES), 90), (str(VIERNES), 95)]
    assert hist[1]["volumen"] == 2000
    # El día de hoy se rehízo con todos los puntos: 91 (11:05), 92.5 propio (11:10), 95 (11:20)
    assert (hist[2]["apertura"], hist[2]["maximo"], hist[2]["minimo"]) == (91, 95, 91)
    dia = client.get(f"/activos/{g['id']}/intradia").json()
    assert [p["precio"] for p in dia["puntos"]] == [91, 92.5, 95]
    assert dia["cierre_anterior"] == 90
    assert str((VIERNES - timedelta(days=45))) not in dia["dias_disponibles"]
    # Bonos: se pasa de precio cada 100 nominales a precio por nominal
    assert client.get(f"/activos/{b['id']}/historial").json()["cierres"][0]["cierre"] == 813.1


def test_cargar_historial_dos_veces_no_duplica(client, red_historial):
    g = nuevo_activo(client, "GGAL", precio=100)
    for _ in range(2):
        db, gen = sesion()
        historial.cargar_historial(db, sv.a_utc(a_las(VIERNES, 12, 0)))
        gen.close()
    assert len(client.get(f"/activos/{g['id']}/intradia").json()["puntos"]) == 3
    assert len(client.get(f"/activos/{g['id']}/historial").json()["cierres"]) == 3


def test_evolucion_y_sparklines(client, reloj):
    from tests.conftest import depositar, nuevo_inversor
    c = nuevo_inversor(client)["cuenta"]["id"]
    a = nuevo_activo(client, "GGAL", precio=100)
    b = nuevo_activo(client, "GD30D", tipo="bono", moneda="USD", precio=0.5, riesgo=2)
    al30 = nuevo_activo(client, "AL30", tipo="bono", precio=800, riesgo=2)
    al30d = nuevo_activo(client, "AL30D", tipo="bono", moneda="USD", precio=0.5, riesgo=2)
    depositar(client, c, 100000); depositar(client, c, 100, "USD")
    reloj.ahora = a_las(VIERNES, 12)
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 10})
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GD30D", "cantidad": 100})
    # Cierres: jueves y viernes (el MEP de cada día sale de AL30 / AL30D)
    for dia, pg, pb, p30, p30d in ((JUEVES, 90, 0.4, 800, 0.5), (VIERNES, 110, 0.5, 900, 0.5)):
        for act, p in ((a, pg), (b, pb), (al30, p30), (al30d, p30d)):
            patch_precio(client, reloj, act["id"], p, a_las(dia, 16))
    ev = client.get(f"/cuentas/{c}/evolucion?dias=30").json()
    # jueves: 10*90 + 100*0.4*1600 = 64900 ; viernes: 10*110 + 100*0.5*1800 = 91100
    assert [(p["fecha"], p["valor_ars"]) for p in ev["puntos"]] == [(str(JUEVES), 64900), (str(VIERNES), 91100)]
    assert ev["variacion_pct"] == pytest.approx(40.37, abs=0.01)
    sp = {s["activo_id"]: s["cierres"] for s in client.get("/activos/sparklines?dias=30").json()}
    assert sp[a["id"]] == [90, 110]


def test_historial_rango_por_defecto_tres_meses(client, reloj):
    a = nuevo_activo(client, "GGAL", precio=100)
    patch_precio(client, reloj, a["id"], 50, a_las(VIERNES - timedelta(days=120), 12))
    patch_precio(client, reloj, a["id"], 80, a_las(VIERNES - timedelta(days=60), 12))
    patch_precio(client, reloj, a["id"], 100, a_las(VIERNES, 12))
    r = client.get(f"/activos/{a['id']}/historial").json()
    assert r["dias"] == 90 and [c["cierre"] for c in r["cierres"]] == [80, 100]
    assert r["variacion_pct"] == 25
    assert len(client.get(f"/activos/{a['id']}/historial?dias=365").json()["cierres"]) == 3
    assert client.get(f"/activos/{a['id']}/historial?dias=0").status_code == 422


def test_si_data912_no_tiene_cierres_se_usan_los_de_yahoo(client, monkeypatch):
    from datetime import datetime, timezone

    import httpx

    from src.app import app
    from src.db.connection import get_db
    from src.services import historial_service as hs

    nuevo_activo(client, "ORCL", tipo="cedear", precio=60000)
    t = int(datetime(2026, 11, 12, 20, 0, tzinfo=timezone.utc).timestamp())
    yahoo = {"chart": {"result": [{"timestamp": [t], "indicators": {"quote": [
        {"open": [61000.0], "high": [62000.0], "low": [60500.0], "close": [61500.0], "volume": [2500]}]}}]}}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "data912.com":
            return httpx.Response(404, json={"detail": "Not Found"})
        if request.url.params.get("interval") == "1d":
            return httpx.Response(200, json=yahoo)
        return httpx.Response(200, json={"chart": {"result": []}})

    real = httpx.Client
    monkeypatch.setattr(hs.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    db = next(app.dependency_overrides[get_db]())
    res = hs.cargar_historial(db, datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc))
    db.close()
    assert res["errores"] == [] and res["cierres"] == 1


def test_serie_congelada_de_yahoo_no_se_guarda(client, monkeypatch, reloj):
    """Yahoo repite siempre el mismo precio sin volumen para algunas acciones (p. ej. A3): se descarta,
    se borra lo que hubiera de antes y la evolución usa el precio actual del activo."""
    from tests.conftest import depositar, nuevo_inversor
    from src.db.models.activo_model import CierreDiario
    from sqlalchemy import select

    a = nuevo_activo(client, "A3", precio=2600)
    c = nuevo_inversor(client)["cuenta"]["id"]
    depositar(client, c, 100000)
    reloj.ahora = a_las(VIERNES, 12)
    client.post(f"/cuentas/{c}/compras", json={"ticker": "A3", "cantidad": 2})
    patch_precio(client, reloj, a["id"], 2610, a_las(VIERNES, 12))  # precio en vivo de la rueda
    # Quedó guardado un cierre congelado de una carga anterior
    db, _ = sesion()
    db.add(CierreDiario(activo_id=a["id"], fecha=JUEVES, apertura=2215, maximo=2215, minimo=2215, cierre=2215, volumen=0))
    db.commit()

    dias = [datetime(2026, 10, 1, 20, tzinfo=timezone.utc) + timedelta(days=i) for i in range(20)]
    yahoo = {"chart": {"result": [{"timestamp": [int(d.timestamp()) for d in dias], "indicators": {"quote": [
        {"open": [2215.0] * 20, "high": [2215.0] * 20, "low": [2215.0] * 20, "close": [2215.0] * 20, "volume": [0] * 20}]}}]}}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "data912.com":
            return httpx.Response(200, json={"Error": "no tengo ese ticker"})
        if request.url.params.get("interval") == "1d":
            return httpx.Response(200, json=yahoo)
        return httpx.Response(200, json={"chart": {"result": []}})

    real = httpx.Client
    monkeypatch.setattr(historial.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    res = historial.cargar_historial(db, datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc))
    assert res["descartados"] == ["A3"] and res["errores"] == []
    assert [x.cierre for x in db.scalars(select(CierreDiario).where(CierreDiario.activo_id == a["id"]))] == [2610]
    db.close()
    # La evolución usa lo que hay (el cierre en vivo del viernes)
    ev = client.get(f"/cuentas/{c}/evolucion?dias=30").json()
    assert [p["valor_ars"] for p in ev["puntos"]] == [5220]


def test_evolucion_con_un_activo_sin_historial_usa_su_precio_actual(client, reloj):
    from tests.conftest import depositar, nuevo_inversor
    c = nuevo_inversor(client)["cuenta"]["id"]
    a = nuevo_activo(client, "GGAL", precio=100)
    nuevo_activo(client, "A3", precio=2600)
    depositar(client, c, 100000)
    reloj.ahora = a_las(VIERNES, 12)
    client.post(f"/cuentas/{c}/compras", json={"ticker": "GGAL", "cantidad": 10})
    client.post(f"/cuentas/{c}/compras", json={"ticker": "A3", "cantidad": 1})
    db, _ = sesion()
    db.query(historial.CierreDiario).delete()
    db.commit(); db.close()
    for dia, p in ((JUEVES, 90), (VIERNES, 110)):
        patch_precio(client, reloj, a["id"], p, a_las(dia, 16))
    ev = client.get(f"/cuentas/{c}/evolucion?dias=30").json()
    # A3 no tiene cierres: entra con su precio actual (2600) en los dos días
    assert [p["valor_ars"] for p in ev["puntos"]] == [900 + 2600, 1100 + 2600]
