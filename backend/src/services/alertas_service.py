"""Alertas de precio: se configuran por activo y se revisan en el backend con cada actualización de precios.

- El porcentaje se mide contra el precio que tenía el activo al crear (o reconfigurar) la alerta.
- Se revisan cada vez que llegan precios reales de data912 (cada PRECIOS_INTERVALO segundos) y cuando un
  administrador cambia un precio a mano. No dependen de que la página esté abierta.
- Cada cruce del objetivo avisa una sola vez: el disparo se marca con un UPDATE condicional, así dos
  revisiones simultáneas no pueden mandar dos correos por la misma alerta.
- Son avisos informativos: nunca compran ni venden.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.db.models.activo_model import Activo
from src.db.models.alerta_model import Alerta, Notificacion
from src.db.models.inversor_model import Inversor
from src.utils import correo
from src.utils.errors import BusinessError, no_encontrado
from src.utils.mercado import q2, q4

log = logging.getLogger("uvicorn.error")
MAX_ALERTAS = 50


def dinero(v: Decimal, moneda: str) -> str:
    """$ 1.234,56 (formato argentino)."""
    texto = f"{q2(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'US$' if moneda == 'USD' else '$'} {texto}"


def porcentaje(v: Decimal) -> str:
    return f"{q2(v):.2f}".replace(".", ",").rstrip("0").rstrip(",") + " %"


def objetivo(tipo: str, valor: Decimal, referencia: Decimal) -> tuple[Decimal, str]:
    """Precio objetivo y dirección ("sube" o "baja") de una alerta."""
    if tipo == "sube_pct":
        return q4(referencia * (1 + valor / 100)), "sube"
    if tipo == "baja_pct":
        if valor >= 100:
            raise BusinessError("Una baja tiene que ser menor al 100 %.", campo="valor")
        return q4(referencia * (1 - valor / 100)), "baja"
    if valor == referencia:
        raise BusinessError("El activo ya está en ese precio: elegí otro objetivo.", campo="valor")
    return q4(valor), "sube" if valor > referencia else "baja"


def describir(al: Alerta) -> str:
    m = al.activo.moneda
    if al.tipo == "sube_pct":
        return f"Sube {porcentaje(al.valor)} (a {dinero(al.precio_objetivo, m)})"
    if al.tipo == "baja_pct":
        return f"Baja {porcentaje(al.valor)} (a {dinero(al.precio_objetivo, m)})"
    return f"{'Sube' if al.direccion == 'sube' else 'Baja'} a {dinero(al.precio_objetivo, m)}"


def to_alerta(al: Alerta) -> dict:
    a = al.activo
    distancia = (al.precio_objetivo / a.precio_actual - 1) * 100 if a.precio_actual else None
    return {
        "id": al.id, "activo_id": a.id, "ticker": a.ticker, "nombre": a.nombre, "moneda": a.moneda,
        "tipo": al.tipo, "valor": al.valor, "direccion": al.direccion, "condicion": describir(al),
        "precio_referencia": al.precio_referencia, "precio_objetivo": al.precio_objetivo,
        "precio_actual": a.precio_actual, "distancia_pct": q2(distancia) if distancia is not None else None,
        "estado": al.estado, "recurrente": al.recurrente, "aviso_email": al.aviso_email, "aviso_app": al.aviso_app,
        "veces_disparada": al.veces_disparada, "creada": al.creada, "ultima_vez": al.ultima_vez,
    }


def to_notificacion(n: Notificacion) -> dict:
    return {"id": n.id, "alerta_id": n.alerta_id, "activo_id": n.activo_id, "titulo": n.titulo, "mensaje": n.mensaje,
            "precio": n.precio, "variacion_pct": n.variacion_pct, "email_enviado": n.email_enviado,
            "leida": n.leida, "fecha": n.fecha}


class AlertasService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- Configuración ----------
    def _mia(self, alerta_id: int, inversor_id: int) -> Alerta:
        al = self.db.get(Alerta, alerta_id)
        if not al or al.inversor_id != inversor_id:
            raise no_encontrado("Alerta")
        return al

    def _armar(self, al: Alerta, activo: Activo) -> None:
        """Toma el precio actual como referencia y recalcula el objetivo."""
        if not activo.precio_actual or activo.precio_actual <= 0:
            raise BusinessError("Ese activo no tiene precio para tomar como referencia.")
        al.precio_referencia = activo.precio_actual
        al.precio_objetivo, al.direccion = objetivo(al.tipo, Decimal(al.valor), activo.precio_actual)
        al.cumplida = False

    def listar(self, inversor_id: int) -> list[dict]:
        alertas = self.db.scalars(select(Alerta).where(Alerta.inversor_id == inversor_id).order_by(Alerta.creada.desc()))
        return [to_alerta(a) for a in alertas]

    def crear(self, inversor_id: int, datos: dict) -> dict:
        activo = self.db.get(Activo, datos["activo_id"])
        if not activo:
            raise no_encontrado("Activo")
        cantidad = len(list(self.db.scalars(select(Alerta.id).where(Alerta.inversor_id == inversor_id,
                                                                     Alerta.estado != "ejecutada"))))
        if cantidad >= MAX_ALERTAS:
            raise BusinessError(f"Podés tener hasta {MAX_ALERTAS} alertas abiertas. Borrá alguna para crear otra.")
        al = Alerta(inversor_id=inversor_id, activo_id=activo.id, tipo=datos["tipo"], valor=datos["valor"],
                    recurrente=datos.get("recurrente", False), aviso_email=datos.get("aviso_email", True),
                    aviso_app=datos.get("aviso_app", True), estado="activa", veces_disparada=0)
        al.activo = activo
        self._armar(al, activo)
        self.db.add(al)
        self.db.commit()
        return to_alerta(al)

    def actualizar(self, alerta_id: int, inversor_id: int, cambios: dict) -> dict:
        al = self._mia(alerta_id, inversor_id)
        rearmar = any(k in cambios and cambios[k] != getattr(al, k) for k in ("tipo", "valor"))
        for k, v in cambios.items():
            setattr(al, k, v)
        if not (al.aviso_email or al.aviso_app):
            raise BusinessError("Elegí al menos una forma de aviso.", campo="aviso_email")
        if rearmar or al.estado == "ejecutada":
            self._armar(al, al.activo)
            if al.estado == "ejecutada":  # una pausada sigue pausada hasta que la reactiven
                al.estado = "activa"
        self.db.commit()
        return to_alerta(al)

    def cambiar_estado(self, alerta_id: int, inversor_id: int, estado: str) -> dict:
        al = self._mia(alerta_id, inversor_id)
        if estado == "activa" and al.estado == "ejecutada":
            self._armar(al, al.activo)  # una alerta ya cumplida se vuelve a armar desde el precio de hoy
        al.estado = estado
        self.db.commit()
        return to_alerta(al)

    def borrar(self, alerta_id: int, inversor_id: int) -> None:
        self.db.delete(self._mia(alerta_id, inversor_id))
        self.db.commit()

    # ---------- Avisos dentro de la app (también son el historial de alertas cumplidas) ----------
    def notificaciones(self, inversor_id: int, limite: int = 50) -> dict:
        q = select(Notificacion).where(Notificacion.inversor_id == inversor_id)
        filas = list(self.db.scalars(q.order_by(Notificacion.fecha.desc(), Notificacion.id.desc()).limit(limite)))
        no_leidas = len(list(self.db.scalars(select(Notificacion.id).where(
            Notificacion.inversor_id == inversor_id, Notificacion.leida.is_(False)))))
        return {"no_leidas": no_leidas, "items": [to_notificacion(n) for n in filas]}

    def marcar_leidas(self, inversor_id: int, notificacion_id: int | None = None) -> None:
        q = update(Notificacion).where(Notificacion.inversor_id == inversor_id)
        if notificacion_id is not None:
            q = q.where(Notificacion.id == notificacion_id)
        self.db.execute(q.values(leida=True))
        self.db.commit()

    # ---------- Revisión automática ----------
    def evaluar(self, activo_ids: list[int] | None = None, ahora: datetime | None = None) -> int:
        """Revisa las alertas activas contra el precio actual. Devuelve cuántas se dispararon."""
        ahora = ahora or datetime.now(timezone.utc)
        q = select(Alerta).where(Alerta.estado == "activa")
        if activo_ids:
            q = q.where(Alerta.activo_id.in_(activo_ids))
        disparadas = 0
        for al in list(self.db.scalars(q)):
            precio = al.activo.precio_actual
            if not precio or precio <= 0:
                continue
            cumple = precio >= al.precio_objetivo if al.direccion == "sube" else precio <= al.precio_objetivo
            if not cumple:
                if al.cumplida:  # salió de la condición: una recurrente queda lista para el próximo cruce
                    al.cumplida = False
                continue
            if al.cumplida:
                continue
            # Toma la alerta de forma atómica: si otra revisión ya la disparó, esta no hace nada
            tomada = self.db.execute(
                update(Alerta).where(Alerta.id == al.id, Alerta.estado == "activa", Alerta.cumplida.is_(False))
                .values(cumplida=True)
            ).rowcount
            if tomada != 1:
                continue
            self.db.refresh(al)
            self._disparar(al, precio, ahora)
            disparadas += 1
        self.db.commit()
        return disparadas

    def _disparar(self, al: Alerta, precio: Decimal, ahora: datetime) -> None:
        a = al.activo
        referencia = al.precio_referencia  # antes de rearmar una recurrente
        variacion = q2((precio / referencia - 1) * 100)
        if al.tipo == "baja_pct":
            titulo = f"Alerta de precio: {a.ticker}"
            mensaje = (f"{a.ticker} bajó un {porcentaje(abs(variacion))} respecto del precio que tenía cuando configuraste "
                       f"esta alerta. Es posible que sea un buen momento para evaluar una oportunidad de compra.")
        elif al.tipo == "sube_pct":
            titulo = "Alerta de precio: objetivo alcanzado"
            mensaje = (f"{a.ticker} subió un {porcentaje(variacion)} desde que configuraste tu alerta. "
                       f"Recordá revisar tu inversión y evaluar si es momento de vender.")
        else:
            titulo = f"Alerta de precio: {a.ticker}"
            mensaje = f"{a.ticker} llegó a {dinero(precio, a.moneda)} (tu objetivo era {dinero(al.precio_objetivo, a.moneda)})."

        inversor = self.db.get(Inversor, al.inversor_id)
        enviar = al.aviso_email and inversor is not None and inversor.email_verificado
        self.db.add(Notificacion(inversor_id=al.inversor_id, alerta_id=al.id, activo_id=a.id, titulo=titulo,
                                 mensaje=mensaje, precio=precio, variacion_pct=variacion, email_enviado=enviar,
                                 leida=not al.aviso_app, fecha=ahora))
        condicion = describir(al)
        al.veces_disparada += 1
        al.ultima_vez = ahora
        if not al.recurrente:
            al.estado = "ejecutada"
        elif al.tipo != "precio":
            # Recurrente por porcentaje: el próximo aviso se mide desde el precio de este disparo
            al.precio_referencia = precio
            al.precio_objetivo, al.direccion = objetivo(al.tipo, Decimal(al.valor), precio)
            al.cumplida = False
        if enviar:
            asunto, texto, html = correo.mail_alerta(
                nombre=inversor.nombre.split(" ")[0], titulo=titulo, mensaje=mensaje, ticker=a.ticker, nombre_activo=a.nombre,
                precio=dinero(precio, a.moneda), referencia=dinero(referencia, a.moneda),
                variacion=("+" if variacion > 0 else "") + porcentaje(variacion), condicion=condicion)
            correo.despachar(inversor.email, asunto, texto, html)
        log.info("Alerta %s disparada: %s a %s", al.id, a.ticker, precio)


def evaluar_con_sesion(activo_ids: list[int] | None = None) -> int:
    """Para la tarea de fondo: abre su propia sesión."""
    from src.db.connection import SessionLocal

    with SessionLocal() as db:
        try:
            return AlertasService(db).evaluar(activo_ids)
        except Exception:
            db.rollback()
            log.exception("No se pudieron revisar las alertas")
            return 0
