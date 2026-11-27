from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from src.db.models.cuenta_model import Cuenta, Movimiento
from src.dtos.broker_dto import CuentaDTO, MovimientoDTO
from src.mappers.broker_mapper import to_cuenta, to_json, to_movimiento
from src.repositories.broker_repository import CuentaRepository, OperacionRepository
from src.services.activo_service import tipo_cambio_mep
from src.utils.errors import BusinessError, no_encontrado
from src.utils.mercado import TZ_AR, a_utc, fmt, q2


def obtener_cuenta(db: Session, cuenta_id: int, bloquear: bool = False) -> Cuenta:
    cuenta = CuentaRepository(db).find_by_id(cuenta_id, bloquear)
    if not cuenta:
        raise no_encontrado("Cuenta")
    return cuenta


class CuentaService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CuentaRepository(db)

    def obtener(self, cuenta_id: int) -> CuentaDTO:
        return to_cuenta(obtener_cuenta(self.db, cuenta_id))

    # ---------- HU3: depósitos y extracciones ----------
    def depositar(self, cuenta_id: int, moneda: str, monto: Decimal) -> MovimientoDTO:
        cuenta = obtener_cuenta(self.db, cuenta_id, bloquear=True)
        cuenta.ajustar_saldo(moneda, monto)
        mov = Movimiento(cuenta_id=cuenta.id, tipo="deposito", moneda=moneda, monto=monto,
                         descripcion=f"Depósito en {moneda}")
        self.repo.add(mov)
        self.repo.flush()
        self.db.commit()
        return to_movimiento(mov)

    def extraer(self, cuenta_id: int, moneda: str, monto: Decimal) -> MovimientoDTO:
        cuenta = obtener_cuenta(self.db, cuenta_id, bloquear=True)
        if monto > cuenta.saldo(moneda):
            raise BusinessError(
                f"Saldo insuficiente: querés extraer {fmt(monto, moneda)} y tenés {fmt(cuenta.saldo(moneda), moneda)}."
            )
        cuenta.ajustar_saldo(moneda, -monto)
        mov = Movimiento(cuenta_id=cuenta.id, tipo="extraccion", moneda=moneda, monto=monto,
                         descripcion=f"Extracción en {moneda}")
        self.repo.add(mov)
        self.repo.flush()
        self.db.commit()
        return to_movimiento(mov)

    def movimientos(self, cuenta_id: int) -> list[MovimientoDTO]:
        obtener_cuenta(self.db, cuenta_id)
        return [to_movimiento(m) for m in self.repo.movimientos(cuenta_id)]

    # ---------- HU10: cartera valorizada ----------
    def cartera(self, cuenta_id: int) -> dict:
        cuenta = obtener_cuenta(self.db, cuenta_id)
        tc = tipo_cambio_mep(self.db)
        items, por_moneda, por_tipo = [], {"ARS": Decimal("0"), "USD": Decimal("0")}, defaultdict(Decimal)
        for t in sorted(cuenta.tenencias, key=lambda x: x.activo.ticker):
            a = t.activo
            valor = q2(t.cantidad * a.precio_actual)
            costo = t.cantidad * t.precio_promedio
            rendimiento = q2((valor - costo) / costo * 100) if costo else Decimal("0")
            items.append({
                "activo_id": a.id, "ticker": a.ticker, "nombre": a.nombre, "tipo": a.tipo, "moneda": a.moneda,
                "nivel_riesgo": a.nivel_riesgo, "operable": a.activo,
                "cantidad": t.cantidad, "precio_promedio": t.precio_promedio, "precio_actual": a.precio_actual,
                "valor_actual": valor, "resultado": q2(valor - costo), "rendimiento_pct": rendimiento,
            })
            por_moneda[a.moneda] += valor
            # Para sumar pesos y dólares en la composición se pasan los USD a ARS al tipo de cambio MEP.
            # Sin tipo de cambio, los dólares quedan afuera (sumarlos como pesos daría porcentajes falsos)
            if a.moneda == "ARS":
                por_tipo[a.tipo] += valor
            elif tc:
                por_tipo[a.tipo] += valor * tc

        total_tipos = sum(por_tipo.values())
        composicion = [
            {"tipo": tipo, "valor_ars": q2(v), "porcentaje": q2(v / total_tipos * 100) if total_tipos else Decimal("0")}
            for tipo, v in sorted(por_tipo.items(), key=lambda kv: -kv[1])
        ]
        patrimonio = None
        if tc:
            patrimonio = q2(cuenta.saldo_ars + por_moneda["ARS"] + (cuenta.saldo_usd + por_moneda["USD"]) * tc)
        return to_json({
            "cuenta_id": cuenta.id, "numero_comitente": cuenta.numero_comitente,
            "tenencias": items,
            "total_valorizado": {m: q2(v) for m, v in por_moneda.items()},
            "saldos_disponibles": {"ARS": cuenta.saldo_ars, "USD": cuenta.saldo_usd},
            "composicion_por_tipo": composicion,
            "tipo_cambio_mep": tc,
            "composicion_sin_dolares": tc is None and por_moneda["USD"] > 0,
            "patrimonio_total_ars": patrimonio,
        })

    # ---------- HU12: ganancias realizadas por año ----------
    def ganancias_realizadas(self, cuenta_id: int) -> dict:
        obtener_cuenta(self.db, cuenta_id)
        por_anio: dict[int, dict] = {}
        for op in OperacionRepository(self.db).ventas_con_ganancia(cuenta_id):
            anio = a_utc(op.fecha).astimezone(TZ_AR).year
            fila = por_anio.setdefault(anio, {"anio": anio, "ARS": Decimal("0"), "USD": Decimal("0"), "ventas": 0})
            fila[op.activo.moneda] += op.ganancia_realizada
            fila["ventas"] += 1
        return to_json({"cuenta_id": cuenta_id, "por_anio": [por_anio[k] for k in sorted(por_anio, reverse=True)]})
