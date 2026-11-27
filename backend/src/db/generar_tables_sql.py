"""Regenera src/db/tables.sql a partir de los modelos de SQLAlchemy (PostgreSQL).

    python -m src.db.generar_tables_sql

Así el script para pgAdmin coincide siempre con lo que la API crea de verdad (antes se escribía a mano y
había quedado desactualizado: tablas en singular, otros estados, sin alertas ni historial de precios).
"""
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")  # no se conecta a nada: solo traduce los modelos a SQL
os.environ.setdefault("JWT_SECRET", "no-se-usa")

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

import src.db.models  # noqa: E402,F401  registra todos los modelos
from src.db import vistas  # noqa: E402
from src.db.connection import Base  # noqa: E402

# Las tablas de la plantilla de la cátedra (users, pasajeros, conductores) no son parte del broker
PLANTILLA = {"users", "pasajeros", "conductores"}
DESTINO = Path(__file__).with_name("tables.sql")


def generar() -> str:
    dialecto = postgresql.dialect()
    partes = [
        "-- =============================================================================",
        "-- Zeno Investments (IOL) - tablas de la base de datos para PostgreSQL / pgAdmin",
        "-- Generado desde los modelos con: python -m src.db.generar_tables_sql (no editar a mano)",
        "-- La API las crea sola al arrancar; este script sirve para verlas o crearlas desde pgAdmin.",
        "-- =============================================================================",
    ]
    for tabla in Base.metadata.sorted_tables:
        if tabla.name in PLANTILLA:
            continue
        partes.append(f"\n-- {tabla.name}")
        partes.append(str(CreateTable(tabla).compile(dialect=dialecto)).strip() + ";")
        for indice in sorted(tabla.indexes, key=lambda i: i.name or ""):
            partes.append(str(CreateIndex(indice).compile(dialect=dialecto)).strip() + ";")
    partes += [
        "\n-- =============================================================================",
        "-- Vistas para leer la base con nombres y tickers en lugar de IDs (solo lectura)",
        "-- =============================================================================",
        vistas.sql(),
    ]
    return "\n".join(partes) + "\n"


if __name__ == "__main__":
    DESTINO.write_text(generar(), encoding="utf-8")
    print(f"Escrito {DESTINO}")
