"""Agente de inversiones (Zeno AI): informe del día y chat, según el perfil y el mercado."""
from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.services import agente_service

router = APIRouter(prefix="/agente", tags=["Agente de inversiones"])


def _token(authorization: str | None) -> str:
    return (authorization or "").removeprefix("Bearer ").strip()


@router.get("/estado", summary="Si el agente está configurado y qué modelo usa")
def estado():
    return agente_service.estado()


@router.get("/informe", summary="Informe del día con recomendaciones según tu perfil y el mercado")
def informe(actualizar: bool = False, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    return agente_service.recomendacion(db, _token(authorization), actualizar)


class Mensaje(BaseModel):
    role: str
    content: str


class ChatSchema(BaseModel):
    mensajes: list[Mensaje]


@router.post("/chat", summary="Conversar con el agente (respuesta en streaming, Server-Sent Events)")
def chat(payload: ChatSchema, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    eventos = agente_service.chat(db, _token(authorization), [m.model_dump() for m in payload.mensajes])
    return StreamingResponse(eventos, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})
