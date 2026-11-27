from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Index, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base
from src.db.models.activo_model import Activo
from src.db.models.cuenta_model import DINERO, PRECIO
from src.db.models.inversor_model import ahora_utc, en

TIPOS_OPERACION = ("compra", "venta")
# "ejecutada" la pone la app; "pendiente" y "rechazada" quedan para correcciones del administrador
ESTADOS_OPERACION = ("ejecutada", "pendiente", "rechazada")


class Operacion(Base):
    __tablename__ = "operaciones"
    __table_args__ = (
        CheckConstraint(f"tipo IN {en(TIPOS_OPERACION)}", name="ck_operacion_tipo"),
        CheckConstraint("cantidad > 0", name="ck_operacion_cantidad"),
        CheckConstraint("precio_unitario > 0", name="ck_operacion_precio"),
        CheckConstraint("comision >= 0", name="ck_operacion_comision"),
        CheckConstraint("total > 0", name="ck_operacion_total"),
        CheckConstraint(f"estado IN {en(ESTADOS_OPERACION)}", name="ck_operacion_estado"),
        # Historial por cuenta (HU11) y ranking de más operados en 7 días (HU12)
        Index("idx_operacion_cuenta_fecha", "cuenta_id", "fecha"),
        Index("idx_operacion_fecha_activo", "fecha", "activo_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas.id"), index=True)
    activo_id: Mapped[int] = mapped_column(ForeignKey("activos.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(6))
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario: Mapped[Decimal] = mapped_column(PRECIO)
    comision: Mapped[Decimal] = mapped_column(DINERO)
    total: Mapped[Decimal] = mapped_column(DINERO)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, index=True)
    estado: Mapped[str] = mapped_column(String(10), default="ejecutada")
    # HU6: ganancia o pérdida realizada respecto del precio promedio (solo ventas)
    ganancia_realizada: Mapped[Decimal | None] = mapped_column(DINERO, nullable=True)

    activo: Mapped[Activo] = relationship()
