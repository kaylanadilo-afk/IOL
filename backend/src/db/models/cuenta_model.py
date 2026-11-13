from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base
from src.db.models.inversor_model import Inversor, ahora_utc, en

MONEDAS = ("ARS", "USD")
TIPOS_MOVIMIENTO = ("deposito", "extraccion", "dividendo")
DINERO = Numeric(18, 2)
PRECIO = Numeric(18, 4)


class Cuenta(Base):
    __tablename__ = "cuentas"
    __table_args__ = (
        CheckConstraint("saldo_ars >= 0", name="ck_cuenta_saldo_ars"),
        CheckConstraint("saldo_usd >= 0", name="ck_cuenta_saldo_usd"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    inversor_id: Mapped[int] = mapped_column(ForeignKey("inversores.id"), unique=True)
    numero_comitente: Mapped[int] = mapped_column(Integer, unique=True)
    saldo_ars: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    saldo_usd: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))

    inversor: Mapped[Inversor] = relationship(back_populates="cuenta")
    tenencias: Mapped[list["Tenencia"]] = relationship(back_populates="cuenta", cascade="all, delete-orphan")

    def saldo(self, moneda: str) -> Decimal:
        return self.saldo_ars if moneda == "ARS" else self.saldo_usd

    def ajustar_saldo(self, moneda: str, delta: Decimal) -> None:
        if moneda == "ARS":
            self.saldo_ars = self.saldo_ars + delta
        else:
            self.saldo_usd = self.saldo_usd + delta


class Tenencia(Base):
    """Relación N a M cuenta <-> activo, con cantidad y precio promedio."""

    __tablename__ = "tenencias"
    __table_args__ = (CheckConstraint("cantidad > 0", name="ck_tenencia_cantidad"),)

    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas.id"), primary_key=True)
    activo_id: Mapped[int] = mapped_column(ForeignKey("activos.id"), primary_key=True)
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_promedio: Mapped[Decimal] = mapped_column(PRECIO)

    cuenta: Mapped[Cuenta] = relationship(back_populates="tenencias")
    activo: Mapped["Activo"] = relationship()


class Movimiento(Base):
    __tablename__ = "movimientos"
    __table_args__ = (
        CheckConstraint(f"tipo IN {en(TIPOS_MOVIMIENTO)}", name="ck_movimiento_tipo"),
        CheckConstraint(f"moneda IN {en(MONEDAS)}", name="ck_movimiento_moneda"),
        CheckConstraint("monto > 0", name="ck_movimiento_monto"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(10))
    moneda: Mapped[str] = mapped_column(String(3))
    monto: Mapped[Decimal] = mapped_column(DINERO)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    descripcion: Mapped[str] = mapped_column(String(200), default="")
