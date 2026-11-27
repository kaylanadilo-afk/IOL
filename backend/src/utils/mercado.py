"""Helpers del dominio broker: redondeos, fechas en hora argentina y horario de mercado."""
import os
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from src.utils.feriados import es_feriado
from src.utils.errors import BusinessError

COMISION = Decimal("0.005")  # 0,5 % del monto operado
RIESGO_MAXIMO = {"conservador": 2, "moderado": 4, "agresivo": 5}
TZ_AR = timezone(timedelta(hours=-3), "ART")  # Argentina no tiene horario de verano
APERTURA, CIERRE = time(11, 0), time(17, 0)
TICKER_MEP_ARS, TICKER_MEP_USD = "AL30", "AL30D"


def get_ahora() -> datetime:
    """Reloj del sistema (dependency de FastAPI). En los tests se reemplaza para simular horarios."""
    return datetime.now(timezone.utc)


def q2(v) -> Decimal:
    return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def q4(v) -> Decimal:
    return Decimal(v).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def a_utc(dt: datetime) -> datetime:
    """Fechas siempre en UTC en la base (timestamptz). Una fecha sin zona se toma como UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def fmt(v: Decimal, moneda: str) -> str:
    return f"{'US$' if moneda == 'USD' else '$'} {q2(v):,.2f}"


def mercado_siempre_abierto() -> bool:
    return os.getenv("MERCADO_SIEMPRE_ABIERTO", "0").lower() in ("1", "true", "si", "sí")


def estado_mercado(ahora: datetime) -> dict:
    local = ahora.astimezone(TZ_AR)
    feriado = es_feriado(local.date())
    en_horario = local.weekday() < 5 and not feriado and APERTURA <= local.time() < CIERRE
    return {
        "feriado": feriado,
        "abierto": en_horario or mercado_siempre_abierto(),
        "en_horario": en_horario,
        "modo_demo": mercado_siempre_abierto(),
        "hora_argentina": local.isoformat(timespec="seconds"),
        "horario": "lunes a viernes de 11:00 a 17:00 (hora de Argentina)",
    }


def validar_horario(ahora: datetime) -> None:
    if not estado_mercado(ahora)["abierto"]:
        local = ahora.astimezone(TZ_AR)
        dia = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")[local.weekday()]
        local = f"{dia} {local:%d/%m %H:%M}"
        raise BusinessError(
            f"Mercado cerrado: solo se opera de lunes a viernes de 11:00 a 17:00, salvo feriados (ahora: {local})."
        )
