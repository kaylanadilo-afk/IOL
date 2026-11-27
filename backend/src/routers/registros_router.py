"""Alta, consulta, edición y baja de cada tabla (los endpoints que trae el backend InitialStructure).

Todo pide sesión (header Authorization: Bearer <token>). Consultar y operar se puede solo sobre la propia cuenta.
Editar y borrar es solo para administradores: son correcciones manuales que no recalculan saldos.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.dtos.broker_dto import (ActivoDTO, CuentaDTO, DividendoRegistroDTO, FavoritoDTO, InversorDTO, MovimientoDTO,
                                 OperacionDTO, TenenciaDTO)
from src.schemas.registros_schema import (CreateCuentaSchema, CreateMovimientoSchema, CreateOperacionSchema,
                                          CreateTenenciaSchema, FavoritoSchema, UpdateActivoSchema, UpdateCuentaSchema,
                                          UpdateDividendoSchema, UpdateInversorSchema, UpdateMovimientoSchema,
                                          UpdateOperacionSchema, UpdateTenenciaSchema)
from src.services.registros_service import RegistrosService
from src.utils.autorizacion import (cuenta_autorizada, inversor_autorizado, solo_admin, usuario_actual, verificar_cuenta,
                                    verificar_inversor)
from src.utils.mercado import get_ahora

ADMIN = "Registros (admin)"
SIN_CONTENIDO = {"status_code": status.HTTP_204_NO_CONTENT, "response_class": Response}

# ---------- Inversores, cuentas y activos: edición y baja (el alta y la consulta ya existían) ----------
inversores = APIRouter(prefix="/inversores", tags=[ADMIN])


@inversores.put("/{inversor_id}", response_model=InversorDTO)
def editar_inversor(inversor_id: int, payload: UpdateInversorSchema, db: Session = Depends(get_db),
                    _=Depends(solo_admin)):
    return RegistrosService(db).actualizar_inversor(inversor_id, payload.model_dump(exclude_unset=True))


@inversores.delete("/{inversor_id}", **SIN_CONTENIDO)
def borrar_inversor(inversor_id: int, db: Session = Depends(get_db), admin: InversorDTO = Depends(solo_admin)):
    RegistrosService(db).borrar_inversor(inversor_id, admin.id)


cuentas = APIRouter(prefix="/cuentas", tags=[ADMIN])


@cuentas.post("", response_model=CuentaDTO, status_code=status.HTTP_201_CREATED,
              summary="Abrir la cuenta comitente de un inversor que no tiene")
def abrir_cuenta(payload: CreateCuentaSchema, db: Session = Depends(get_db), _=Depends(solo_admin)):
    return RegistrosService(db).crear_cuenta(payload.inversor_id)


@cuentas.put("/{cuenta_id}", response_model=CuentaDTO, summary="Ajuste manual de saldos")
def editar_cuenta(cuenta_id: int, payload: UpdateCuentaSchema, db: Session = Depends(get_db), _=Depends(solo_admin)):
    return RegistrosService(db).actualizar_cuenta(cuenta_id, payload.model_dump(exclude_unset=True))


@cuentas.delete("/{cuenta_id}", **SIN_CONTENIDO, summary="Borrar una cuenta sin saldo ni actividad")
def borrar_cuenta(cuenta_id: int, db: Session = Depends(get_db), _=Depends(solo_admin)):
    RegistrosService(db).borrar_cuenta(cuenta_id)


activos = APIRouter(prefix="/activos", tags=[ADMIN])


@activos.put("/{activo_id}", response_model=ActivoDTO)
def editar_activo(activo_id: int, payload: UpdateActivoSchema, db: Session = Depends(get_db), _=Depends(solo_admin),
                  ahora: datetime = Depends(get_ahora)):
    return RegistrosService(db).actualizar_activo(activo_id, payload.model_dump(exclude_unset=True), ahora)


@activos.delete("/{activo_id}", **SIN_CONTENIDO, summary="Borrar un activo que nunca se operó")
def borrar_activo(activo_id: int, db: Session = Depends(get_db), _=Depends(solo_admin)):
    RegistrosService(db).borrar_activo(activo_id)


# ---------- Operaciones ----------
operaciones = APIRouter(prefix="/operaciones", tags=["Operaciones"])


@operaciones.post("", response_model=OperacionDTO, status_code=status.HTTP_201_CREATED,
                  summary="Compra o venta (mismas reglas que /cuentas/{id}/compras y /ventas)")
def crear_operacion(payload: CreateOperacionSchema, db: Session = Depends(get_db),
                    ahora: datetime = Depends(get_ahora), yo: InversorDTO = Depends(usuario_actual)):
    verificar_cuenta(db, payload.cuenta_id, yo)
    return RegistrosService(db).crear_operacion(payload.cuenta_id, payload.tipo, payload.cantidad, ahora,
                                                payload.activo_id, payload.ticker)


@operaciones.get("/{operacion_id}", response_model=OperacionDTO)
def ver_operacion(operacion_id: int, db: Session = Depends(get_db), yo: InversorDTO = Depends(usuario_actual)):
    op = RegistrosService(db).obtener_operacion(operacion_id)
    verificar_cuenta(db, op.cuenta_id, yo)
    return op


@operaciones.put("/{operacion_id}", response_model=OperacionDTO, tags=[ADMIN], summary="Cambiar el estado")
def editar_operacion(operacion_id: int, payload: UpdateOperacionSchema, db: Session = Depends(get_db),
                     _=Depends(solo_admin)):
    return RegistrosService(db).actualizar_operacion(operacion_id, payload.estado)


@operaciones.delete("/{operacion_id}", **SIN_CONTENIDO, tags=[ADMIN])
def borrar_operacion(operacion_id: int, db: Session = Depends(get_db), _=Depends(solo_admin)):
    RegistrosService(db).borrar_operacion(operacion_id)


# ---------- Movimientos ----------
movimientos = APIRouter(prefix="/movimientos", tags=["Cuentas"])


@movimientos.post("", response_model=MovimientoDTO, status_code=status.HTTP_201_CREATED,
                  summary="Depósito o extracción (mismas reglas que /cuentas/{id}/depositos y /extracciones)")
def crear_movimiento(payload: CreateMovimientoSchema, db: Session = Depends(get_db),
                     yo: InversorDTO = Depends(usuario_actual)):
    verificar_cuenta(db, payload.cuenta_id, yo)
    return RegistrosService(db).crear_movimiento(payload.cuenta_id, payload.tipo, payload.moneda, payload.monto)


@movimientos.get("/{movimiento_id}", response_model=MovimientoDTO)
def ver_movimiento(movimiento_id: int, db: Session = Depends(get_db), yo: InversorDTO = Depends(usuario_actual)):
    mov = RegistrosService(db).obtener_movimiento(movimiento_id)
    verificar_cuenta(db, mov.cuenta_id, yo)
    return mov


@movimientos.put("/{movimiento_id}", response_model=MovimientoDTO, tags=[ADMIN], summary="Cambiar la descripción")
def editar_movimiento(movimiento_id: int, payload: UpdateMovimientoSchema, db: Session = Depends(get_db),
                      _=Depends(solo_admin)):
    return RegistrosService(db).actualizar_movimiento(movimiento_id, payload.descripcion)


@movimientos.delete("/{movimiento_id}", **SIN_CONTENIDO, tags=[ADMIN])
def borrar_movimiento(movimiento_id: int, db: Session = Depends(get_db), _=Depends(solo_admin)):
    RegistrosService(db).borrar_movimiento(movimiento_id)


# ---------- Tenencias ----------
tenencias = APIRouter(prefix="/tenencias", tags=["Cuentas"])


@tenencias.post("", response_model=TenenciaDTO, status_code=status.HTTP_201_CREATED, tags=[ADMIN])
def crear_tenencia(payload: CreateTenenciaSchema, db: Session = Depends(get_db), _=Depends(solo_admin)):
    return RegistrosService(db).crear_tenencia(payload.cuenta_id, payload.activo_id, payload.cantidad,
                                               payload.precio_promedio)


@tenencias.get("/{cuenta_id}/{activo_id}", response_model=TenenciaDTO)
def ver_tenencia(cuenta_id: int, activo_id: int, db: Session = Depends(get_db), _yo=Depends(cuenta_autorizada)):
    return RegistrosService(db).obtener_tenencia(cuenta_id, activo_id)


@tenencias.put("/{cuenta_id}/{activo_id}", response_model=TenenciaDTO, tags=[ADMIN])
def editar_tenencia(cuenta_id: int, activo_id: int, payload: UpdateTenenciaSchema, db: Session = Depends(get_db),
                    _=Depends(solo_admin)):
    return RegistrosService(db).actualizar_tenencia(cuenta_id, activo_id, payload.model_dump(exclude_unset=True))


@tenencias.delete("/{cuenta_id}/{activo_id}", **SIN_CONTENIDO, tags=[ADMIN])
def borrar_tenencia(cuenta_id: int, activo_id: int, db: Session = Depends(get_db), _=Depends(solo_admin)):
    RegistrosService(db).borrar_tenencia(cuenta_id, activo_id)


# ---------- Dividendos (el pago ya existía en POST /dividendos) ----------
dividendos = APIRouter(prefix="/dividendos", tags=["Activos (admin)"])


@dividendos.get("/{dividendo_id}", response_model=DividendoRegistroDTO)
def ver_dividendo(dividendo_id: int, db: Session = Depends(get_db)):
    return RegistrosService(db).obtener_dividendo(dividendo_id)


@dividendos.put("/{dividendo_id}", response_model=DividendoRegistroDTO, tags=[ADMIN],
                summary="Corregir el registro (no vuelve a pagar ni descuenta lo acreditado)")
def editar_dividendo(dividendo_id: int, payload: UpdateDividendoSchema, db: Session = Depends(get_db),
                     _=Depends(solo_admin)):
    return RegistrosService(db).actualizar_dividendo(dividendo_id, payload.model_dump(exclude_unset=True))


@dividendos.delete("/{dividendo_id}", **SIN_CONTENIDO, tags=[ADMIN])
def borrar_dividendo(dividendo_id: int, db: Session = Depends(get_db), _=Depends(solo_admin)):
    RegistrosService(db).borrar_dividendo(dividendo_id)


# ---------- Favoritos ----------
favoritos = APIRouter(prefix="/favoritos", tags=["Favoritos"])


@favoritos.post("", response_model=FavoritoDTO, status_code=status.HTTP_201_CREATED)
def crear_favorito(payload: FavoritoSchema, db: Session = Depends(get_db), yo: InversorDTO = Depends(usuario_actual)):
    verificar_inversor(payload.inversor_id, yo)
    return RegistrosService(db).crear_favorito(payload.inversor_id, payload.activo_id)


@favoritos.get("/{inversor_id}/{activo_id}", response_model=FavoritoDTO)
def ver_favorito(inversor_id: int, activo_id: int, db: Session = Depends(get_db), _yo=Depends(inversor_autorizado)):
    return RegistrosService(db).obtener_favorito(inversor_id, activo_id)


@favoritos.delete("/{inversor_id}/{activo_id}", **SIN_CONTENIDO)
def borrar_favorito(inversor_id: int, activo_id: int, db: Session = Depends(get_db), _yo=Depends(inversor_autorizado)):
    RegistrosService(db).borrar_favorito(inversor_id, activo_id)


ROUTERS = (inversores, cuentas, activos, operaciones, movimientos, tenencias, dividendos, favoritos)
