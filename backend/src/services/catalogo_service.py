"""Catálogo ampliado de acciones y CEDEARs reales de BYMA.

Los activos se agregan solo si data912 tiene cotización para ese ticker en ese momento: el precio y la
variación del día salen de la fuente, nunca se inventan. Si un ticker no cotiza, se saltea y se vuelve a
intentar en la próxima sincronización. El nivel de riesgo (1 a 5) es la clasificación propia de la app.
"""
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


def ampliar(db: Session, cotizaciones: dict[str, dict]) -> list[str]:
    """Agrega los activos del catálogo que falten y tengan cotización real. Devuelve los tickers agregados."""
    repo = ActivoRepository(db)
    existentes = {a.ticker for a in repo.list_por_ticker()}
    agregados = []
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
