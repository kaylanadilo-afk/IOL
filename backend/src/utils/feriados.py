"""Feriados de Argentina: BYMA no opera esos días.

La lista de cada año sale de api.argentinadatos.com (feriados nacionales, móviles y puentes). Se carga en
segundo plano y queda en memoria. Si la fuente no responde, se usan igual los feriados de fecha fija (esos no
cambian nunca), así que la app sigue funcionando.
"""
import logging
import threading
from datetime import date

import httpx

log = logging.getLogger("iol.precios")
URL = "https://api.argentinadatos.com/v1/feriados/{anio}"
# Feriados nacionales que caen siempre el mismo día (mes, día)
FIJOS = {(1, 1), (3, 24), (4, 2), (5, 1), (5, 25), (6, 20), (7, 9), (12, 8), (12, 25)}

_por_anio: dict[int, set[date]] = {}
_lock = threading.Lock()


def cargar(anio: int) -> bool:
    """Trae los feriados del año. Devuelve False si no se pudo (se reintenta en la próxima carga)."""
    try:
        r = httpx.get(URL.format(anio=anio), timeout=8)
        r.raise_for_status()
        dias = {date.fromisoformat(x["fecha"]) for x in r.json() if x.get("fecha")}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        log.warning("No se pudieron cargar los feriados de %s: %s", anio, type(e).__name__)
        return False
    with _lock:
        _por_anio[anio] = dias
    return True


def cargar_si_falta(hoy: date) -> None:
    """Para la tarea de fondo: deja cargados este año y el siguiente."""
    for anio in (hoy.year, hoy.year + 1):
        if anio not in _por_anio:
            cargar(anio)


def es_feriado(d: date) -> bool:
    if (d.month, d.day) in FIJOS:
        return True
    with _lock:
        return d in _por_anio.get(d.year, set())
