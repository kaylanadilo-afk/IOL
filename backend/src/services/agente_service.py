"""Agente de inversiones: arma recomendaciones según el perfil de riesgo y el mercado del día con Groq.

Groq expone una API compatible con OpenAI (https://api.groq.com/openai/v1). Se configura en el .env:
    GROQ_API_KEY=gsk_...                  (https://console.groq.com/keys)
    GROQ_MODEL=openai/gpt-oss-120b        (opcional)

Dos usos:
- recomendacion(): un informe estructurado (JSON con esquema estricto) que la pantalla dibuja en tarjetas.
- chat(): conversación libre sobre ese contexto, con la respuesta en streaming (texto a medida que llega).

La IA solo propone: las compras que superan el riesgo del perfil o no tienen saldo se ajustan o se
descartan acá, antes de mostrarlas. Ninguna operación se ejecuta sola.
"""
import json
import math
import os
import re
import time
from collections.abc import Iterator
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from src.repositories.broker_repository import ActivoRepository
from src.services import precios_service
from src.services.cuenta_service import CuentaService
from src.services.inversor_service import InversorService
from src.utils import limites
from src.utils.feriados import es_feriado
from src.utils.errors import AppError
from src.utils.mercado import RIESGO_MAXIMO, TZ_AR, estado_mercado, get_ahora

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _url() -> str:
    """GROQ_URL en el .env permite apuntar a otro servidor compatible (por ejemplo uno simulado para probar)."""
    return os.getenv("GROQ_URL", "").strip() or GROQ_URL
MODELO_POR_DEFECTO = "openai/gpt-oss-120b"
DURACION_INFORME = 15 * 60  # el informe del día se reutiliza 15 minutos (salvo que se pida actualizar)
MAX_INFORMES = 500          # informes guardados en memoria (uno por cuenta)
_informes: dict[int, tuple[float, dict]] = {}  # cuenta_id -> (momento, informe)

DESCRIPCION_PERFIL = {
    "conservador": "prioriza cuidar el capital; solo puede comprar activos con riesgo hasta 2 (bonos y defensivos)",
    "moderado": "busca crecer con riesgo medido; puede comprar activos con riesgo hasta 4",
    "agresivo": "acepta más volatilidad para buscar rendimiento; puede comprar cualquier activo (riesgo hasta 5)",
}


class AgenteNoConfiguradoError(AppError):
    status_code = 503
    message = "El agente todavía no está configurado: falta la clave de Groq (GROQ_API_KEY) en el .env de la API."


def configurado() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def modelo() -> str:
    return os.getenv("GROQ_MODEL", "").strip() or MODELO_POR_DEFECTO


# ---------- Contexto: perfil, cartera y mercado del día ----------
def _num(v) -> float | None:
    return None if v is None else round(float(v), 2)


MOVIMIENTOS_POR_LADO = 8  # cuántos de los que más suben y más bajan hoy van al modelo
BASE_POR_TIPO = 6         # y cuántos de cada tipo con más peso (los de mayor precio negociado)


MENCIONADOS_MAX = 8       # activos que el inversor nombra en el chat y se suman aunque no estén en la selección
_NO_TICKERS = {"EL", "LA", "LOS", "LAS", "DE", "DEL", "UN", "UNA", "QUE", "Y", "O", "A", "EN", "ES", "MI", "ME", "SE",
               "LO", "AL", "POR", "CON", "SIN", "HOY", "YA", "NO", "SI", "MAS", "MÁS", "VS", "USD", "ARS", "MEP", "CCL"}


def mencionados(activos, textos: list[str]) -> list:
    """Activos que el inversor nombra por ticker (TSLA, ypfd) o por empresa (Tesla, Galicia)."""
    por_ticker = {a.ticker: a for a in activos}
    encontrados: dict[str, object] = {}
    for texto in textos:
        for palabra in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ0-9.]+", texto):
            p = palabra.strip(".").upper()
            if p in por_ticker and p not in _NO_TICKERS:
                encontrados.setdefault(p, por_ticker[p])
            elif len(p) >= 4:
                for a in activos:
                    if a.nombre != a.ticker and re.match(rf"{re.escape(p)}\b", a.nombre.upper()):
                        encontrados.setdefault(a.ticker, a)
    return list(encontrados.values())[:MENCIONADOS_MAX]


