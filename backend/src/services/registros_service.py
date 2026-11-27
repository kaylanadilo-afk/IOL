"""Alta, edición y baja de cada tabla (lo que trae el backend InitialStructure), sobre nuestras reglas.

- Las altas de operaciones y movimientos pasan por la lógica del broker (saldos, comisión, horario, perfil).
- Las ediciones y bajas son correcciones del administrador: cambian el registro tal cual y NO recalculan
  saldos ni tenencias. Los borrados que dejarían datos huérfanos se rechazan con un mensaje claro.
"""
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models.activo_model import Activo, Dividendo
from src.db.models.cuenta_model import Cuenta, Movimiento, Tenencia
from src.db.models.inversor_model import Inversor
from src.db.models.operacion_model import Operacion
from src.dtos.broker_dto import (ActivoDTO, CuentaDTO, DividendoRegistroDTO, FavoritoDTO, InversorDTO, MovimientoDTO,
                                 OperacionDTO, TenenciaDTO)
from src.mappers.broker_mapper import to_activo, to_cuenta, to_inversor, to_movimiento, to_operacion
from src.repositories.broker_repository import CuentaRepository
from src.repositories.registros_repository import RegistrosRepository
from src.services.cuenta_service import CuentaService
from src.services.operacion_service import OperacionService
from src.utils.errors import BusinessError, ConflictError, no_encontrado


