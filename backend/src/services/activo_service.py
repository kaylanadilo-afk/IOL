from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.db.models.activo_model import Activo, Dividendo
from src.db.models.cuenta_model import Movimiento
from src.dtos.broker_dto import ActivoDTO, DividendoDTO
from src.mappers.broker_mapper import to_activo, to_activos, to_json
from src.repositories.broker_repository import ActivoRepository, CuentaRepository, OperacionRepository
from src.utils.errors import BusinessError, ConflictError, no_encontrado
from src.utils.mercado import TICKER_MEP_ARS, TICKER_MEP_USD, TZ_AR, a_utc, q2, q4


def obtener_activo(db: Session, activo_id: int | None = None, ticker: str | None = None) -> Activo:
    repo = ActivoRepository(db)
    ticker = (ticker or "").strip().upper() or None
    activo = repo.find_by_id(activo_id) if activo_id is not None else repo.find_by_ticker(ticker or "")
    if not activo:
        raise no_encontrado("Activo")
    if activo_id is not None and ticker and activo.ticker != ticker:
        raise BusinessError(f"El activo {activo_id} es {activo.ticker}, no {ticker}: revisá el pedido.")
    return activo


def tipo_cambio_mep(db: Session) -> Decimal | None:
    """MEP de la app: precio AL30 / precio AL30D."""
    repo = ActivoRepository(db)
    ars, usd = repo.find_by_ticker(TICKER_MEP_ARS), repo.find_by_ticker(TICKER_MEP_USD)
    if not ars or not usd:
        return None
    return q2(ars.precio_actual / usd.precio_actual)


class ActivoService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ActivoRepository(db)

    # ---------- HU2: catálogo ----------
    def crear(self, ticker: str, nombre: str, tipo: str, moneda: str, precio_actual: Decimal,
              nivel_riesgo: int, activo: bool = True) -> ActivoDTO:
        if self.repo.find_by_ticker(ticker):
            raise ConflictError(f"Ya existe el ticker {ticker}")
        a = Activo(ticker=ticker, nombre=nombre, tipo=tipo, moneda=moneda, precio_actual=precio_actual,
                   nivel_riesgo=nivel_riesgo, activo=activo)
        self.repo.add(a)
        self.db.commit()
        return to_activo(a)

    def listar(self, tipo: str | None, moneda: str | None) -> list[ActivoDTO]:
        return to_activos(self.repo.listar(tipo, moneda))

    def obtener(self, activo_id: int) -> ActivoDTO:
        return to_activo(obtener_activo(self.db, activo_id))

    # ---------- HU8: precio y suspensión ----------
    def actualizar_precio(self, activo_id: int, precio: Decimal, ahora: datetime | None = None) -> ActivoDTO:
        from src.services import historial_service  # evita import circular

        activo = obtener_activo(self.db, activo_id)
        activo.precio_actual = precio  # las operaciones guardan su propio precio_unitario
        activo.variacion_pct = None
        activo.precio_actualizado = a_utc(ahora) if ahora is not None else datetime.now(timezone.utc)
        # El cambio manual queda en el gráfico solo si es durante la rueda (un sábado no hay cotización)
        if ahora is not None and historial_service.en_rueda(ahora):
            historial_service.registrar_precio(self.db, activo, precio, ahora)
        self.db.commit()
        # Un cambio manual de precio también revisa las alertas de ese activo
        from src.services.alertas_service import AlertasService
        AlertasService(self.db).evaluar([activo.id])
        return to_activo(activo)

    def actualizar_estado(self, activo_id: int, operable: bool) -> ActivoDTO:
        activo = obtener_activo(self.db, activo_id)
        activo.activo = operable
        self.db.commit()
        return to_activo(activo)

    # ---------- HU9: dividendos ----------
    def registrar_dividendo(self, activo_id: int, monto_por_unidad: Decimal, fecha_pago: date | None) -> DividendoDTO:
        activo = obtener_activo(self.db, activo_id)
        if activo.tipo not in ("accion", "cedear"):
            raise BusinessError("Solo las acciones y los CEDEARs pagan dividendos.")
        hoy = datetime.now(TZ_AR).date()
        fecha_pago = fecha_pago or hoy
        # Se acredita en el momento: una fecha futura no tendría sentido
        if fecha_pago > hoy:
            raise BusinessError("La fecha de pago no puede ser futura: el dividendo se acredita en el momento.",
                                campo="fecha_pago")
        # Doble clic o pedido repetido: el mismo dividendo (activo, día y monto) no se paga dos veces
        if self.repo.dividendo_igual(activo.id, fecha_pago, monto_por_unidad):
            raise ConflictError(f"Ese dividendo de {activo.ticker} ya se pagó el {fecha_pago:%d/%m/%Y}.")
        div = Dividendo(activo_id=activo.id, monto_por_unidad=monto_por_unidad, fecha_pago=fecha_pago)
        self.repo.add_dividendo(div)

        cuentas = CuentaRepository(self.db)
        total, acreditadas = Decimal("0"), 0
        for t in cuentas.tenencias_de_activo(activo.id):
            monto = q2(t.cantidad * monto_por_unidad)
            if monto <= 0:
                continue
            cuenta = cuentas.find_by_id(t.cuenta_id, bloquear=True)
            cuenta.ajustar_saldo(activo.moneda, monto)
            cuentas.add(Movimiento(cuenta_id=cuenta.id, tipo="dividendo", moneda=activo.moneda, monto=monto,
                                   descripcion=f"Dividendo {activo.ticker}: {t.cantidad} x {q4(monto_por_unidad)}"))
            total += monto
            acreditadas += 1
        self.db.flush()
        self.db.commit()
        return DividendoDTO(id=div.id, activo_id=activo.id, ticker=activo.ticker, moneda=activo.moneda,
                            monto_por_unidad=div.monto_por_unidad, fecha_pago=div.fecha_pago,
                            cuentas_acreditadas=acreditadas, total_pagado=total)

    # ---------- HU12: rankings ----------
    def mas_operados(self, ahora: datetime, limite: int = 10) -> list[dict]:
        filas = OperacionRepository(self.db).volumen_por_activo(a_utc(ahora) - timedelta(days=7))
        tc = tipo_cambio_mep(self.db)
        ranking = []
        for activo, n_ops, unidades, monto in filas:
            monto = Decimal(monto or 0)
            ranking.append({
                "activo_id": activo.id, "ticker": activo.ticker, "nombre": activo.nombre, "tipo": activo.tipo,
                "moneda": activo.moneda, "operaciones": n_ops, "cantidad_operada": int(unidades or 0),
                "volumen": q2(monto),
                # Volumen comparable entre monedas: los USD se pasan a pesos al tipo de cambio MEP
                # Sin tipo de cambio no se puede pasar a pesos: queda sin dato en vez de sumar dólares como pesos
                "volumen_ars": q2(monto * tc) if activo.moneda == "USD" and tc else (q2(monto) if activo.moneda == "ARS" else None),
            })
        ranking.sort(key=lambda r: (-r["volumen_ars"], r["ticker"]))
        return to_json(ranking[:limite])

    def mas_favoritos(self, limite: int = 10) -> list[dict]:
        return [{"activo_id": a.id, "ticker": a.ticker, "nombre": a.nombre, "tipo": a.tipo,
                 "moneda": a.moneda, "favoritos": n} for a, n in self.repo.mas_favoritos(limite)]
