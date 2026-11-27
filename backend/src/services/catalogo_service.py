"""Catálogo ampliado de acciones y CEDEARs reales de BYMA.

Los activos se agregan solo si data912 tiene cotización para ese ticker en ese momento: el precio y la
variación del día salen de la fuente, nunca se inventan. Si un ticker no cotiza, se saltea y se vuelve a
intentar en la próxima sincronización. El nivel de riesgo (1 a 5) es la clasificación propia de la app.

Acciones: se suman TODAS las que cotizan en pesos en el panel de acciones de BYMA (data912). Las que
también cotizan en dólares (GGALD, BMA.D...) son la misma acción, así que no se repiten. El nombre de la
empresa sale de Yahoo Finanzas (misma fuente que el historial); si no lo tiene, se muestra el ticker.
"""
import logging
import re

import httpx
from sqlalchemy.orm import Session

from src.db.models.activo_model import Activo
from src.repositories.broker_repository import ActivoRepository

# ticker, nombre, nivel de riesgo
ACCIONES = [
    ("BBAR", "Banco BBVA Argentina", 4), ("SUPV", "Grupo Supervielle", 5), ("TGSU2", "Transportadora de Gas del Sur", 4),
    ("TGNO4", "Transportadora de Gas del Norte", 4), ("TECO2", "Telecom Argentina", 4), ("CRES", "Cresud", 4),
    ("IRSA", "IRSA Inversiones y Representaciones", 4), ("LOMA", "Loma Negra", 4), ("EDN", "Edenor", 5),
    ("COME", "Sociedad Comercial del Plata", 5), ("BYMA", "Bolsas y Mercados Argentinos", 3), ("MIRG", "Mirgor", 5),
    ("TRAN", "Transener", 5), ("VALO", "Grupo Financiero Valores", 5), ("CVH", "Cablevisión Holding", 5),
    ("METR", "Metrogas", 5), ("HARG", "Holcim Argentina", 3), ("BHIP", "Banco Hipotecario", 5),
    ("MOLI", "Molinos Río de la Plata", 4), ("LEDE", "Ledesma", 4), ("AUSO", "Autopistas del Sol", 4),
    ("CECO2", "Central Costanera", 5), ("DGCU2", "Distribuidora de Gas Cuyana", 4), ("AGRO", "Agrometal", 5),
]
CEDEARS = [
    ("GOOGL", "Alphabet (CEDEAR)", 3), ("AMZN", "Amazon (CEDEAR)", 3), ("META", "Meta Platforms (CEDEAR)", 4),
    ("TSLA", "Tesla (CEDEAR)", 5), ("AMD", "AMD (CEDEAR)", 4), ("INTC", "Intel (CEDEAR)", 4),
    ("NFLX", "Netflix (CEDEAR)", 4), ("DISN", "Walt Disney (CEDEAR)", 3), ("BABA", "Alibaba (CEDEAR)", 4),
    ("JPM", "JPMorgan Chase (CEDEAR)", 3), ("V", "Visa (CEDEAR)", 2), ("MA", "Mastercard (CEDEAR)", 2),
    ("WMT", "Walmart (CEDEAR)", 2), ("PEP", "PepsiCo (CEDEAR)", 2), ("MCD", "McDonald's (CEDEAR)", 2),
    ("JNJ", "Johnson & Johnson (CEDEAR)", 2), ("PFE", "Pfizer (CEDEAR)", 2), ("XOM", "ExxonMobil (CEDEAR)", 3),
    ("CVX", "Chevron (CEDEAR)", 3), ("BRKB", "Berkshire Hathaway (CEDEAR)", 2), ("QQQ", "Invesco QQQ - Nasdaq 100 (CEDEAR)", 3),
    ("DIA", "SPDR Dow Jones (CEDEAR)", 2), ("EEM", "iShares Mercados Emergentes (CEDEAR)", 3),
    ("VIST", "Vista Energy (CEDEAR)", 4), ("GLOB", "Globant (CEDEAR)", 4), ("ADBE", "Adobe (CEDEAR)", 3),
    ("CRM", "Salesforce (CEDEAR)", 3), ("ORCL", "Oracle (CEDEAR)", 3), ("AVGO", "Broadcom (CEDEAR)", 4),
    ("COIN", "Coinbase (CEDEAR)", 5), ("UBER", "Uber (CEDEAR)", 4), ("PYPL", "PayPal (CEDEAR)", 4),
    ("NKE", "Nike (CEDEAR)", 3), ("BIOX", "Bioceres (CEDEAR)", 5),
]


