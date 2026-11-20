"""Columnas agregadas después de creada la base (create_all no modifica tablas existentes)."""
from sqlalchemy import inspect, text

COLUMNAS_INVERSOR = {
    "email_verificado": "BOOLEAN NOT NULL DEFAULT false",
    "codigo_hash": "VARCHAR(128)",
    "codigo_expira": "TIMESTAMP WITH TIME ZONE",
    "codigo_enviado": "TIMESTAMP WITH TIME ZONE",
    "codigo_intentos": "INTEGER NOT NULL DEFAULT 0",
}


def aplicar(engine) -> None:
    existentes = {c["name"] for c in inspect(engine).get_columns("inversores")}
    faltan = {k: v for k, v in COLUMNAS_INVERSOR.items() if k not in existentes}
    if not faltan:
        return
    with engine.begin() as c:
        for nombre, tipo in faltan.items():
            c.execute(text(f"ALTER TABLE inversores ADD COLUMN {nombre} {tipo}"))
        if "email_verificado" in faltan:
            # Los administradores ya existentes quedan confirmados; el resto confirma al ingresar
            c.execute(text("UPDATE inversores SET email_verificado = true WHERE es_admin"))
