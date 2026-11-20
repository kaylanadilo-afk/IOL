"""Carga datos de ejemplo del broker usando las mismas reglas de negocio que la API.

    python -m src.db.seeders.seed            -> crea tablas y carga datos si la base está vacía
    python -m src.db.seeders.seed --reset    -> borra las tablas del broker y vuelve a cargar
"""
import os
import sys
from datetime import datetime, time, timedelta
from decimal import Decimal as D

from sqlalchemy import text

import src.db.models  # noqa: F401
from src.db.connection import Base, SessionLocal, engine
from src.db.models.inversor_model import Inversor
from src.repositories.broker_repository import ActivoRepository, InversorRepository
from src.services.activo_service import ActivoService, obtener_activo
from src.services.cuenta_service import CuentaService
from src.services.inversor_service import InversorService
from src.services.operacion_service import OperacionService
from src.utils import seguridad
from src.utils.mercado import TZ_AR

ACTIVOS = [
    # ticker, nombre, tipo, moneda, precio, riesgo
    ("GGAL", "Grupo Financiero Galicia", "accion", "ARS", "7480", 4),
    ("YPFD", "YPF", "accion", "ARS", "48600", 4),
    ("PAMP", "Pampa Energía", "accion", "ARS", "4165", 4),
    ("BMA", "Banco Macro", "accion", "ARS", "11250", 4),
    ("TXAR", "Ternium Argentina", "accion", "ARS", "1320", 5),
    ("ALUA", "Aluar", "accion", "ARS", "985", 5),
    ("CEPU", "Central Puerto", "accion", "ARS", "1690", 4),
    ("AAPL", "Apple (CEDEAR)", "cedear", "ARS", "18750", 3),
    ("MSFT", "Microsoft (CEDEAR)", "cedear", "ARS", "21300", 3),
    ("NVDA", "NVIDIA (CEDEAR)", "cedear", "ARS", "9850", 4),
    ("KO", "Coca-Cola (CEDEAR)", "cedear", "ARS", "17400", 2),
    ("MELI", "MercadoLibre (CEDEAR)", "cedear", "ARS", "23900", 4),
    ("SPY", "S&P 500 ETF (CEDEAR)", "cedear", "ARS", "42300", 2),
    ("AL30", "Bonar 2030 (pesos)", "bono", "ARS", "1245.5", 2),
    ("AL30D", "Bonar 2030 (dólar MEP)", "bono", "USD", "0.85", 2),
    ("GD30D", "Global 2030 (dólares)", "bono", "USD", "0.89", 2),
    ("AE38", "Bonar 2038", "bono", "ARS", "1080", 3),
]

PASSWORD_DEMO = "aula1234"  # contraseña inicial de los usuarios de ejemplo (se puede cambiar desde Perfil)
ADMIN = ("admin@aula.test", "Administración IOL", "30711111112", "agresivo")
INVERSORES = [
    ("alumno@aula.test", "Alumno Demo", "20111111112", "moderado"),
    ("lucia@aula.test", "Lucía Fernández", "27222222223", "agresivo"),
    ("martin@aula.test", "Martín Gómez", "20333333334", "conservador"),
]
TABLAS_BROKER = ("favoritos", "operaciones", "movimientos", "tenencias", "dividendos", "cierres_diarios",
                 "cotizaciones_intradia", "cuentas", "inversores", "activos")


def crear_admin(db) -> None:
    """Perfiles autorizados para la sección de Administración (activos, precios, dividendos).

    Además del admin de ejemplo, si el .env define ADMIN_EMAIL y ADMIN_PASSWORD se crea esa cuenta
    (así la contraseña real no queda en el repositorio).
    """
    repo, servicio = InversorRepository(db), InversorService(db)
    email, clave = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if email and clave:
        if not repo.find_by_email(email):
            servicio.crear(email, os.getenv("ADMIN_NOMBRE", "Administración"), os.getenv("ADMIN_CUIT", "30711111111"),
                           "agresivo", clave, es_admin=True)
        return
    if not repo.find_by_email(ADMIN[0]):
        e, n, c, p = ADMIN
        servicio.crear(e, n, c, p, PASSWORD_DEMO, es_admin=True)


def dia_habil(dias_atras: int, hora: int = 12) -> datetime:
    """Fecha `dias_atras` días antes de hoy, movida al viernes anterior si cae en fin de semana."""
    d = datetime.now(TZ_AR).date() - timedelta(days=dias_atras)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return datetime.combine(d, time(hora, 0), tzinfo=TZ_AR)


