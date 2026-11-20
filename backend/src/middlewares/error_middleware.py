from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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
