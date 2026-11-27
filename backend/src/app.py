import asyncio
import contextlib
from contextlib import asynccontextmanager

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError

import src.db.models  # noqa: F401  registra todos los modelos en Base.metadata
from src.config.env import settings
from src.db import migraciones
from src.db.connection import Base, engine
from src.middlewares.error_middleware import (app_error_handler, data_error_handler, integrity_error_handler,
                                              validation_error_handler)
from src.routers import (activos_router, agente_router, alertas_router, auth_router, conductores_router, cuentas_router, inversores_router,
                         mercado_router, panel_router, pasajero_router, registros_router, user_router)
from src.services import precios_service
from src.utils.autorizacion import solo_admin
from src.utils.errors import AppError


log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # crea las tablas que falten
    migraciones.aplicar(engine)  # agrega las columnas nuevas a tablas que ya existían
    tarea = asyncio.create_task(precios_service.bucle_precios()) if precios_service.activado() else None
    yield
    if tarea:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea


app = FastAPI(
    title="IOL - InvertirOnline",
    description="Broker de bolsa: cuentas comitentes, activos, operaciones, MEP, dividendos y cartera.",
    lifespan=lifespan,
)

@app.middleware("http")
async def errores_inesperados(request: Request, call_next):
    """Un error no previsto responde JSON 500. Al estar registrado antes que CORS, la respuesta lleva sus
    headers y el front muestra el mensaje en vez de un "error de CORS"."""
    try:
        return await call_next(request)
    except Exception:
        log.exception("Error no previsto en %s %s", request.method, request.url.path)
        mensaje = "Ocurrió un error inesperado. Probá de nuevo en un momento."
        return JSONResponse(status_code=500, content={"error": "ErrorInterno", "message": mensaje, "detail": mensaje})


app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(DataError, data_error_handler)

app.include_router(agente_router.router, prefix="/api")
# Módulos de ejemplo de la plantilla: quedan disponibles solo para administradores
app.include_router(user_router.router, prefix="/api", dependencies=[Depends(solo_admin)])
app.include_router(auth_router.router, prefix="/api")
app.include_router(pasajero_router.router, prefix="/api", dependencies=[Depends(solo_admin)])
app.include_router(conductores_router.router, prefix="/api", dependencies=[Depends(solo_admin)])
# Broker
app.include_router(mercado_router.router, prefix="/api")
app.include_router(inversores_router.router, prefix="/api")
app.include_router(activos_router.router, prefix="/api")
app.include_router(activos_router.dividendos_router, prefix="/api")
app.include_router(cuentas_router.router, prefix="/api")
# Alta, edición y baja de cada tabla y panel de inversiones (lo que trae el backend InitialStructure)
for r in registros_router.ROUTERS:
    app.include_router(r, prefix="/api")
app.include_router(panel_router.router, prefix="/api")
app.include_router(alertas_router.router, prefix="/api")
app.include_router(alertas_router.notificaciones, prefix="/api")


@app.get("/health", tags=["Estado"], summary="Revisa que la API y la base de datos respondan")
def health():
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error", "detail": "La base de datos no responde."})
    return {"status": "ok"}


# TODO: registrar product_router cuando se implemente
# app.include_router(product_router.router, prefix="/api")
