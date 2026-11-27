"""Límites de intentos en memoria (ventana deslizante), para frenar abusos sin infraestructura extra.

Viven en el proceso de la API: alcanzan para un solo servidor como el de este proyecto. Con varios procesos
habría que moverlos a algo compartido (Redis, la base).
"""
import math
import threading
import time
from collections import defaultdict, deque

from src.utils.errors import AppError


class DemasiadosIntentosError(AppError):
    status_code = 429
    message = "Demasiados intentos. Esperá un momento y probá de nuevo."


def _espera_texto(segundos: float) -> str:
    if segundos < 60:
        return f"{max(1, math.ceil(segundos))} segundos"
    minutos = math.ceil(segundos / 60)
    return "1 minuto" if minutos == 1 else f"{minutos} minutos"


class Limitador:
    """Permite `maximo` eventos por clave cada `ventana` segundos."""

    def __init__(self, maximo: int, ventana: float, mensaje: str):
        self.maximo, self.ventana, self.mensaje = maximo, ventana, mensaje
        self._eventos: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
        _todos.append(self)

    def _limpiar(self, clave: str, ahora: float) -> deque:
        cola = self._eventos[clave]
        while cola and ahora - cola[0] >= self.ventana:
            cola.popleft()
        return cola

    def espera(self, clave: str) -> float:
        """Segundos que faltan para poder volver a intentar (0 si se puede ya)."""
        with self._lock:
            ahora = time.monotonic()
            cola = self._limpiar(clave, ahora)
            return self.ventana - (ahora - cola[0]) if len(cola) >= self.maximo else 0.0

    def verificar(self, clave: str) -> None:
        """Corta con 429 si la clave ya agotó sus intentos."""
        falta = self.espera(clave)
        if falta > 0:
            raise DemasiadosIntentosError(f"{self.mensaje} Probá de nuevo en {_espera_texto(falta)}.")

    def registrar(self, clave: str) -> None:
        with self._lock:
            self._limpiar(clave, time.monotonic()).append(time.monotonic())
            # Para que la memoria no crezca sin fin con claves viejas
            if len(self._eventos) > 10_000:
                for k in [k for k, v in self._eventos.items() if not v][:5_000]:
                    del self._eventos[k]

    def consumir(self, clave: str) -> None:
        """Verifica y cuenta el intento en un solo paso."""
        self.verificar(clave)
        self.registrar(clave)

    def limpiar(self, clave: str) -> None:
        with self._lock:
            self._eventos.pop(clave, None)

    def reiniciar(self) -> None:
        with self._lock:
            self._eventos.clear()


_todos: list[Limitador] = []

# Contraseña: 5 errores en 15 minutos por cuenta bloquean el ingreso (y el cambio de contraseña) un rato
LOGIN = Limitador(5, 15 * 60, "Demasiados intentos fallidos para esta cuenta.")
CAMBIO_PASSWORD = Limitador(5, 15 * 60, "Demasiados intentos con la contraseña actual.")
# Código de verificación: 10 errores por hora por cuenta, aunque se pidan códigos nuevos
CODIGO = Limitador(10, 60 * 60, "Demasiados códigos incorrectos.")
REENVIO = Limitador(5, 60 * 60, "Ya te mandamos varios códigos.")
# Revisar correos del formulario de alta: 20 por minuto por IP (consulta servidores de terceros)
VALIDAR_EMAIL = Limitador(20, 60, "Demasiadas consultas.")
# Informe nuevo de la IA (saltando la caché): 1 cada 2 minutos por cuenta (cuota compartida de Groq)
INFORME_IA = Limitador(1, 120, "Ya pediste un informe nuevo hace poco.")


def reiniciar_todos() -> None:
    """Para los tests: cada prueba arranca sin intentos acumulados."""
    for limitador in _todos:
        limitador.reiniciar()