def _hora_ar(valor) -> str | None:
    """Fecha y hora de Argentina ('26/11/2026 17:56') desde un datetime o un texto ISO en UTC."""
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00")) if isinstance(valor, str) else valor
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_AR)
    return dt.astimezone(TZ_AR).strftime("%d/%m/%Y %H:%M")


# Nombres de dolarapi.com → nombres claros para el modelo ("bolsa" es el MEP, no el CCL)
DOLARES = {"oficial": "oficial", "mayorista": "mayorista", "blue": "blue", "bolsa": "mep", "contadoconliqui": "ccl",
           "cripto": "cripto", "tarjeta": "tarjeta"}


def _dolares() -> dict:
    """Cotizaciones de referencia con fuente y fecha. Si la fuente no responde, lo dice en vez de omitirlo."""
    try:
        lista = precios_service.dolares()
    except Exception as exc:  # dolarapi caída o lenta: el agente tiene que avisarlo, no inventar
        return {"fuente": "dolarapi.com", "no_disponible": f"la fuente no respondió ({type(exc).__name__})"}
    filas = [[DOLARES[d["casa"]], d.get("compra"), d.get("venta"), _hora_ar(d.get("fecha_actualizacion"))]
             for d in lista if d.get("casa") in DOLARES and d.get("venta")]
    faltan = [n for n in DOLARES.values() if n not in {f[0] for f in filas}]
    return {"fuente": "dolarapi.com (referencia del mercado, pesos por dólar)",
            "columnas": ["tipo", "compra", "venta", "fecha_de_este_tipo"], "filas": filas,
            **({"sin_dato": faltan} if faltan else {})}


def _momento_precios(ahora: datetime, en_rueda: bool) -> str:
    """Cuándo valen los precios, dicho como lo diría un operador: 'hoy 15:30' o 'cierre del 26/11'.
    Fuera de la rueda la cotización es la del último cierre (salteando fines de semana y feriados)."""
    local = ahora.astimezone(TZ_AR)
    if en_rueda:
        return f"hoy {local:%H:%M}"
    dia = local.date()
    if local.weekday() < 5 and local.hour < 11:
        dia -= timedelta(days=1)  # antes de la apertura vale el cierre del día hábil anterior
    while dia.weekday() >= 5 or es_feriado(dia):
        dia -= timedelta(days=1)
    return f"cierre del {dia:%d/%m}"


def _mep_zeno(cart: dict, activos_por_ticker: dict, momento: str) -> dict:
    al30, al30d = activos_por_ticker.get("AL30"), activos_por_ticker.get("AL30D")
    base = {"como_se_calcula": "precio de AL30 / precio de AL30D (explicalo solo si lo preguntan)",
            "fuente_si_preguntan": "precios de BYMA que publica data912.com, con hasta 30 s de demora"}
    if cart["tipo_cambio_mep"] is None or not al30 or not al30d:
        return {**base, "no_disponible": "faltan los precios de los bonos con los que se calcula"}
    return {**base, "valor": _num(cart["tipo_cambio_mep"]), "momento": momento}


def _comparar_mep(mep: dict, ref: dict) -> dict:
    """La comparación se calcula acá: el modelo a veces dice 'por encima' cuando es 'por debajo'."""
    venta_ref = next((f[2] for f in ref.get("filas", []) if f[0] == "mep"), None)
    if "valor" not in mep or not venta_ref:
        return mep
    dif = (mep["valor"] / float(venta_ref) - 1) * 100
    lado = "por debajo" if dif < 0 else "por encima" if dif > 0 else "igual"
    return {**mep, "comparado_con_mep_referencia_venta": f"{lado} ({dif:+.2f} %)"}


