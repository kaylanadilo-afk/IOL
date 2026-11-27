"""Precios reales de mercado.

Fuentes gratuitas, sin cuenta ni API key:
  - data912.com: cotizaciones de BYMA (acciones, CEDEARs y bonos), con unos 30 s de caché.
  - dolarapi.com: dólar oficial, blue, MEP (bolsa), CCL, etc. Es solo informativo: el MEP con
    el que opera la app sigue siendo AL30 / AL30D, como pide la HU7.

Activar la actualización automática con la variable de entorno PRECIOS_REALES=1.
Cada PRECIOS_INTERVALO segundos (60 por defecto) se pisa el precio_actual de los activos cuyo
ticker aparece en la fuente. Las operaciones pasadas no cambian: guardan su precio_unitario (HU8).
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy.orm import Session

from src.repositories.broker_repository import ActivoRepository
from src.services import catalogo_service as catalogo
from src.services.alertas_service import AlertasService
from src.services import historial_service as historial
from src.utils.mercado import q4

log = logging.getLogger("iol.precios")

DATA912 = "https://data912.com/live/{panel}"
PANELES = ("arg_stocks", "arg_cedears", "arg_bonds")
DOLARAPI = "https://dolarapi.com/v1/dolares"
# Los bonos cotizan cada 100 nominales; en la app el precio es por 1 nominal
ESCALA = {"arg_bonds": Decimal("0.01")}
TIMEOUT = 10.0

estado = {"ultima_sincronizacion": None, "actualizados": 0, "sin_dato": [], "alertas_disparadas": 0, "error": None}
_cache_dolares = {"t": 0.0, "datos": None}


def activado() -> bool:
    return os.getenv("PRECIOS_REALES", "0").lower() in ("1", "true", "si", "sí")


def intervalo() -> int:
    try:
        return max(15, int(os.getenv("PRECIOS_INTERVALO", "60")))
    except ValueError:
        return 60


def _dec(v) -> Decimal | None:
    try:
        d = Decimal(str(v))
    except (InvalidOperation, TypeError):
        return None
    return d if d.is_finite() else None


def obtener_cotizaciones() -> dict[str, dict]:
    """{ticker: {"precio": Decimal, "variacion_pct": Decimal | None}} de los tres paneles."""
    cotizaciones: dict[str, dict] = {}
    with httpx.Client(timeout=TIMEOUT) as client:
        for panel in PANELES:
            r = client.get(DATA912.format(panel=panel))
            r.raise_for_status()
            for fila in r.json():
                ticker = str(fila.get("symbol", "")).upper()
                # "c" es el último precio operado; si todavía no operó, se usa el punto medio de la punta
                precio = _dec(fila.get("c"))
                if not precio or precio <= 0:
                    bid, ask = _dec(fila.get("px_bid")), _dec(fila.get("px_ask"))
                    precio = (bid + ask) / 2 if bid and ask and bid > 0 and ask > 0 else None
                if not ticker or not precio:
                    continue
                cotizaciones[ticker] = {
                    "precio": q4(precio * ESCALA.get(panel, Decimal("1"))),
                    "variacion_pct": _dec(fila.get("pct_change")),
                }
    return cotizaciones


def aplicar_cotizaciones(db: Session, cotizaciones: dict[str, dict], ahora: datetime | None = None) -> dict:
    """Actualiza los activos del catálogo con las cotizaciones recibidas (no hace commit)."""
    ahora = ahora or datetime.now(timezone.utc)
    rueda = historial.en_rueda(ahora)  # fuera de la rueda el precio no cambia: no se guarda historial
    actualizados, sin_dato = 0, []
    for activo in ActivoRepository(db).list_por_ticker():
        dato = cotizaciones.get(activo.ticker)
        if not dato or dato["precio"] <= 0:
            sin_dato.append(activo.ticker)
            continue
        activo.precio_actual = dato["precio"]
        activo.variacion_pct = dato["variacion_pct"]
        activo.precio_actualizado = ahora
        if rueda:
            historial.registrar_precio(db, activo, dato["precio"], ahora)
        actualizados += 1
    db.flush()
    return {"actualizados": actualizados, "sin_dato": sin_dato}


def sincronizar(db: Session) -> dict:
    """Trae las cotizaciones y las guarda. Deja registro del resultado en `estado`."""
    try:
        cotizaciones = obtener_cotizaciones()
        # Suma al catálogo las acciones y CEDEARs reales que falten (con el precio que trae la fuente)
        nuevos = catalogo.ampliar(db, cotizaciones)
        if nuevos:
            log.info("Activos agregados al catálogo: %s", ", ".join(nuevos))
        res = aplicar_cotizaciones(db, cotizaciones)
        db.commit()
        # Con los precios nuevos se revisan las alertas de los usuarios (aunque nadie tenga la página abierta)
        res["alertas_disparadas"] = AlertasService(db).evaluar()
        estado.update(ultima_sincronizacion=datetime.now(timezone.utc), error=None, **res)
    except Exception as exc:  # la API sigue funcionando con los últimos precios
        db.rollback()
        estado["error"] = f"{type(exc).__name__}: {exc}"
        log.warning("No se pudieron actualizar los precios: %s", estado["error"])
    return resumen()


def resumen() -> dict:
    return {
        "modo": "reales" if activado() else "manuales",
        "fuente": "data912.com (BYMA)" if activado() else "carga manual (PATCH /api/activos/{id}/precio)",
        "intervalo_segundos": intervalo() if activado() else None,
        **estado,
    }


def dolares() -> list[dict]:
    """Cotizaciones del dólar de dolarapi.com, con 60 s de caché para no pegarle en cada request."""
    if _cache_dolares["datos"] is not None and time.monotonic() - _cache_dolares["t"] < 60:
        return _cache_dolares["datos"]
    r = httpx.get(DOLARAPI, timeout=TIMEOUT)
    r.raise_for_status()
    datos = [
        {"casa": d.get("casa"), "nombre": d.get("nombre"), "compra": d.get("compra"),
         "venta": d.get("venta"), "fecha_actualizacion": d.get("fechaActualizacion")}
        for d in r.json()
    ]
    _cache_dolares.update(t=time.monotonic(), datos=datos)
    return datos


# ---------- Tarea de fondo ----------
def _sincronizar_con_sesion() -> dict:
    from src.db.connection import SessionLocal

    with SessionLocal() as db:
        return sincronizar(db)


def _historial_con_sesion() -> dict:
    from src.db.connection import SessionLocal

    with SessionLocal() as db:
        return historial.cargar_y_registrar(db)


async def bucle_precios() -> None:
    """Precios reales cada PRECIOS_INTERVALO segundos e historial una vez por día."""
    dia_historial = None
    while True:
        await asyncio.to_thread(_sincronizar_con_sesion)
        hoy = historial.fecha_ar(datetime.now(timezone.utc))
        if dia_historial != hoy:
            await asyncio.to_thread(_historial_con_sesion)
            if not historial.estado_historial["error"]:
                dia_historial = hoy
        await asyncio.sleep(intervalo())