log = logging.getLogger("iol.precios")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}"
# Panel líder (Merval): riesgo 4. El resto del panel general, con menos volumen: riesgo 5
PANEL_LIDER = {"ALUA", "BBAR", "BMA", "BYMA", "CEPU", "COME", "CRES", "CVH", "EDN", "GGAL", "HARG", "LOMA", "METR",
               "MIRG", "PAMP", "SUPV", "TECO2", "TGNO4", "TGSU2", "TRAN", "TXAR", "VALO", "YPFD", "IRSA"}
_SUFIJOS = re.compile(r",?\s+(S\.?\s?A\.?(\s?I\.?\s?C\.?(\s?y\s?F\.?)?)?|Sociedad An[oó]nima)\s*$", re.IGNORECASE)


def nombre_yahoo(ticker: str) -> str | None:
    """Nombre de la empresa según Yahoo Finanzas (símbolo TICKER.BA). None si no lo tiene o no responde."""
    try:
        r = httpx.get(YAHOO.format(simbolo=f"{ticker}.BA"), params={"range": "1d", "interval": "1d"},
                      headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        resultado = r.json().get("chart", {}).get("result") if r.status_code == 200 else None
        meta = resultado[0].get("meta", {}) if resultado else {}
    except (httpx.HTTPError, ValueError):
        return None
    nombre = (meta.get("longName") or meta.get("shortName") or "").strip()
    if not nombre or nombre.upper() == ticker:
        return None
    if nombre.isupper():  # "HAVANNA HOLDING SA" -> "Havanna Holding SA"
        nombre = nombre.title()
    return _SUFIJOS.sub("", nombre).strip(" ,") or None


# Especies en dólares cuyo ticker no es "el de pesos + D" (TECO2 -> TECOD, TGNO4 -> TGN4D, TGSU2 -> TGSUD)
VARIANTES_DOLAR = {"TECOD", "TGN4D", "TGSUD"}


def es_variante_en_dolares(ticker: str, tickers: set[str]) -> bool:
    """GGALD, BMA.D, YPFDD: la misma acción que GGAL, BMA o YPFD, cotizada en dólares."""
    if ticker.endswith(".D") or ticker in VARIANTES_DOLAR:
        return True
    return ticker.endswith("D") and ticker[:-1] in tickers


def acciones_del_panel(cotizaciones: dict[str, dict]) -> list[str]:
    """Tickers en pesos del panel de acciones de BYMA, sin las variantes en dólares."""
    panel = {t for t, d in cotizaciones.items() if d.get("panel") == "arg_stocks"}
    return sorted(t for t in panel if not es_variante_en_dolares(t, panel))


def ampliar(db: Session, cotizaciones: dict[str, dict], buscar_nombre=nombre_yahoo) -> list[str]:
    """Agrega los activos del catálogo que falten y tengan cotización real. Devuelve los tickers agregados."""
    repo = ActivoRepository(db)
    existentes = {a.ticker for a in repo.list_por_ticker()}
    agregados = []
    # Todas las acciones del panel: las de la lista tienen nombre y riesgo definidos; el resto se completa
    conocidas = {t for t, _, _ in ACCIONES}
    for ticker in acciones_del_panel(cotizaciones):
        if ticker in existentes or ticker in conocidas or cotizaciones[ticker]["precio"] <= 0:
            continue
        dato = cotizaciones[ticker]
        nombre = buscar_nombre(ticker) or ticker
        repo.add(Activo(ticker=ticker, nombre=nombre[:120], tipo="accion", moneda="ARS", precio_actual=dato["precio"],
                        nivel_riesgo=4 if ticker in PANEL_LIDER else 5, activo=True, variacion_pct=dato.get("variacion_pct")))
        existentes.add(ticker)
        agregados.append(ticker)
    for tipo, lista in (("accion", ACCIONES), ("cedear", CEDEARS)):
        for ticker, nombre, riesgo in lista:
            dato = cotizaciones.get(ticker)
            if ticker in existentes or not dato or dato["precio"] <= 0:
                continue
            repo.add(Activo(ticker=ticker, nombre=nombre, tipo=tipo, moneda="ARS", precio_actual=dato["precio"],
                            nivel_riesgo=riesgo, activo=True, variacion_pct=dato.get("variacion_pct")))
            agregados.append(ticker)
    if agregados:
        db.flush()
    return agregados