def _seleccion(activos, cart: dict, riesgo_max: int, extra: list | None = None) -> list:
    """El catálogo completo (500+ activos) no entra en el límite de tokens de Groq gratis.
    Al modelo van: lo que el inversor ya tiene, los bonos, los que nombra en el chat, los que más suben
    y bajan hoy entre los que puede comprar, y algunos de cada tipo para que siempre haya opciones."""
    tenidos = {t["ticker"] for t in cart["tenencias"]}
    elegidos = {a.ticker: a for a in activos if a.ticker in tenidos or a.tipo == "bono"}
    for a in extra or []:
        elegidos.setdefault(a.ticker, a)
    comprables = [a for a in activos if a.activo and a.nivel_riesgo <= riesgo_max and a.precio_actual]
    con_var = [a for a in comprables if getattr(a, "variacion_pct", None) is not None]
    por_var = sorted(con_var, key=lambda a: float(a.variacion_pct))
    for a in por_var[-MOVIMIENTOS_POR_LADO:] + por_var[:MOVIMIENTOS_POR_LADO]:
        elegidos.setdefault(a.ticker, a)
    for tipo in ("accion", "cedear"):
        # Los que tienen nombre de empresa conocido (no solo el ticker) primero
        del_tipo = sorted((a for a in comprables if a.tipo == tipo),
                          key=lambda a: (a.nombre == a.ticker, -float(a.precio_actual)))
        for a in del_tipo[:BASE_POR_TIPO]:
            elegidos.setdefault(a.ticker, a)
    return sorted(elegidos.values(), key=lambda a: (a.tipo, a.ticker))


def contexto(db: Session, token: str | None, textos: list[str] | None = None) -> dict:
    inv = InversorService(db).de_token(token)
    if not inv.cuenta:
        raise AppError("Tu usuario no tiene cuenta comitente.", 422)
    cart = CuentaService(db).cartera(inv.cuenta.id)
    riesgo_max = RIESGO_MAXIMO[inv.perfil_riesgo]
    activos = ActivoRepository(db).listar(None, None)
    por_ticker = {a.ticker: a for a in activos}
    elegidos = _seleccion(activos, cart, riesgo_max, mencionados(activos, textos or []))
    # Tablas con columnas en vez de un objeto por fila: mismo dato con muchos menos tokens
    # (Groq gratis limita los tokens por minuto, así que cada análisis tiene que ser liviano)
    filas = [[a.ticker, a.tipo, a.moneda, _num(a.precio_actual), _num(getattr(a, "variacion_pct", None)), a.nivel_riesgo,
              a.activo and a.nivel_riesgo <= riesgo_max] for a in elegidos]
    ahora = get_ahora()
    en_rueda = estado_mercado(ahora).get("en_horario")  # horario real de BYMA (11 a 17 h)
    hay_saldo = any(float(v or 0) > 0 for v in cart["saldos_disponibles"].values())
    situacion = ("con_inversiones" if cart["tenencias"] else "sin_inversiones" if hay_saldo else "cuenta_nueva_sin_saldo")
    return {
        "situacion_cuenta": situacion,
        "fecha_hora_argentina": _hora_ar(ahora),
        "rueda_abierta_ahora": en_rueda,
        "inversor": {"nombre": inv.nombre.split(" ")[0], "perfil_riesgo": inv.perfil_riesgo,
                     "descripcion_perfil": DESCRIPCION_PERFIL[inv.perfil_riesgo], "riesgo_maximo_compra": riesgo_max},
        "cartera": {
            "saldo_disponible": {m: _num(v) for m, v in cart["saldos_disponibles"].items()},
            "patrimonio_total_ars": _num(cart["patrimonio_total_ars"]),
            "composicion_pct": {c["tipo"]: _num(c["porcentaje"]) for c in cart["composicion_por_tipo"]},
            "tenencias": {"columnas": ["ticker", "moneda", "cantidad", "valor_actual", "rendimiento_pct", "riesgo"],
                          "filas": [[t["ticker"], t["moneda"], t["cantidad"], _num(t["valor_actual"]), _num(t["rendimiento_pct"]),
                                     t["nivel_riesgo"]] for t in cart["tenencias"]]},
        },
        "mercado_hoy": {
            "precios": {
                "momento": (momento := _momento_precios(ahora, en_rueda)),
                "fuente_si_preguntan": "BYMA, publicado por data912.com con hasta 30 s de demora",
                "aclaracion": ("rueda abierta: último precio operado" if en_rueda else
                               "rueda cerrada: son los precios con los que cerró la última rueda, no cotizan ahora"),
            },
            "seleccion": (f"{len(filas)} de {len(activos)} activos del catálogo: tenencias, bonos, los que nombraste, "
                          "los que más suben y bajan hoy y los principales de cada tipo"),
            "activos": {"columnas": ["ticker", "tipo", "moneda", "precio", "variacion_dia_pct", "riesgo", "se_puede_comprar"],
                        "filas": filas},
            "dolar_referencia": (ref := _dolares()),
            "dolar_mep": _comparar_mep(_mep_zeno(cart, por_ticker, momento), ref),
        },
        "comision_por_operacion_pct": 0.5,
        "_cartera": cart,  # uso interno (no se manda al modelo)
        "_activos": por_ticker,
    }


