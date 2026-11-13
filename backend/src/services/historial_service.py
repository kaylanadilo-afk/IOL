"""Historial de precios para los gráficos.

Dos tablas:
  - cierres_diarios: una fila por activo y por día (apertura, máximo, mínimo, cierre, volumen).
    Se carga desde data912.com/historical (un año para atrás) y el día de hoy se va
    actualizando con cada precio nuevo: el último precio de la rueda queda como cierre.
  - cotizaciones_intradia: el precio a lo largo del día. La app guarda un punto cada vez que
    sincroniza (cada minuto) durante la rueda. Para completar las horas en que el servidor
    estuvo apagado, y los días anteriores, se completa con velas de 5 minutos de Yahoo Finance
    (solo acciones y CEDEARs; Yahoo no tiene los bonos).
"""
import bisect
import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from src.db.models.activo_model import Activo, CierreDiario, CotizacionIntradia
from src.mappers.broker_mapper import to_json
from src.repositories.broker_repository import ActivoRepository, HistorialRepository
from src.services.activo_service import obtener_activo
from src.services.cuenta_service import obtener_cuenta
from src.utils.mercado import TZ_AR, a_utc, q4

log = logging.getLogger("iol.historial")

DATA912_HIST = "https://data912.com/historical/{panel}/{ticker}"
PANEL = {"accion": "stocks", "cedear": "cedears", "bono": "bonds"}
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}"
DIAS_HISTORIAL = 400      # se guarda algo más de un año de cierres
DIAS_INTRADIA = 30        # los puntos intradiarios se guardan un mes
TIMEOUT = 15.0
FIN_RUEDA = time(17, 10)  # unos minutos después del cierre para tomar el precio final

estado_historial = {"ultima_carga": None, "resultado": None, "error": None}


def escala(activo: Activo) -> Decimal:
    """Los bonos cotizan cada 100 nominales; en la app el precio es por nominal."""
    return Decimal("0.01") if activo.tipo == "bono" else Decimal("1")


def fecha_ar(ahora: datetime) -> date:
    return a_utc(ahora).astimezone(TZ_AR).date()


def en_rueda(ahora: datetime) -> bool:
    local = a_utc(ahora).astimezone(TZ_AR)
    return local.weekday() < 5 and time(11, 0) <= local.time() <= FIN_RUEDA


def _rango_dia(d: date) -> tuple[datetime, datetime]:
    inicio = datetime.combine(d, time(0, 0), tzinfo=TZ_AR)
    return a_utc(inicio), a_utc(inicio + timedelta(days=1))


# ---------- Registro en vivo ----------
def registrar_precio(db: Session, activo: Activo, precio: Decimal, ahora: datetime) -> None:
    """Guarda un punto intradiario y actualiza el cierre del día (no hace commit)."""
    repo = HistorialRepository(db)
    momento = a_utc(ahora).replace(microsecond=0)
    if repo.intradia(activo.id, momento) is None:
        repo.add(CotizacionIntradia(activo_id=activo.id, fecha_hora=momento, precio=precio))
    hoy = fecha_ar(ahora)
    fila = repo.cierre(activo.id, hoy)
    if fila is None:
        repo.add(CierreDiario(activo_id=activo.id, fecha=hoy, apertura=precio, maximo=precio,
                              minimo=precio, cierre=precio))
    else:
        fila.cierre = precio
        fila.maximo = max(fila.maximo, precio)
        fila.minimo = min(fila.minimo, precio)


def recalcular_dia(db: Session, activo_id: int, d: date) -> None:
    """Rehace la fila diaria a partir de los puntos intradiarios de ese día."""
    repo = HistorialRepository(db)
    desde, hasta = _rango_dia(d)
    precios = [p for _, p in repo.precios_intradia(activo_id, desde, hasta)]
    if not precios:
        return
    fila = repo.cierre(activo_id, d)
    if fila is None:
        fila = CierreDiario(activo_id=activo_id, fecha=d)
        repo.add(fila)
    fila.apertura, fila.cierre = precios[0], precios[-1]
    fila.maximo, fila.minimo = max(precios), min(precios)


# ---------- Carga de historial (red) ----------
def _cierres_data912(client: httpx.Client, activo: Activo, desde: date) -> list[dict]:
    r = client.get(DATA912_HIST.format(panel=PANEL[activo.tipo], ticker=activo.ticker))
    r.raise_for_status()
    k = escala(activo)
    filas = []
    for x in r.json():
        try:
            d = date.fromisoformat(str(x["date"])[:10])
            o, h, l, c = (Decimal(str(x[c_])) * k for c_ in ("o", "h", "l", "c"))
        except (KeyError, ValueError, ArithmeticError):
            continue
        if d < desde or c <= 0:
            continue
        v = x.get("v")
        filas.append({"fecha": d, "apertura": q4(o if o > 0 else c), "maximo": q4(max(h, c)),
                      "minimo": q4(min(l, c) if l > 0 else c), "cierre": q4(c),
                      "volumen": Decimal(str(v)).quantize(Decimal("0.01")) if v is not None else None})
    return filas