def cargar(db) -> None:
    activos, cuentas, ops = ActivoService(db), CuentaService(db), OperacionService(db)

    def precio(ticker: str, valor: str) -> None:
        activos.actualizar_precio(obtener_activo(db, ticker=ticker).id, D(valor))

    def op(cuenta_id: int, tipo: str, ticker: str, cantidad: int, cuando: datetime) -> None:
        (ops.comprar if tipo == "compra" else ops.vender)(cuenta_id, cantidad, cuando, ticker=ticker)

    for t, n, tipo, mon, p, r in ACTIVOS:
        activos.crear(t, n, tipo, mon, D(p), r)
    invs = [InversorService(db).crear(e, n, c, p, PASSWORD_DEMO) for e, n, c, p in INVERSORES]
    alumno, lucia, martin = (i.cuenta.id for i in invs)
    crear_admin(db)

    for c, ars, usd in ((alumno, "10000000", "5000"), (lucia, "25000000", "20000"), (martin, "3000000", "1000")):
        cuentas.depositar(c, "ARS", D(ars))
        cuentas.depositar(c, "USD", D(usd))

    # Historia del alumno: año pasado y este año, con precios que se mueven entre operaciones
    for t, v in (("GGAL", "5200"), ("AAPL", "14100"), ("KO", "13900")):
        precio(t, v)
    op(alumno, "compra", "GGAL", 200, dia_habil(400))
    op(alumno, "compra", "AAPL", 50, dia_habil(390))
    op(alumno, "compra", "KO", 40, dia_habil(380))
    precio("GGAL", "6100")
    op(alumno, "venta", "GGAL", 80, dia_habil(330))
    precio("KO", "13100")
    op(alumno, "venta", "KO", 40, dia_habil(320))
    precio("AAPL", "16900")
    op(alumno, "compra", "AAPL", 30, dia_habil(120))
    precio("GGAL", "6900")
    op(alumno, "venta", "GGAL", 40, dia_habil(60))
    op(alumno, "compra", "AL30", 1500, dia_habil(30))
    op(alumno, "compra", "SPY", 20, dia_habil(20))

    # Actividad reciente de otros inversores para el ranking de los últimos 7 días
    precio("YPFD", "47200"); precio("NVDA", "9400"); precio("MELI", "23100")  # noqa: E702
    op(lucia, "compra", "YPFD", 120, dia_habil(5))
    op(lucia, "compra", "NVDA", 300, dia_habil(4))
    op(lucia, "compra", "MELI", 80, dia_habil(3))
    op(lucia, "compra", "GGAL", 500, dia_habil(2))
    op(martin, "compra", "KO", 30, dia_habil(4))
    op(martin, "compra", "AL30", 900, dia_habil(2))
    op(alumno, "compra", "MSFT", 15, dia_habil(1))
    ops.dolar_mep(lucia, D("1500000"), dia_habil(1))
    ops.dolar_mep(alumno, D("300000"), dia_habil(1))

    # Precios "de hoy"
    for t, _, _, _, p, _ in ACTIVOS:
        precio(t, p)

    # Dividendo pagado por Coca-Cola a quienes la tienen hoy (Martín)
    activos.registrar_dividendo(obtener_activo(db, ticker="KO").id, D("45.5"), None)

    # Favoritos
    favs = [["GGAL", "AAPL", "AL30"], ["NVDA", "MELI", "GGAL", "YPFD"], ["KO", "AL30", "SPY", "GGAL"]]
    for inv, tickers in zip(invs, favs):
        for t in tickers:
            InversorService(db).agregar_favorito(inv.id, obtener_activo(db, ticker=t).id)

    # Un activo suspendido para mostrar HU8
    activos.actualizar_estado(obtener_activo(db, ticker="ALUA").id, False)


def main() -> None:
    if "--reset" in sys.argv:
        tablas = [Base.metadata.tables[t] for t in TABLAS_BROKER]
        Base.metadata.drop_all(engine, tables=tablas)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if ActivoRepository(db).list_por_ticker():
            try:
                db.execute(text("ALTER TABLE inversores ADD COLUMN IF NOT EXISTS es_admin BOOLEAN NOT NULL DEFAULT false"))
                db.execute(text("ALTER TABLE inversores ADD COLUMN IF NOT EXISTS password_hash VARCHAR(200)"))
                db.commit()
            except Exception:
                db.rollback()  # SQLite no soporta IF NOT EXISTS; ahí conviene --reset
            crear_admin(db)
            sin_clave = db.query(Inversor).filter(Inversor.password_hash.is_(None)).all()
            for inv in sin_clave:
                inv.password_hash = seguridad.hashear(PASSWORD_DEMO)
            db.commit()
            print(f"La base ya tenía datos: administrador listo ({os.getenv('ADMIN_EMAIL') or ADMIN[0]}) y {len(sin_clave)} usuarios sin "
                  f"contraseña quedaron con {PASSWORD_DEMO!r}. Usá --reset para recargar todo.")
            return
        cargar(db)
    print(f"Datos de ejemplo cargados. Ingresá con alumno@aula.test y la contraseña {PASSWORD_DEMO!r}")


if __name__ == "__main__":
    main()