def _para_modelo(ctx: dict) -> str:
    return json.dumps({k: v for k, v in ctx.items() if not k.startswith("_")}, ensure_ascii=False, default=str,
                      separators=(",", ":"))


# ---------- Llamada a Groq ----------
ESPERA_MAXIMA = 20  # segundos que la API espera sola antes de avisar que hay que probar más tarde
INTENTOS = 3


def _segundos(valor: str | None) -> float | None:
    """'7', '7.5s', '585ms' o '1m2.5s' (formatos de Groq) a segundos."""
    if not valor:
        return None
    try:
        return float(valor)
    except ValueError:
        pass
    total, num = 0.0, ""
    unidades = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}
    i = 0
    while i < len(valor):
        c = valor[i]
        if c.isdigit() or c == ".":
            num += c
            i += 1
            continue
        u = "ms" if valor[i:i + 2] == "ms" else c
        total += float(num or 0) * unidades.get(u, 0)
        num, i = "", i + len(u)
    return total


def _espera(r: httpx.Response) -> float:
    h = r.headers
    return _segundos(h.get("retry-after")) or _segundos(h.get("x-ratelimit-reset-tokens")) or 5.0


def _cabeceras() -> dict:
    return {"Authorization": f"Bearer {os.environ['GROQ_API_KEY'].strip()}"}


def _groq(mensajes: list[dict], **extra) -> httpx.Response:
    if not configurado():
        raise AgenteNoConfiguradoError()
    for intento in range(1, INTENTOS + 1):
        try:
            r = httpx.post(_url(), timeout=httpx.Timeout(60, connect=10), headers=_cabeceras(),
                           json={"model": modelo(), "messages": mensajes, **extra})
        except httpx.HTTPError as e:
            raise AppError(f"No se pudo conectar con el servicio de IA ({type(e).__name__}).", 502) from e
        if intento < INTENTOS:
            # Límite por minuto: si hay que esperar poco, se espera y se reintenta sin molestar al usuario
            if r.status_code == 429 and _espera(r) <= ESPERA_MAXIMA:
                time.sleep(_espera(r) + 0.3)
                continue
            # El modelo a veces arma mal el JSON del informe: otra pasada suele salir bien
            if r.status_code == 400 and _json_invalido(r.text):
                continue
        _revisar(r.status_code, r.text, _espera(r) if r.status_code == 429 else None)
        return r
    raise AppError("El servicio de IA no respondió bien. Probá de nuevo.", 502)


def _json_invalido(cuerpo: str) -> bool:
    """Groq avisa así que el modelo armó un JSON que no cumple el esquema ('json_validate_failed')."""
    t = cuerpo.lower()
    return "json_validate_failed" in t or "failed_generation" in t or ("json" in t and ("schema" in t or "validate" in t))


