"""Tests de la API.

Por defecto usan SQLite en memoria (rápido, sin instalar nada). Para correrlos contra
PostgreSQL:  TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/iol_test pytest
"""
import os

# La config exige estas variables; los tests usan SQLite en memoria
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test")
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.utils import mercado as sv
import src.db.models  # noqa: F401
from src.db.connection import Base, get_db
from src.app import app
from src.utils.mercado import get_ahora

URL = os.getenv("TEST_DATABASE_URL", "sqlite://")

# Viernes 13/11/2026 a las 12:00 en Argentina: mercado abierto
EN_HORARIO = datetime(2026, 11, 13, 12, 0, tzinfo=sv.TZ_AR)


class Reloj:
    def __init__(self):
        self.ahora = EN_HORARIO

    def __call__(self):
        return self.ahora


@pytest.fixture()
def reloj():
    return Reloj()


@pytest.fixture()
def client(reloj, monkeypatch):
    monkeypatch.delenv("MERCADO_SIEMPRE_ABIERTO", raising=False)
    kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if URL.startswith("sqlite") else {}
    engine = create_engine(URL, **kwargs)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _db():
        db = Session()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_ahora] = reloj
    yield TestClient(app, base_url="http://testserver/api")
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


# ---------- helpers ----------
_cuit = iter(range(20000000001, 20999999999))
PASSWORD = "clave-segura"


def nuevo_inversor(client, perfil="agresivo", email=None):
    n = next(_cuit)
    r = client.post("/inversores", json={
        "email": email or f"inv{n}@test.com", "nombre": "Test", "cuit": str(n), "perfil_riesgo": perfil,
        "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()


def nuevo_activo(client, ticker, tipo="accion", moneda="ARS", precio=100, riesgo=3):
    r = client.post("/activos", json={"ticker": ticker, "nombre": ticker, "tipo": tipo, "moneda": moneda,
                                      "precio_actual": precio, "nivel_riesgo": riesgo})
    assert r.status_code == 201, r.text
    return r.json()


def depositar(client, cuenta_id, monto, moneda="ARS"):
    r = client.post(f"/cuentas/{cuenta_id}/depositos", json={"moneda": moneda, "monto": monto})
    assert r.status_code == 201, r.text
