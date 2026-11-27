"""Queries del broker. Sin lógica de negocio y sin commit: la transacción la maneja el service
(así las dos patas del MEP se guardan juntas o ninguna)."""
from datetime import date, datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from src.db.models.activo_model import Activo, CierreDiario, CotizacionIntradia, Dividendo
from src.db.models.cuenta_model import Cuenta, Movimiento, Tenencia
from src.db.models.inversor_model import Inversor, favoritos
from src.db.models.operacion_model import Operacion


class InversorRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, inversor_id: int) -> Inversor | None:
        return self.db.get(Inversor, inversor_id)

    def find_by_email(self, email: str) -> Inversor | None:
        return self.db.scalars(select(Inversor).where(Inversor.email == email)).first()

    def find_by_cuit(self, cuit: str) -> Inversor | None:
        return self.db.scalars(select(Inversor).where(Inversor.cuit == cuit)).first()

    def add(self, inv: Inversor) -> Inversor:
        self.db.add(inv)
        self.db.flush()
        return inv


class CuentaRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, cuenta_id: int, bloquear: bool = False) -> Cuenta | None:
        stmt = select(Cuenta).where(Cuenta.id == cuenta_id)
        if bloquear:  # SELECT ... FOR UPDATE: evita que dos operaciones simultáneas pisen el saldo
            stmt = stmt.with_for_update()
        return self.db.scalars(stmt).first()

    def max_numero_comitente(self) -> int | None:
        return self.db.scalar(select(func.max(Cuenta.numero_comitente)))

    def add(self, obj) -> None:
        self.db.add(obj)

    def flush(self) -> None:
        self.db.flush()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def delete(self, obj) -> None:
        self.db.delete(obj)

    def tenencia(self, cuenta_id: int, activo_id: int) -> Tenencia | None:
        return self.db.get(Tenencia, (cuenta_id, activo_id))

    def tenencias_de_activo(self, activo_id: int) -> list[Tenencia]:
        return list(self.db.scalars(select(Tenencia).where(Tenencia.activo_id == activo_id)
                                    .order_by(Tenencia.cuenta_id)))

    def movimientos(self, cuenta_id: int) -> list[Movimiento]:
        return list(self.db.scalars(select(Movimiento).where(Movimiento.cuenta_id == cuenta_id)
                                    .order_by(Movimiento.fecha.desc(), Movimiento.id.desc())))


class ActivoRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, activo_id: int) -> Activo | None:
        return self.db.get(Activo, activo_id)

    def find_by_ticker(self, ticker: str) -> Activo | None:
        return self.db.scalars(select(Activo).where(Activo.ticker == ticker)).first()

    def find_by_tickers(self, tickers) -> list[Activo]:
        return list(self.db.scalars(select(Activo).where(Activo.ticker.in_(tuple(tickers)))))

    def listar(self, tipo: str | None = None, moneda: str | None = None) -> list[Activo]:
        stmt = select(Activo).order_by(Activo.tipo, Activo.ticker)
        if tipo:
            stmt = stmt.where(Activo.tipo == tipo)
        if moneda:
            stmt = stmt.where(Activo.moneda == moneda)
        return list(self.db.scalars(stmt))

    def list_por_ticker(self) -> list[Activo]:
        return list(self.db.scalars(select(Activo).order_by(Activo.ticker)))

    def add(self, obj) -> None:
        self.db.add(obj)
        self.db.flush()

    def dividendo_igual(self, activo_id: int, fecha_pago: date, monto_por_unidad) -> bool:
        return self.db.scalar(select(func.count()).select_from(Dividendo).where(
            Dividendo.activo_id == activo_id, Dividendo.fecha_pago == fecha_pago,
            Dividendo.monto_por_unidad == monto_por_unidad)) > 0

    def add_dividendo(self, div: Dividendo) -> None:
        self.db.add(div)

    def mas_favoritos(self, limite: int) -> list[tuple[Activo, int]]:
        cantidad = func.count(favoritos.c.inversor_id).label("cantidad")
        return [tuple(f) for f in self.db.execute(
            select(Activo, cantidad).join(favoritos, favoritos.c.activo_id == Activo.id)
            .group_by(Activo.id).order_by(cantidad.desc(), Activo.ticker).limit(limite)).all()]


class OperacionRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, op: Operacion) -> None:
        self.db.add(op)
        self.db.flush()

    def historial(self, cuenta_id: int, desde: datetime | None, hasta: datetime | None,
                  tipo: str | None, ticker: str | None) -> list[Operacion]:
        stmt = (select(Operacion).join(Operacion.activo).where(Operacion.cuenta_id == cuenta_id)
                .order_by(Operacion.fecha.desc(), Operacion.id.desc()))
        if desde:
            stmt = stmt.where(Operacion.fecha >= desde)
        if hasta:
            stmt = stmt.where(Operacion.fecha < hasta)
        if tipo:
            stmt = stmt.where(Operacion.tipo == tipo)
        if ticker:
            stmt = stmt.where(Activo.ticker == ticker)
        return list(self.db.scalars(stmt))

    def volumen_por_activo(self, desde: datetime) -> list[tuple]:
        """(activo, cantidad de operaciones, unidades, monto) desde una fecha."""
        return [tuple(f) for f in self.db.execute(
            select(Activo, func.count(Operacion.id), func.sum(Operacion.cantidad),
                   func.sum(Operacion.cantidad * Operacion.precio_unitario))
            .join(Operacion, Operacion.activo_id == Activo.id)
            .where(Operacion.fecha >= desde, Operacion.estado == "ejecutada")
            .group_by(Activo.id)).all()]

    def ventas_con_ganancia(self, cuenta_id: int) -> list[Operacion]:
        return list(self.db.scalars(select(Operacion).where(
            Operacion.cuenta_id == cuenta_id, Operacion.tipo == "venta", Operacion.estado == "ejecutada",
            Operacion.ganancia_realizada.is_not(None))))


class HistorialRepository:
    def __init__(self, db: Session):
        self.db = db

    def intradia(self, activo_id: int, momento: datetime) -> CotizacionIntradia | None:
        return self.db.get(CotizacionIntradia, (activo_id, momento))

    def cierre(self, activo_id: int, d: date) -> CierreDiario | None:
        return self.db.get(CierreDiario, (activo_id, d))

    def add(self, obj) -> None:
        self.db.add(obj)

    def precios_intradia(self, activo_id: int, desde: datetime, hasta: datetime) -> list[tuple]:
        """[(fecha_hora, precio)] ordenados."""
        return [tuple(f) for f in self.db.execute(
            select(CotizacionIntradia.fecha_hora, CotizacionIntradia.precio).where(
                CotizacionIntradia.activo_id == activo_id,
                CotizacionIntradia.fecha_hora >= desde, CotizacionIntradia.fecha_hora < hasta)
            .order_by(CotizacionIntradia.fecha_hora)).all()]

    def momentos_intradia(self, activo_id: int, desde: datetime | None = None) -> list[datetime]:
        stmt = select(CotizacionIntradia.fecha_hora).where(CotizacionIntradia.activo_id == activo_id)
        if desde is not None:
            stmt = stmt.where(CotizacionIntradia.fecha_hora >= desde)
        return list(self.db.scalars(stmt))

    def cierres_desde(self, activo_id: int, desde: date) -> list[CierreDiario]:
        return list(self.db.scalars(select(CierreDiario).where(
            CierreDiario.activo_id == activo_id, CierreDiario.fecha >= desde).order_by(CierreDiario.fecha)))

    def cierre_anterior(self, activo_id: int, fecha: date):
        return self.db.scalars(select(CierreDiario.cierre).where(
            CierreDiario.activo_id == activo_id, CierreDiario.fecha < fecha)
            .order_by(CierreDiario.fecha.desc()).limit(1)).first()

    def cierres_todos_desde(self, desde: date) -> list[tuple]:
        """[(activo_id, cierre)] de todos los activos, ordenados por activo y fecha."""
        return [tuple(f) for f in self.db.execute(
            select(CierreDiario.activo_id, CierreDiario.cierre).where(CierreDiario.fecha >= desde)
            .order_by(CierreDiario.activo_id, CierreDiario.fecha)).all()]

    def cierres_de_activos(self, ids: list[int], desde: date) -> list[tuple]:
        """[(activo_id, fecha, cierre)] ordenados por fecha."""
        return [tuple(f) for f in self.db.execute(
            select(CierreDiario.activo_id, CierreDiario.fecha, CierreDiario.cierre).where(
                CierreDiario.activo_id.in_(ids), CierreDiario.fecha >= desde)
            .order_by(CierreDiario.fecha)).all()]

    def borrar_congelados(self, activo_id: int, precio) -> None:
        """Borra los cierres sin volumen y los puntos intradiarios que repiten un precio que la fuente dejó congelado."""
        self.db.execute(delete(CierreDiario).where(
            CierreDiario.activo_id == activo_id, CierreDiario.cierre == precio,
            or_(CierreDiario.volumen.is_(None), CierreDiario.volumen == 0)))
        self.db.execute(delete(CotizacionIntradia).where(
            CotizacionIntradia.activo_id == activo_id, CotizacionIntradia.precio == precio))

    def borrar_intradia_anterior(self, limite: datetime) -> None:
        self.db.execute(delete(CotizacionIntradia).where(CotizacionIntradia.fecha_hora < limite))