def _revisar(status: int, cuerpo: str, espera: float | None = None) -> None:
    if status < 400:
        return
    if status == 400 and _json_invalido(cuerpo):
        raise AppError("La IA armó mal el informe varias veces seguidas. Tocá \"Intentar de nuevo\".", 502)
    try:
        detalle = json.loads(cuerpo).get("error", {}).get("message", "")
    except ValueError:
        detalle = cuerpo[:200]
    if status == 401:
        raise AppError("La clave de Groq no es válida. Revisá GROQ_API_KEY en el .env de la API.", 502)
    if status == 429:
        if "per day" in detalle.lower() or (espera or 0) > 120:
            raise AppError("Se alcanzó el límite diario gratuito de Groq. Vuelve a estar disponible mañana "
                           "(o con el plan pago de Groq).", 503)
        cuando = f"{int(espera) + 1} segundos" if espera else "un minuto"
        raise AppError(f"Zeno AI recibió muchas consultas seguidas (límite del plan gratuito de Groq). "
                       f"Probá de nuevo en {cuando}.", 503)
    if status == 404 or "model" in detalle.lower() and "not" in detalle.lower():
        raise AppError(f"El modelo '{modelo()}' no está disponible en Groq. Cambiá GROQ_MODEL en el .env.", 502)
    raise AppError(f"El servicio de IA respondió con un error: {detalle or status}", 502)


SISTEMA = """Sos "Zeno AI", el analista de inversiones de Zeno Investments, un broker del mercado argentino \
(acciones de BYMA, CEDEARs, bonos y dólar MEP). Hablás en español rioplatense, claro y profesional, \
sin jerga innecesaria y sin exagerar.

Datos:
- Basate SOLO en los datos del contexto (perfil, cartera y mercado del día). No inventes precios, cotizaciones, \
noticias ni datos que no estén ahí, ni los completes de memoria.
- Dá los datos en forma directa, como un analista: el valor y cuándo vale, nada más. Ejemplos: "El dólar MEP \
está a **$1.662,96** (cierre del 26/11)." / "**TSLA** cerró en **$44.820** (-0,48 %) el 26/11." \
No nombres proveedores de datos (data912, dolarapi, "BYMA vía…"), no expliques cómo se calcula un dato y no digas \
"uso interno", "según el contexto" ni "según la información que tengo". Solo si el inversor pregunta de dónde sale \
un dato, contale la fuente. Usá "fecha_hora_argentina" para saber qué día es hoy.
- Dólar MEP: es "dolar_mep" (el valor al que se compran y venden dólares en Zeno). Dalo como "el dólar MEP", \
un solo valor. El MEP de "dolar_referencia" usalo solo si piden comparar o la diferencia con otros mercados.
- Otros dólares: "dolar_referencia" trae oficial, mayorista, blue, mep, ccl, cripto y tarjeta, cada uno con su \
propia fecha y hora. Cada tipo es distinto (MEP no es CCL ni mayorista): si piden uno que no figura, decí que no \
lo tenés en vez de dar otro.
- Las tenencias del inversor son SOLO las de "cartera.tenencias". Los demás activos de la tabla de mercado no \
los tiene.
- Si un dato dice "no_disponible" o "sin_dato", o un activo no está en la tabla, decí claramente que no lo pudiste \
obtener y por qué si se sabe; no lo estimes. Si un activo no está en la tabla puede que igual se opere en Zeno: \
sugerí buscarlo en Mercado.
- Con la rueda cerrada, los precios son los del cierre de la última rueda: aclaralo.
- No muestres los nombres internos del contexto (como "dolar_referencia" o "no_disponible"): decilo con palabras.

Educación y recomendaciones:
- Distinguí siempre la información educativa (qué es algo, cómo funciona, qué mirar) de una recomendación \
personalizada para este inversor (qué haría con su perfil y su cartera). Si es una recomendación, decilo y basala \
en su perfil, su saldo y sus tenencias.
- Nunca presentes resultados como seguros ni prometas rendimientos: no proyectes cuánto va a ganar o rendir \
un activo. Podés explicar riesgos, escenarios y qué factores mirar.

Reglas para recomendar:
- Nunca recomiendes COMPRAR un activo con "se_puede_comprar" en false (supera el riesgo del perfil o está \nsuspendido). Vender siempre se puede.
- Las compras no pueden superar el saldo disponible en esa moneda. Tené en cuenta la comisión del 0,5 %.
- Priorizá la diversificación por tipo de activo y la coherencia con el perfil.
- "mantener" y "vender" SOLO para tickers que estén en sus tenencias. Si no tiene tenencias, no los uses.
- Según "situacion_cuenta":
  - "con_inversiones": revisá lo que tiene (mantener, vender o reforzar) y sumá compras si tiene saldo.
  - "sin_inversiones": tiene saldo pero nada invertido; proponé una primera cartera solo con compras.
  - "cuenta_nueva_sin_saldo": todavía no depositó. Proponé un plan inicial SOLO con compras, con \
"porcentaje" del primer depósito (que sumen 100) y "monto" 0. El primer próximo paso es depositar.
- "porcentaje" es qué parte del saldo disponible (o del primer depósito) va a esa compra; 0 si no es compra.
- Las recomendaciones son orientativas, no asesoramiento financiero profesional: la decisión final es del inversor."""

ESQUEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["titular", "resumen_mercado", "lectura_cartera", "postura", "puntaje_riesgo", "recomendaciones",
                 "riesgos", "proximos_pasos"],
    "properties": {
        "titular": {"type": "string", "description": "Una frase corta que resume la recomendación del día"},
        "resumen_mercado": {"type": "string", "description": "Qué está pasando hoy en el mercado (2 a 3 oraciones)"},
        "lectura_cartera": {"type": "string", "description": "Diagnóstico de la cartera actual (2 a 3 oraciones)"},
        "postura": {"type": "string", "enum": ["defensiva", "neutral", "ofensiva"]},
        "puntaje_riesgo": {"type": "integer", "description": "Qué tan arriesgado está hoy el mercado para este perfil, de 1 a 10"},
        "recomendaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["accion", "ticker", "monto", "porcentaje", "moneda", "confianza", "motivo"],
                "properties": {
                    "accion": {"type": "string", "enum": ["comprar", "vender", "mantener"]},
                    "ticker": {"type": "string"},
                    "monto": {"type": "number", "description": "Monto sugerido en la moneda del activo (0 si es mantener)"},
                    "porcentaje": {"type": "number", "description": "Parte del saldo (o del primer depósito) para esta compra, de 0 a 100"},
                    "moneda": {"type": "string", "enum": ["ARS", "USD"]},
                    "confianza": {"type": "string", "enum": ["alta", "media", "baja"]},
                    "motivo": {"type": "string", "description": "Por qué, en una o dos oraciones"},
                },
            },
        },
        "riesgos": {"type": "array", "items": {"type": "string"}},
        "proximos_pasos": {"type": "array", "items": {"type": "string"}},
    },
}


def recomendacion(db: Session, token: str | None, actualizar: bool = False) -> dict:
    ctx = contexto(db, token)
    # Con el contexto armado ya no hace falta la base: se libera la conexión antes de esperar a la IA
    db.close()
    cuenta_id = ctx["_cartera"]["cuenta_id"]
    guardado = _informes.get(cuenta_id)
    vigente = guardado and time.monotonic() - guardado[0] < DURACION_INFORME
    if vigente and not actualizar:
        return guardado[1]
    if actualizar and guardado:
        # Pedir un informe nuevo gasta la cuota compartida de Groq: uno cada 2 minutos por cuenta
        if limites.INFORME_IA.espera(str(cuenta_id)) > 0:
            return guardado[1]
        limites.INFORME_IA.registrar(str(cuenta_id))
    pedido = ("Analizá mi situación y el mercado de hoy y armá el informe del día: entre 3 y 5 recomendaciones "
              "concretas con montos realistas, respetando mi situacion_cuenta, 2 a 4 riesgos a vigilar y 2 o 3 próximos "
              f"pasos. Contexto:\n{_para_modelo(ctx)}")
    r = _groq([{"role": "system", "content": SISTEMA}, {"role": "user", "content": pedido}],
              temperature=0.4, reasoning_effort="low", max_completion_tokens=3000,
              response_format={"type": "json_schema",
                                                 "json_schema": {"name": "informe", "strict": True, "schema": ESQUEMA}})
    try:
        datos = json.loads(r.json()["choices"][0]["message"]["content"])
    except (KeyError, IndexError, ValueError) as e:
        raise AppError("La IA devolvió una respuesta que no se pudo leer. Probá de nuevo.", 502) from e
    informe = _ajustar(datos, ctx)
    if len(_informes) >= MAX_INFORMES:  # se descarta el más viejo para que la memoria no crezca sin fin
        _informes.pop(min(_informes, key=lambda k: _informes[k][0]), None)
    _informes[cuenta_id] = (time.monotonic(), informe)
    return informe


