from datetime import date, datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal

from sqlalchemy.orm import Session

from src.db.models.activo_model import Activo
from src.db.models.cuenta_model import Tenencia
from src.db.models.inversor_model import Inversor
from src.db.models.operacion_model import Operacion
from src.dtos.broker_dto import MepDTO, OperacionDTO
from src.mappers.broker_mapper import to_json, to_operacion
from src.repositories.broker_repository import CuentaRepository, OperacionRepository
from src.services.activo_service import obtener_activo
from src.services.cuenta_service import obtener_cuenta
from src.utils.errors import BusinessError
from src.utils.mercado import (COMISION, RIESGO_MAXIMO, TICKER_MEP_ARS, TICKER_MEP_USD, TZ_AR, a_utc, fmt, q2,
                               q4, validar_horario)


def validar_operable(activo: Activo) -> None:
    if not activo.activo:
        raise BusinessError(f"{activo.ticker} está suspendido y no se puede operar.")


def validar_perfil(inversor: Inversor, activo: Activo) -> None:
    """HU5: el perfil de riesgo solo restringe compras."""
    maximo = RIESGO_MAXIMO[inversor.perfil_riesgo]
    if activo.nivel_riesgo > maximo:
        raise BusinessError(
            f"{activo.ticker} tiene nivel de riesgo {activo.nivel_riesgo} y tu perfil "
            f"{inversor.perfil_riesgo} permite hasta {maximo}. Podés actualizar tu perfil."
        )


