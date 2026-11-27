"""Tests de la API.

Por defecto usan SQLite en memoria (rápido, sin instalar nada). Para correrlos contra
PostgreSQL:  TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost/iol_test pytest
"""
import os

# La config exige estas variables; los tests usan SQLite en memoria
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test")
os.environ["VALIDAR_EMAIL_DNS"] = "0"  # sin consultas a internet
os.environ["VERIFICAR_EMAIL"] = "0"  # las cuentas de prueba quedan confirmadas
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
from src.services.inversor_service import InversorService
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


@pytest.fixture(autouse=True)
def sin_limites_previos():
    from src.utils import limites
    limites.reiniciar_todos()


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
    c = ClienteZeno(app, base_url="http://testserver/api")
    # Un administrador para los endpoints de administración (precios, activos, dividendos)
    db = Session()
    InversorService(db).crear("admin@test.com", "Admin Prueba", "30711111111", "agresivo", PASSWORD, es_admin=True)
    db.close()
    c.admin = {"Authorization": "Bearer " + c.post("/auth/ingresar", json={"email": "admin@test.com", "password": PASSWORD}).json()["token"]}
    yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


# ---------- cliente con sesión ----------
class ClienteZeno(TestClient):
    """TestClient que manda la sesión del inversor "actual" (el último creado con nuevo_inversor, o el que se elija
    con client.como(inv)). Un header Authorization explícito tiene prioridad, y client.como(None) prueba sin sesión."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.sesion: dict | None = None
        self.admin: dict = {}

    def como(self, inversor: dict | None) -> None:
        self.sesion = inversor["headers"] if inversor else None

    def request(self, method, url, **kw):
        headers = dict(kw.pop("headers", None) or {})
        if self.sesion and not any(k.lower() == "authorization" for k in headers):
            headers.update(self.sesion)
        return super().request(method, url, headers=headers, **kw)


# ---------- helpers ----------
def _cuits_validos():
    """CUITs con dígito verificador correcto, distintos para cada inversor de prueba."""
    from src.utils.validaciones import digito_verificador_cuit
    for base in range(2000000000, 2099999999):
        d = digito_verificador_cuit(str(base))
        if d is not None:
            yield f"{base}{d}"


_cuit = _cuits_validos()
PASSWORD = "clave-segura"


def nuevo_inversor(client, perfil="agresivo", email=None):
    n = next(_cuit)
    r = client.post("/inversores", json={
        "email": email or f"inv{n}@test.com", "nombre": "Test Prueba", "cuit": n, "perfil_riesgo": perfil,
        "password": PASSWORD})
    assert r.status_code == 201, r.text
    inv = r.json()
    token = client.post("/auth/ingresar", json={"email": inv["email"], "password": PASSWORD}).json()["token"]
    inv["headers"] = {"Authorization": f"Bearer {token}"}
    client.como(inv)  # los pedidos siguientes van con la sesión de este inversor
    return inv


def nuevo_activo(client, ticker, tipo="accion", moneda="ARS", precio=100, riesgo=3):
    r = client.post("/activos", json={"ticker": ticker, "nombre": ticker, "tipo": tipo, "moneda": moneda,
                                      "precio_actual": precio, "nivel_riesgo": riesgo}, headers=client.admin)
    assert r.status_code == 201, r.text
    return r.json()


def depositar(client, cuenta_id, monto, moneda="ARS"):
    r = client.post(f"/cuentas/{cuenta_id}/depositos", json={"moneda": moneda, "monto": monto})
    assert r.status_code == 201, r.text