def _ajustar(datos: dict, ctx: dict) -> dict:
    """Aplica las reglas del broker a lo que propuso la IA y suma los datos de cada activo para la pantalla."""
    riesgo_max = ctx["inversor"]["riesgo_maximo_compra"]
    saldo = {m: float(v or 0) for m, v in ctx["_cartera"]["saldos_disponibles"].items()}
    tenidos = {t["ticker"] for t in ctx["_cartera"]["tenencias"]}
    sin_saldo = all(v <= 0 for v in saldo.values())
    recs, descartadas = [], []
    for rec in datos.get("recomendaciones", []):
        a = ctx["_activos"].get(str(rec.get("ticker", "")).upper().strip())
        if not a:
            descartadas.append(f"{rec.get('ticker')}: no se opera en Zeno")
            continue
        rec["ticker"], rec["moneda"] = a.ticker, a.moneda
        if rec["accion"] == "comprar":
            if a.nivel_riesgo > riesgo_max:
                descartadas.append(f"{a.ticker}: su riesgo ({a.nivel_riesgo}) supera tu perfil")
                continue
            if not a.activo:
                descartadas.append(f"{a.ticker}: está suspendido")
                continue
            rec["porcentaje"] = round(min(max(float(rec.get("porcentaje") or 0), 0), 100), 1)
            if sin_saldo:
                # Cuenta sin saldo: la compra queda como idea para el primer depósito (sin monto)
                rec["monto"], rec["idea"] = 0, True
            else:
                tope = saldo.get(a.moneda, 0) / 1.005
                if tope <= 0:
                    descartadas.append(f"{a.ticker}: no tenés saldo en {a.moneda}")
                    continue
                # Redondeo hacia abajo: nunca más que el saldo, comisión incluida
                rec["monto"] = math.floor(min(max(float(rec.get("monto") or 0), 0), tope) * 100) / 100
                saldo[a.moneda] -= rec["monto"] * 1.005
        elif a.ticker not in tenidos:
            # Mantener o vender algo que no se tiene no tiene sentido
            descartadas.append(f"{a.ticker}: no lo tenés en cartera ({rec['accion']})")
            continue
        else:
            rec["porcentaje"] = 0
        precio = float(a.precio_actual)
        rec["activo"] = {"id": a.id, "nombre": a.nombre, "tipo": a.tipo, "precio": precio, "riesgo": a.nivel_riesgo,
                         "variacion_pct": _num(getattr(a, "variacion_pct", None))}
        rec["cantidad_estimada"] = int(rec["monto"] // precio) if rec["accion"] != "mantener" and precio > 0 else 0
        rec.setdefault("idea", False)
        recs.append(rec)
    return {
        **datos,
        "puntaje_riesgo": max(1, min(10, int(datos.get("puntaje_riesgo") or 5))),
        "recomendaciones": recs,
        "descartadas": descartadas,
        "situacion": ctx["situacion_cuenta"],
        "perfil": ctx["inversor"]["perfil_riesgo"],
        "generado": datetime.now(TZ_AR).isoformat(timespec="seconds"),
        "modelo": modelo(),
        "fuentes": _fuentes(ctx),
    }


def _fuentes(ctx: dict) -> list[str]:
    """Qué datos usó el análisis, de dónde salen y de cuándo son (se muestran debajo del informe)."""
    m = ctx["mercado_hoy"]
    precios = f"Precios de BYMA, {m['precios']['momento']}"
    ref = m["dolar_referencia"]
    fechas = {f[0]: f[3] for f in ref.get("filas", [])}
    dolar = ("Otros tipos de dólar: no disponibles en este momento" if "no_disponible" in ref else
             f"Otros tipos de dólar: dolarapi.com, {fechas.get('mep') or fechas.get('oficial') or 'sin fecha'}")
    mep = m["dolar_mep"]
    mep_txt = ("Dólar MEP: no disponible en este momento" if "no_disponible" in mep else
               f"Dólar MEP: calculado con los bonos AL30 y AL30D, {mep['momento']}")
    return [precios, mep_txt, dolar]


# ---------- Chat con streaming ----------
def _sin_relleno(texto: str | None, espacios: list[int]) -> str:
    """El modelo a veces escribe cientos de espacios seguidos: se dejan pasar como mucho 4 (sangría de listas)."""
    salida = []
    for c in texto or "":
        if c in "   ​\t":
            espacios[0] += 1
            if espacios[0] > 4:
                continue
        else:
            espacios[0] = 0
        salida.append(c)
    return "".join(salida)


def chat(db: Session, token: str | None, mensajes: list[dict]) -> Iterator[str]:
    """Genera la respuesta de a pedazos (Server-Sent Events) para que la pantalla la escriba en vivo."""
    if not configurado():
        raise AgenteNoConfiguradoError()
    historial = [{"role": m["role"], "content": str(m["content"])[:4000]} for m in mensajes[-8:]
                 if m.get("role") in ("user", "assistant") and m.get("content")]
    # Los activos que el inversor nombra en las últimas preguntas se suman a la tabla del contexto
    ctx = contexto(db, token, [m["content"] for m in historial if m["role"] == "user"][-3:])
    db.close()  # el contexto ya está armado: la conexión vuelve al pool mientras dura la respuesta de la IA
    sistema = (SISTEMA + "\n\nRespondé en pocos párrafos cortos (máximo 180 palabras), con viñetas si ayuda. "
               "Usá **negrita** para tickers y cifras clave. Contexto actual del inversor y del mercado:\n" + _para_modelo(ctx))

    def eventos() -> Iterator[str]:
        espacios = [0]  # espacios seguidos que ya se mandaron (el corte puede caer entre dos pedazos)
        try:
            with httpx.stream("POST", _url(), timeout=httpx.Timeout(60, connect=10), headers=_cabeceras(),
                              json={"model": modelo(), "stream": True, "temperature": 0.2, "reasoning_effort": "low",
                                    "max_completion_tokens": 1200,
                                    "messages": [{"role": "system", "content": sistema}, *historial]}) as r:
                if r.status_code >= 400:
                    _revisar(r.status_code, r.read().decode(errors="ignore"), _espera(r) if r.status_code == 429 else None)
                for linea in r.iter_lines():
                    if not linea.startswith("data: "):
                        continue
                    dato = linea[6:].strip()
                    if dato == "[DONE]":
                        break
                    try:
                        delta = json.loads(dato)["choices"][0]["delta"].get("content")
                    except (KeyError, IndexError, ValueError):
                        continue
                    delta = _sin_relleno(delta, espacios)
                    if delta:
                        yield f"data: {json.dumps({'texto': delta}, ensure_ascii=False)}\n\n"
        except AppError as e:
            yield f"data: {json.dumps({'error': e.message}, ensure_ascii=False)}\n\n"
        except httpx.HTTPError as e:
            yield f"data: {json.dumps({'error': f'Se cortó la conexión con el servicio de IA ({type(e).__name__}).'})}\n\n"
        yield "data: [FIN]\n\n"

    return eventos()


def estado() -> dict:
    return {"configurado": configurado(), "modelo": modelo()}