class OperacionService:
    def __init__(self, db: Session):
        self.db = db
        self.cuentas = CuentaRepository(db)
        self.repo = OperacionRepository(db)

    # ---------- API pública (cada una es una transacción) ----------
    def comprar(self, cuenta_id: int, cantidad: int, ahora: datetime,
                activo_id: int | None = None, ticker: str | None = None) -> OperacionDTO:
        op = self._comprar(cuenta_id, obtener_activo(self.db, activo_id, ticker), cantidad, ahora)
        self.db.commit()
        return to_operacion(op)

    def vender(self, cuenta_id: int, cantidad: int, ahora: datetime,
               activo_id: int | None = None, ticker: str | None = None) -> OperacionDTO:
        op = self._vender(cuenta_id, obtener_activo(self.db, activo_id, ticker), cantidad, ahora)
        self.db.commit()
        return to_operacion(op)

    def dolar_mep(self, cuenta_id: int, monto_ars: Decimal, ahora: datetime) -> MepDTO:
        """HU7: compra AL30 en pesos y vende AL30D en dólares. Las dos patas o ninguna."""
        al30 = obtener_activo(self.db, ticker=TICKER_MEP_ARS)
        al30d = obtener_activo(self.db, ticker=TICKER_MEP_USD)
        # Cantidad entera de nominales que alcanzan a pagarse con el monto (comisión incluida)
        cantidad = int((monto_ars / (al30.precio_actual * (1 + COMISION))).to_integral_value(ROUND_DOWN))
        if cantidad < 1:
            raise BusinessError(
                f"Con {fmt(monto_ars, 'ARS')} no alcanza para comprar 1 nominal de AL30 "
                f"({fmt(al30.precio_actual * (1 + COMISION), 'ARS')} con comisión)."
            )
        compra = self._comprar(cuenta_id, al30, cantidad, ahora)
        venta = self._vender(cuenta_id, al30d, cantidad, ahora, activo_tenencia=al30)
        self.db.commit()
        return MepDTO(tipo_cambio=q2(al30.precio_actual / al30d.precio_actual), cantidad_nominales=cantidad,
                      pesos_debitados=compra.total, dolares_acreditados=venta.total,
                      compra=to_operacion(compra), venta=to_operacion(venta))

    # ---------- HU11: historial ----------
    def historial(self, cuenta_id: int, desde: date | None, hasta: date | None,
                  tipo: str | None, ticker: str | None) -> dict:
        if desde and hasta and desde > hasta:
            raise BusinessError("'desde' no puede ser posterior a 'hasta'.")
        obtener_cuenta(self.db, cuenta_id)
        inicio = lambda d: a_utc(datetime.combine(d, time(0, 0), tzinfo=TZ_AR))  # noqa: E731
        ops = self.repo.historial(
            cuenta_id,
            inicio(desde) if desde else None,
            inicio(hasta + timedelta(days=1)) if hasta else None,
            tipo,
            ticker.strip().upper() if ticker else None,
        )
        comisiones = {"ARS": Decimal("0"), "USD": Decimal("0")}
        for op in ops:
            comisiones[op.activo.moneda] += op.comision
        return to_json({"operaciones": [to_operacion(o) for o in ops], "cantidad": len(ops),
                        "total_comisiones": comisiones})

    # ---------- Reglas (sin commit) ----------
    def _comprar(self, cuenta_id: int, activo: Activo, cantidad: int, ahora: datetime) -> Operacion:
        validar_horario(ahora)
        validar_operable(activo)
        cuenta = obtener_cuenta(self.db, cuenta_id, bloquear=True)
        validar_perfil(cuenta.inversor, activo)

        precio = activo.precio_actual
        bruto = q2(cantidad * precio)
        comision = q2(bruto * COMISION)
        total = bruto + comision
        if total > cuenta.saldo(activo.moneda):
            raise BusinessError(
                f"Saldo insuficiente: la compra cuesta {fmt(total, activo.moneda)} (con comisión) "
                f"y tenés {fmt(cuenta.saldo(activo.moneda), activo.moneda)}."
            )
        cuenta.ajustar_saldo(activo.moneda, -total)

        tenencia = self.cuentas.tenencia(cuenta.id, activo.id)
        if tenencia:  # precio promedio ponderado (sin comisión)
            nueva = tenencia.cantidad + cantidad
            tenencia.precio_promedio = q4((tenencia.cantidad * tenencia.precio_promedio + cantidad * precio) / nueva)
            tenencia.cantidad = nueva
        else:
            self.cuentas.add(Tenencia(cuenta_id=cuenta.id, activo_id=activo.id, cantidad=cantidad,
                                      precio_promedio=precio))

        op = Operacion(cuenta_id=cuenta.id, activo_id=activo.id, tipo="compra", cantidad=cantidad,
                       precio_unitario=precio, comision=comision, total=total, fecha=a_utc(ahora),
                       estado="ejecutada")
        op.activo = activo
        self.repo.add(op)
        return op

    def _vender(self, cuenta_id: int, activo: Activo, cantidad: int, ahora: datetime,
                activo_tenencia: Activo | None = None) -> Operacion:
        """`activo_tenencia` permite vender AL30D contra la tenencia de AL30 (mismo bono, otra moneda)."""
        validar_horario(ahora)
        validar_operable(activo)
        cuenta = obtener_cuenta(self.db, cuenta_id, bloquear=True)
        especie = activo_tenencia or activo
        tenencia = self.cuentas.tenencia(cuenta.id, especie.id)
        disponible = tenencia.cantidad if tenencia else 0
        if cantidad > disponible:
            raise BusinessError(f"No podés vender {cantidad} {activo.ticker}: tenés {disponible}.")

        precio = activo.precio_actual
        bruto = q2(cantidad * precio)
        comision = q2(bruto * COMISION)
        neto = bruto - comision
        cuenta.ajustar_saldo(activo.moneda, neto)

        # Ganancia respecto del precio promedio, neta de la comisión de venta.
        # Si se vende en otra moneda (pata USD del MEP) no tiene sentido compararlo.
        ganancia = None
        if activo_tenencia is None:
            ganancia = q2((precio - tenencia.precio_promedio) * cantidad - comision)

        tenencia.cantidad -= cantidad
        if tenencia.cantidad == 0:
            self.cuentas.delete(tenencia)

        op = Operacion(cuenta_id=cuenta.id, activo_id=activo.id, tipo="venta", cantidad=cantidad,
                       precio_unitario=precio, comision=comision, total=neto, fecha=a_utc(ahora),
                       estado="ejecutada", ganancia_realizada=ganancia)
        op.activo = activo
        self.repo.add(op)
        return op
