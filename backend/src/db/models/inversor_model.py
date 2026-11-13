from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base

PERFILES = ("conservador", "moderado", "agresivo")


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def en(valores) -> str:
    return "(" + ", ".join(f"'{v}'" for v in valores) + ")"


# Relación N a M: inversor <-> activo marcado como favorito
favoritos = Table(
    "favoritos",
    Base.metadata,
    Column("inversor_id", ForeignKey("inversores.id", ondelete="CASCADE"), primary_key=True),
    Column("activo_id", ForeignKey("activos.id", ondelete="CASCADE"), primary_key=True),
)


class Inversor(Base):
    __tablename__ = "inversores"
    __table_args__ = (
        CheckConstraint(f"perfil_riesgo IN {en(PERFILES)}", name="ck_inversor_perfil"),
        CheckConstraint("length(cuit) = 11", name="ck_inversor_cuit"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    cuit: Mapped[str] = mapped_column(String(11), unique=True)
    perfil_riesgo: Mapped[str] = mapped_column(String(12))
    fecha_alta: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    # Solo los perfiles autorizados ven la sección de Administración (no se elige al darse de alta)
    es_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Hash scrypt de la contraseña (nunca el texto). Ver src/utils/seguridad.py
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)

    cuenta: Mapped["Cuenta"] = relationship(back_populates="inversor", uselist=False)
    favoritos: Mapped[list["Activo"]] = relationship(secondary=favoritos, order_by="Activo.ticker")
