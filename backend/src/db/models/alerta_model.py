"""Alertas de precio y avisos dentro de la app."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base
from src.db.models.activo_model import Activo
from src.db.models.cuenta_model import PRECIO
from src.db.models.inversor_model import ahora_utc, en

TIPOS_ALERTA = ("sube_pct", "baja_pct", "precio")
ESTADOS_ALERTA = ("activa", "pausada", "ejecutada")


class Alerta(Base):
    """El objetivo se calcula al crearla: sube/baja X % respecto del precio de ese momento, o un precio fijo.

    `direccion` dice si se dispara al llegar por arriba ("sube") o por abajo ("baja").
    `cumplida` recuerda si la condición ya se cumplía en la última revisión: así se avisa una sola vez
    por cruce (y una alerta recurrente se vuelve a armar recién cuando el precio sale de la condición).
    """

    __tablename__ = "alertas"
    __table_args__ = (
        CheckConstraint(f"tipo IN {en(TIPOS_ALERTA)}", name="ck_alerta_tipo"),
        CheckConstraint(f"estado IN {en(ESTADOS_ALERTA)}", name="ck_alerta_estado"),
        CheckConstraint("direccion IN ('sube', 'baja')", name="ck_alerta_direccion"),
        CheckConstraint("valor > 0", name="ck_alerta_valor"),
        CheckConstraint("precio_referencia > 0 AND precio_objetivo > 0", name="ck_alerta_precios"),
        Index("idx_alerta_estado_activo", "estado", "activo_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    inversor_id: Mapped[int] = mapped_column(ForeignKey("inversores.id", ondelete="CASCADE"), index=True)
    activo_id: Mapped[int] = mapped_column(ForeignKey("activos.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(10))
    valor: Mapped[Decimal] = mapped_column(Numeric(18, 4))  # porcentaje o precio, según el tipo
    direccion: Mapped[str] = mapped_column(String(4))
    precio_referencia: Mapped[Decimal] = mapped_column(PRECIO)
    precio_objetivo: Mapped[Decimal] = mapped_column(PRECIO)
    estado: Mapped[str] = mapped_column(String(10), default="activa")
    recurrente: Mapped[bool] = mapped_column(Boolean, default=False)
    aviso_email: Mapped[bool] = mapped_column(Boolean, default=True)
    aviso_app: Mapped[bool] = mapped_column(Boolean, default=True)
    cumplida: Mapped[bool] = mapped_column(Boolean, default=False)
    veces_disparada: Mapped[int] = mapped_column(Integer, default=0)
    creada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    ultima_vez: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    activo: Mapped[Activo] = relationship(lazy="joined")


class Notificacion(Base):
    """Aviso dentro de la app. También es el historial de alertas disparadas."""

    __tablename__ = "notificaciones"
    __table_args__ = (Index("idx_notificacion_inversor_fecha", "inversor_id", "fecha"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    inversor_id: Mapped[int] = mapped_column(ForeignKey("inversores.id", ondelete="CASCADE"))
    alerta_id: Mapped[int | None] = mapped_column(ForeignKey("alertas.id", ondelete="SET NULL"), nullable=True)
    activo_id: Mapped[int | None] = mapped_column(ForeignKey("activos.id", ondelete="SET NULL"), nullable=True)
    titulo: Mapped[str] = mapped_column(String(120))
    mensaje: Mapped[str] = mapped_column(String(400))
    precio: Mapped[Decimal | None] = mapped_column(PRECIO, nullable=True)
    variacion_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 2), nullable=True)
    email_enviado: Mapped[bool] = mapped_column(Boolean, default=False)
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
