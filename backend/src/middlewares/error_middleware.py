from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from sqlalchemy.exc import DataError, IntegrityError

from src.utils.errors import AppError


async def app_error_handler(request: Request, exc: AppError):
    # "detail" es lo que lee el front (mismo formato que los errores propios de FastAPI)
    content = {"error": exc.__class__.__name__, "message": exc.message, "detail": exc.message}
    if exc.campo:
        content["campos"] = {exc.campo: exc.message}
    return JSONResponse(status_code=exc.status_code, content=content)


async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Errores de validación en una sola línea legible: 'campo: motivo; campo: motivo'."""
    mensajes, campos = [], {}
    for e in exc.errors():
        campo = ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path"))
        msg = str(e["msg"]).removeprefix("Value error, ")
        mensajes.append(f"{campo}: {msg}" if campo else msg)
        if campo:
            campos.setdefault(campo, msg)
    # "campos" permite mostrar cada error debajo de su campo
    return JSONResponse(status_code=422, content={"error": "ValidationError", "detail": "; ".join(mensajes), "campos": campos})


# Códigos de PostgreSQL de las restricciones de la base (los mismos que maneja el backend InitialStructure)
_INTEGRIDAD = {
    "23502": (422, "Falta un dato obligatorio."),
    "23505": (409, "Ya existe un registro con ese identificador o valor único."),
    "23503": (409, "La operación entra en conflicto con un registro relacionado."),
    "23514": (422, "Los datos no cumplen una regla de validación de la base de datos."),
}


async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Si una restricción de la base frena un cambio, se responde con un error claro en vez de un 500."""
    codigo = getattr(exc.orig, "pgcode", None) or getattr(getattr(exc.orig, "diag", None), "sqlstate", None)
    if codigo is None:  # SQLite no tiene códigos: se reconoce por el texto del error
        texto = str(exc.orig).upper()
        codigo = ("23505" if "UNIQUE" in texto else "23502" if "NOT NULL" in texto
                  else "23514" if "CHECK" in texto else "23503" if "FOREIGN KEY" in texto else None)
    estado, mensaje = _INTEGRIDAD.get(codigo, (409, "No se pudo guardar el cambio en la base de datos."))
    return JSONResponse(status_code=estado, content={"error": "IntegrityError", "message": mensaje, "detail": mensaje})


async def data_error_handler(request: Request, exc: DataError):
    """Un número que no entra en la columna (desborde) u otro dato inválido para la base."""
    mensaje = "Algún valor es demasiado grande o tiene un formato que la base no acepta."
    return JSONResponse(status_code=422, content={"error": "DataError", "message": mensaje, "detail": mensaje})