def _velas_yahoo(client: httpx.Client, activo: Activo) -> list[tuple[datetime, Decimal]]:
    r = client.get(YAHOO.format(simbolo=f"{activo.ticker}.BA"),
                   params={"interval": "5m", "range": "1mo"}, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    res = (r.json().get("chart") or {}).get("result") or []
    if not res:
        return []
    ts = res[0].get("timestamp") or []
    cierres = ((res[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    puntos = []
    for t, c in zip(ts, cierres):
        if c is None or c <= 0:
            continue
        # La vela de 5 minutos empieza en t; su precio de cierre corresponde a t + 5 min
        momento = datetime.fromtimestamp(t + 300, timezone.utc)
        if en_rueda(momento):
            puntos.append((momento, q4(Decimal(str(c)) * escala(activo))))
    return puntos


def guardar_cierres(db: Session, activo: Activo, filas: list[dict]) -> int:
    if not filas:
        return 0
    repo = HistorialRepository(db)
    existentes = {c.fecha: c for c in repo.cierres_desde(activo.id, min(f["fecha"] for f in filas))}
    for f in filas:
        fila = existentes.get(f["fecha"])
        if fila is None:
            repo.add(CierreDiario(activo_id=activo.id, **f))
        else:  # el dato oficial reemplaza al que armamos en vivo
            for k, v in f.items():
                setattr(fila, k, v)
    return len(filas)


def guardar_intradia(db: Session, activo: Activo, puntos: list[tuple[datetime, Decimal]]) -> set[date]:
    """Agrega los puntos que no tengan ya uno propio a menos de 2,5 minutos. Devuelve los días tocados."""
    if not puntos:
        return set()
    repo = HistorialRepository(db)
    desde = min(p[0] for p in puntos) - timedelta(minutes=5)
    propios = sorted(a_utc(t) for t in repo.momentos_intradia(activo.id, desde))
    dias = set()
    for momento, precio in puntos:
        i = bisect.bisect_left(propios, momento)
        cerca = [propios[j] for j in (i - 1, i) if 0 <= j < len(propios)]
        if any(abs((c - momento).total_seconds()) < 150 for c in cerca):
            continue
        repo.add(CotizacionIntradia(activo_id=activo.id, fecha_hora=momento, precio=precio))
        bisect.insort(propios, momento)
        dias.add(fecha_ar(momento))
    return dias


def cargar_historial(db: Session, ahora: datetime | None = None) -> dict:
    """Trae cierres diarios (data912) e intradiario (Yahoo) para todo el catálogo y hace commit.

    Un activo que falla no frena a los demás: queda anotado en `errores`.
    """
    ahora = ahora or datetime.now(timezone.utc)
    hoy = fecha_ar(ahora)
    desde = hoy - timedelta(days=DIAS_HISTORIAL)
    res = {"cierres": 0, "puntos_intradia": 0, "activos": 0, "errores": []}
    with httpx.Client(timeout=TIMEOUT) as client:
        for activo in ActivoRepository(db).list_por_ticker():
            try:
                filas = _cierres_data912(client, activo, desde)
                res["cierres"] += guardar_cierres(db, activo, filas)
                db.flush()
            except Exception as exc:
                res["errores"].append(f"{activo.ticker} (cierres): {type(exc).__name__}")
                continue
            if activo.tipo != "bono":
                try:
                    antes = len(db.new)
                    dias = guardar_intradia(db, activo, _velas_yahoo(client, activo))
                    res["puntos_intradia"] += len(db.new) - antes
                    db.flush()
                    # Hoy todavía no está en data912: el día se arma con los puntos intradiarios
                    if hoy in dias and not any(f["fecha"] == hoy for f in filas):
                        recalcular_dia(db, activo.id, hoy)
                except Exception as exc:
                    res["errores"].append(f"{activo.ticker} (intradía): {type(exc).__name__}")
            res["activos"] += 1
    limite = a_utc(datetime.combine(hoy - timedelta(days=DIAS_INTRADIA), time(0), tzinfo=TZ_AR))
    HistorialRepository(db).borrar_intradia_anterior(limite)
    db.commit()
    return res


def cargar_y_registrar(db: Session) -> dict:
    """Carga el historial y deja el resultado en `estado_historial` (lo muestra /mercado/estado)."""
    try:
        res = cargar_historial(db)
        estado_historial.update(ultima_carga=datetime.now(timezone.utc), resultado=res, error=None)
    except Exception as exc:
        db.rollback()
        estado_historial["error"] = f"{type(exc).__name__}: {exc}"
    return estado_historial


# ---------- Consultas para los gráficos ----------
def sparklines(db: Session, dias: int, hoy: date) -> list[dict]:
    """Cierres de los últimos `dias` días de todos los activos, para los mini gráficos de las listas."""
    series: dict[int, list] = {}
    for activo_id, cierre in HistorialRepository(db).cierres_todos_desde(hoy - timedelta(days=dias)):
        series.setdefault(activo_id, []).append(cierre)
    return to_json([{"activo_id": k, "cierres": v} for k, v in series.items()])


def evolucion_cartera(db: Session, cuenta_id: int, dias: int, hoy: date) -> dict:
    """Valor en pesos de las tenencias ACTUALES a lo largo del tiempo, con los cierres de cada día.

    Es una referencia de "cómo le fue a lo que tenés hoy": no reconstruye compras y ventas pasadas.
    Los activos en dólares se pasan a pesos con el MEP de ese día (cierre AL30 / cierre AL30D).
    """
    cuenta = obtener_cuenta(db, cuenta_id)
    tenencias = [(t.activo, t.cantidad) for t in cuenta.tenencias]
    desde = hoy - timedelta(days=dias)
    ids = [a.id for a, _ in tenencias]
    mep_ids = {a.ticker: a.id for a in ActivoRepository(db).find_by_tickers(("AL30", "AL30D"))}
    filas = HistorialRepository(db).cierres_de_activos(ids + list(mep_ids.values()), desde) if ids else []
    por_fecha: dict[date, dict[int, Decimal]] = {}
    for activo_id, f, c in filas:
        por_fecha.setdefault(f, {})[activo_id] = c
    ultimo: dict[int, Decimal] = {}
    puntos = []
    for f in sorted(por_fecha):
        ultimo.update(por_fecha[f])  # si un activo no operó ese día, vale su último cierre
        al30, al30d = ultimo.get(mep_ids.get("AL30")), ultimo.get(mep_ids.get("AL30D"))
        tc = al30 / al30d if al30 and al30d else None
        valor, completo = Decimal("0"), True
        for a, cant in tenencias:
            precio = ultimo.get(a.id)
            if precio is None or (a.moneda == "USD" and tc is None):
                completo = False
                break
            valor += cant * precio * (tc if a.moneda == "USD" else 1)
        if completo:
            puntos.append({"fecha": f, "valor_ars": q4(valor)})
    var = None
    if len(puntos) >= 2 and puntos[0]["valor_ars"]:
        var = q4((puntos[-1]["valor_ars"] / puntos[0]["valor_ars"] - 1) * 100)
    return to_json({"cuenta_id": cuenta_id, "dias": dias, "puntos": puntos, "variacion_pct": var})


def historial_diario(db: Session, activo_id: int, dias: int, hoy: date) -> dict:
    activo = obtener_activo(db, activo_id)
    filas = HistorialRepository(db).cierres_desde(activo_id, hoy - timedelta(days=dias))
    puntos = [{"fecha": f.fecha, "apertura": f.apertura, "maximo": f.maximo, "minimo": f.minimo,
               "cierre": f.cierre, "volumen": f.volumen} for f in filas]
    var = None
    if len(puntos) >= 2:
        var = q4((puntos[-1]["cierre"] / puntos[0]["cierre"] - 1) * 100)
    return to_json({"activo_id": activo.id, "ticker": activo.ticker, "moneda": activo.moneda, "dias": dias,
                    "cierres": puntos, "variacion_pct": var,
                    "maximo": max((p["maximo"] for p in puntos), default=None),
                    "minimo": min((p["minimo"] for p in puntos), default=None)})


def intradia(db: Session, activo_id: int, fecha: date | None) -> dict:
    activo = obtener_activo(db, activo_id)
    repo = HistorialRepository(db)
    dias = sorted({fecha_ar(m) for m in repo.momentos_intradia(activo_id)}, reverse=True)
    fecha = fecha or (dias[0] if dias else None)
    base = {"activo_id": activo.id, "ticker": activo.ticker, "moneda": activo.moneda,
            "fecha": fecha, "dias_disponibles": dias, "puntos": [], "cierre_anterior": None, "cierre": None,
            "apertura": None, "maximo": None, "minimo": None, "ultimo": None, "variacion_pct": None}
    if fecha is None:
        return to_json(base)
    desde, hasta = _rango_dia(fecha)
    filas = repo.precios_intradia(activo_id, desde, hasta)
    anterior = repo.cierre_anterior(activo_id, fecha)
    precios = [p for _, p in filas]
    # Cierre oficial del día (incluye la subasta de cierre); el último punto intradiario puede diferir
    dia = repo.cierre(activo_id, fecha)
    base.update(
        cierre=dia.cierre if dia else None,
        puntos=[{"t": a_utc(t), "precio": p} for t, p in filas],
        cierre_anterior=anterior,
        apertura=precios[0] if precios else None,
        maximo=max(precios) if precios else None,
        minimo=min(precios) if precios else None,
        ultimo=precios[-1] if precios else None,
        variacion_pct=q4(((dia.cierre if dia else precios[-1]) / anterior - 1) * 100) if precios and anterior else None,
    )
    return to_json(base)
