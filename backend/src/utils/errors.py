class AppError(Exception):
    status_code: int = 500
    message: str = "Internal error"

    def __init__(self, message: str | None = None, status_code: int | None = None, campo: str | None = None):
        if message:
            self.message = message
        if status_code:
            self.status_code = status_code
        # Campo del formulario al que se refiere el error (el front lo marca en rojo)
        self.campo = campo
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    message = "Resource not found"


class UnauthorizedError(AppError):
    status_code = 401
    message = "Unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    message = "Forbidden"


class EmailNoVerificadoError(ForbiddenError):
    """La cuenta existe y la contraseña es correcta, pero falta confirmar el correo."""

    message = "Confirmá tu correo para ingresar. Te mandamos un código."


class ConflictError(AppError):
    status_code = 409
    message = "Conflict"


class BusinessError(AppError):
    """Una regla de negocio no se cumple (saldo insuficiente, mercado cerrado...). 422 por defecto."""

    status_code = 422
    message = "Regla de negocio no cumplida"


def no_encontrado(que: str) -> NotFoundError:
    return NotFoundError(f"{que} no encontrado")
