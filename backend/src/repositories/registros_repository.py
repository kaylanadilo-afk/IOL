"""Queries de los endpoints de registros (buscar, contar dependencias y borrar). Sin lógica de negocio."""
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from src.db.models.activo_model import CierreDiario, CotizacionIntradia, Dividendo
from src.db.models.cuenta_model import Cuenta, Movimiento, Tenencia
from src.db.models.inversor_model import favoritos
from src.db.models.operacion_model import Operacion


class RegistrosRepository:
    def __init__(self, db: Session):
        self.db = db

    def buscar(self, modelo, *clave):
        return self.db.get(modelo, clave if len(clave) > 1 else clave[0])

    def agregar(self, obj) -> None:
        self.db.add(obj)
        self.db.flush()

    def borrar(self, obj) -> None:
        self.db.delete(obj)
        self.db.flush()

    def contar(self, modelo, **filtros) -> int:
        q = select(func.count()).select_from(modelo)
        for campo, valor in filtros.items():
            q = q.where(getattr(modelo, campo) == valor)
        return self.db.scalar(q) or 0

    def cuenta_de_inversor(self, inversor_id: int) -> Cuenta | None:
        return self.db.scalar(select(Cuenta).where(Cuenta.inversor_id == inversor_id))

    # ---------- Favoritos (tabla de relación) ----------
    def favorito(self, inversor_id: int, activo_id: int):
        return self.db.execute(
            select(favoritos).where(favoritos.c.inversor_id == inversor_id, favoritos.c.activo_id == activo_id)
        ).mappings().first()

    def agregar_favorito(self, inversor_id: int, activo_id: int) -> None:
        self.db.execute(insert(favoritos).values(inversor_id=inversor_id, activo_id=activo_id))

    def borrar_favorito(self, inversor_id: int, activo_id: int) -> None:
        self.db.execute(delete(favoritos).where(favoritos.c.inversor_id == inversor_id,
                                                favoritos.c.activo_id == activo_id))

    def borrar_favoritos_de(self, inversor_id: int | None = None, activo_id: int | None = None) -> None:
        q = delete(favoritos)
        q = q.where(favoritos.c.inversor_id == inversor_id) if inversor_id else q.where(favoritos.c.activo_id == activo_id)
        self.db.execute(q)

    # ---------- Datos que se van con un activo ----------
    def borrar_historial_de_activo(self, activo_id: int) -> None:
        for modelo in (CierreDiario, CotizacionIntradia, Dividendo):
            self.db.execute(delete(modelo).where(modelo.activo_id == activo_id))

    def tiene_movimientos_u_operaciones(self, cuenta_id: int) -> bool:
        return bool(self.contar(Operacion, cuenta_id=cuenta_id) or self.contar(Movimiento, cuenta_id=cuenta_id)
                    or self.contar(Tenencia, cuenta_id=cuenta_id))