class RegistrosService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RegistrosRepository(db)

    def _get(self, modelo, nombre: str, *clave):
        obj = self.repo.buscar(modelo, *clave)
        if obj is None:
            raise no_encontrado(nombre)
        return obj

    def _guardar(self) -> None:
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise ConflictError("El cambio choca con otro registro (dato repetido o relacionado).") from e

    # ---------- Inversores ----------
    def actualizar_inversor(self, inversor_id: int, cambios: dict) -> InversorDTO:
        inv = self._get(Inversor, "Inversor", inversor_id)
        if "email" in cambios and cambios["email"] != inv.email:
            if self.db.query(Inversor).filter(Inversor.email == cambios["email"]).first():
                raise ConflictError("Ya existe una cuenta con este correo", campo="email")
        if "cuit" in cambios and cambios["cuit"] != inv.cuit:
            if self.db.query(Inversor).filter(Inversor.cuit == cambios["cuit"]).first():
                raise ConflictError("Ya existe una cuenta con este CUIT", campo="cuit")
        for campo, valor in cambios.items():
            setattr(inv, campo, valor)
        self._guardar()
        return to_inversor(inv)

    def borrar_inversor(self, inversor_id: int, quien: int) -> None:
        inv = self._get(Inversor, "Inversor", inversor_id)
        if inv.id == quien:
            raise BusinessError("No podés borrar tu propia cuenta de administrador.")
        if inv.es_admin:
            raise BusinessError("No se puede borrar un administrador.")
        cuenta = self.repo.cuenta_de_inversor(inv.id)
        if cuenta:
            self._validar_cuenta_vacia(cuenta)
            self.repo.borrar(cuenta)
        self.repo.borrar_favoritos_de(inversor_id=inv.id)
        self.repo.borrar(inv)
        self._guardar()

    # ---------- Cuentas ----------
    def crear_cuenta(self, inversor_id: int) -> CuentaDTO:
        inv = self._get(Inversor, "Inversor", inversor_id)
        if self.repo.cuenta_de_inversor(inv.id):
            raise ConflictError("Ese inversor ya tiene una cuenta comitente.")
        cuentas = CuentaRepository(self.db)
        cuenta = Cuenta(inversor_id=inv.id, numero_comitente=(cuentas.max_numero_comitente() or 100000) + 1)
        self.repo.agregar(cuenta)
        self._guardar()
        return to_cuenta(cuenta)

    def actualizar_cuenta(self, cuenta_id: int, cambios: dict) -> CuentaDTO:
        cuenta = self._get(Cuenta, "Cuenta", cuenta_id)
        for campo, valor in cambios.items():
            setattr(cuenta, campo, valor)
        self._guardar()
        return to_cuenta(cuenta)

    def _validar_cuenta_vacia(self, cuenta: Cuenta) -> None:
        if cuenta.saldo_ars or cuenta.saldo_usd:
            raise BusinessError("La cuenta todavía tiene saldo: extraelo antes de borrarla.")
        if self.repo.tiene_movimientos_u_operaciones(cuenta.id):
            raise BusinessError("La cuenta tiene tenencias, operaciones o movimientos: no se puede borrar.")

    def borrar_cuenta(self, cuenta_id: int) -> None:
        cuenta = self._get(Cuenta, "Cuenta", cuenta_id)
        self._validar_cuenta_vacia(cuenta)
        self.repo.borrar(cuenta)
        self._guardar()

    # ---------- Activos ----------
    def actualizar_activo(self, activo_id: int, cambios: dict, ahora: datetime | None = None) -> ActivoDTO:
        activo = self._get(Activo, "Activo", activo_id)
        en_uso = self.repo.contar(Operacion, activo_id=activo.id) or self.repo.contar(Tenencia, activo_id=activo.id)
        for campo in ("tipo", "moneda"):
            if campo in cambios and cambios[campo] != getattr(activo, campo) and en_uso:
                raise BusinessError(f"No se puede cambiar el {campo} de un activo que ya se operó o que alguien tiene.",
                                    campo=campo)
        precio = cambios.pop("precio_actual", None)
        for campo, valor in cambios.items():
            setattr(activo, campo, valor)
        self._guardar()
        if precio is not None:  # mismo camino que PATCH /precio: historial y alertas
            from src.services.activo_service import ActivoService
            return ActivoService(self.db).actualizar_precio(activo.id, precio, ahora)
        return to_activo(activo)

    def borrar_activo(self, activo_id: int) -> None:
        activo = self._get(Activo, "Activo", activo_id)
        if self.repo.contar(Operacion, activo_id=activo.id) or self.repo.contar(Tenencia, activo_id=activo.id):
            raise BusinessError("El activo ya se operó o alguien lo tiene: suspendelo en vez de borrarlo.")
        self.repo.borrar_favoritos_de(activo_id=activo.id)
        self.repo.borrar_historial_de_activo(activo.id)
        self.repo.borrar(activo)
        self._guardar()

    # ---------- Operaciones ----------
    def crear_operacion(self, cuenta_id: int, tipo: str, cantidad: int, ahora: datetime,
                        activo_id: int | None, ticker: str | None) -> OperacionDTO:
        servicio = OperacionService(self.db)
        hacer = servicio.comprar if tipo == "compra" else servicio.vender
        return hacer(cuenta_id, cantidad, ahora, activo_id=activo_id, ticker=ticker)

    def obtener_operacion(self, operacion_id: int) -> OperacionDTO:
        return to_operacion(self._get(Operacion, "Operación", operacion_id))

    def actualizar_operacion(self, operacion_id: int, estado: str) -> OperacionDTO:
        op = self._get(Operacion, "Operación", operacion_id)
        op.estado = estado
        self._guardar()
        return to_operacion(op)

    def borrar_operacion(self, operacion_id: int) -> None:
        self.repo.borrar(self._get(Operacion, "Operación", operacion_id))
        self._guardar()

    # ---------- Movimientos ----------
    def crear_movimiento(self, cuenta_id: int, tipo: str, moneda: str, monto) -> MovimientoDTO:
        servicio = CuentaService(self.db)
        return (servicio.depositar if tipo == "deposito" else servicio.extraer)(cuenta_id, moneda, monto)

    def obtener_movimiento(self, movimiento_id: int) -> MovimientoDTO:
        return to_movimiento(self._get(Movimiento, "Movimiento", movimiento_id))

    def actualizar_movimiento(self, movimiento_id: int, descripcion: str) -> MovimientoDTO:
        mov = self._get(Movimiento, "Movimiento", movimiento_id)
        mov.descripcion = descripcion
        self._guardar()
        return to_movimiento(mov)

    def borrar_movimiento(self, movimiento_id: int) -> None:
        self.repo.borrar(self._get(Movimiento, "Movimiento", movimiento_id))
        self._guardar()

    # ---------- Tenencias ----------
    def crear_tenencia(self, cuenta_id: int, activo_id: int, cantidad: int, precio_promedio) -> TenenciaDTO:
        self._get(Cuenta, "Cuenta", cuenta_id)
        self._get(Activo, "Activo", activo_id)
        if self.repo.buscar(Tenencia, cuenta_id, activo_id):
            raise ConflictError("Esa cuenta ya tiene ese activo: editá la tenencia existente.")
        ten = Tenencia(cuenta_id=cuenta_id, activo_id=activo_id, cantidad=cantidad, precio_promedio=precio_promedio)
        self.repo.agregar(ten)
        self._guardar()
        return TenenciaDTO.model_validate(ten)

    def obtener_tenencia(self, cuenta_id: int, activo_id: int) -> TenenciaDTO:
        return TenenciaDTO.model_validate(self._get(Tenencia, "Tenencia", cuenta_id, activo_id))

    def actualizar_tenencia(self, cuenta_id: int, activo_id: int, cambios: dict) -> TenenciaDTO:
        ten = self._get(Tenencia, "Tenencia", cuenta_id, activo_id)
        for campo, valor in cambios.items():
            setattr(ten, campo, valor)
        self._guardar()
        return TenenciaDTO.model_validate(ten)

    def borrar_tenencia(self, cuenta_id: int, activo_id: int) -> None:
        self.repo.borrar(self._get(Tenencia, "Tenencia", cuenta_id, activo_id))
        self._guardar()

    # ---------- Dividendos ----------
    def obtener_dividendo(self, dividendo_id: int) -> DividendoRegistroDTO:
        return DividendoRegistroDTO.model_validate(self._get(Dividendo, "Dividendo", dividendo_id))

    def actualizar_dividendo(self, dividendo_id: int, cambios: dict) -> DividendoRegistroDTO:
        div = self._get(Dividendo, "Dividendo", dividendo_id)
        for campo, valor in cambios.items():
            setattr(div, campo, valor)
        self._guardar()
        return DividendoRegistroDTO.model_validate(div)

    def borrar_dividendo(self, dividendo_id: int) -> None:
        self.repo.borrar(self._get(Dividendo, "Dividendo", dividendo_id))
        self._guardar()

    # ---------- Favoritos ----------
    def _favorito(self, inversor_id: int, activo_id: int) -> FavoritoDTO:
        fila = self.repo.favorito(inversor_id, activo_id)
        if not fila:
            raise no_encontrado("Favorito")
        return FavoritoDTO(**dict(fila))

    def crear_favorito(self, inversor_id: int, activo_id: int) -> FavoritoDTO:
        self._get(Inversor, "Inversor", inversor_id)
        self._get(Activo, "Activo", activo_id)
        if self.repo.favorito(inversor_id, activo_id):
            raise ConflictError("Ese activo ya está en favoritos.")
        self.repo.agregar_favorito(inversor_id, activo_id)
        self._guardar()
        return self._favorito(inversor_id, activo_id)

    def obtener_favorito(self, inversor_id: int, activo_id: int) -> FavoritoDTO:
        return self._favorito(inversor_id, activo_id)

    def borrar_favorito(self, inversor_id: int, activo_id: int) -> None:
        self._favorito(inversor_id, activo_id)
        self.repo.borrar_favorito(inversor_id, activo_id)
        self._guardar()
