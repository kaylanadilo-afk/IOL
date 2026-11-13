from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base
from src.db.models.cuenta_model import MONEDAS, PRECIO
from src.db.models.inversor_model import en

TIPOS_ACTIVO = ("accion", "cedear", "bono")


class Activo(Base):
    __tablename__ = "activos"
    __table_args__ = (
        CheckConstraint(f"tipo IN {en(TIPOS_ACTIVO)}", name="ck_activo_tipo"),
        CheckConstraint(f"moneda IN {en(MONEDAS)}", name="ck_activo_moneda"),
        CheckConstraint("precio_actual > 0", name="ck_activo_precio"),
        CheckConstraint("nivel_riesgo BETWEEN 1 AND 5", name="ck_activo_riesgo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(12), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(10))
    moneda: Mapped[str] = mapped_column(String(3))
    precio_actual: Mapped[Decimal] = mapped_column(PRECIO)
    nivel_riesgo: Mapped[int] = mapped_column(Integer)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Datos de mercado (se completan al sincronizar con precios reales)
    variacion_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 2), nullable=True)
    precio_actualizado: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Dividendo(Base):
    __tablename__ = "dividendos"
    __table_args__ = (CheckConstraint("monto_por_unidad > 0", name="ck_dividendo_monto"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    activo_id: Mapped[int] = mapped_column(ForeignKey("activos.id"), index=True)
    monto_por_unidad: Mapped[Decimal] = mapped_column(PRECIO)
    fecha_pago: Mapped[date] = mapped_column(Date)

    activo: Mapped[Activo] = relationship()


class CierreDiario(Base):
    """Historial diario de cada activo: una fila por día con apertura, máximo, mínimo y cierre."""

    __tablename__ = "cierres_diarios"
    __table_args__ = (CheckConstraint("cierre > 0", name="ck_cierre_positivo"),)

    activo_id: Mapped[int] = mapped_column(ForeignKey("activos.id", ondelete="CASCADE"), primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    apertura: Mapped[Decimal] = mapped_column(PRECIO)
    maximo: Mapped[Decimal] = mapped_column(PRECIO)
    minimo: Mapped[Decimal] = mapped_column(PRECIO)
    cierre: Mapped[Decimal] = mapped_column(PRECIO)
    volumen: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)


class CotizacionIntradia(Base):
    """Precio de un activo a lo largo de la rueda (un punto por minuto aprox.)."""

    __tablename__ = "cotizaciones_intradia"

    activo_id: Mapped[int] = mapped_column(ForeignKey("activos.id", ondelete="CASCADE"), primary_key=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    precio: Mapped[Decimal] = mapped_column(PRECIO)
