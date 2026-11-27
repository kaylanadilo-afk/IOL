"""Cambios en tablas que ya existían (create_all crea tablas nuevas, pero no modifica las existentes).

Cada paso revisa primero si ya está aplicado, así que se puede correr en cada arranque de la API.
"""
from sqlalchemy import inspect, text

from src.db import vistas

COLUMNAS_INVERSOR = {
    # Bases creadas antes de la sesión con contraseña y la sección de administración
    "es_admin": "BOOLEAN NOT NULL DEFAULT false",
    "password_hash": "VARCHAR(200)",
    "email_verificado": "BOOLEAN NOT NULL DEFAULT false",
    "codigo_hash": "VARCHAR(128)",
    "codigo_expira": "TIMESTAMP WITH TIME ZONE",
    "codigo_enviado": "TIMESTAMP WITH TIME ZONE",
    "codigo_intentos": "INTEGER NOT NULL DEFAULT 0",
    "pwd_nueva_hash": "VARCHAR(200)",
    "pwd_codigo_hash": "VARCHAR(128)",
    "pwd_codigo_expira": "TIMESTAMP WITH TIME ZONE",
    "pwd_intentos": "INTEGER NOT NULL DEFAULT 0",
}

# Bases creadas antes de los precios reales
COLUMNAS_ACTIVO = {
    "variacion_pct": "NUMERIC(9, 2)",
    "precio_actualizado": "TIMESTAMP WITH TIME ZONE",
}

# Del script "PROYECTO 6" (tables.sql): restricciones e índices que nuestra base no tenía
RESTRICCIONES = {
    "operaciones": {
        "ck_operacion_precio": "precio_unitario > 0",
        "ck_operacion_comision": "comision >= 0",
        "ck_operacion_total": "total > 0",
        "ck_operacion_estado": "estado IN ('ejecutada', 'pendiente', 'rechazada')",
    },
    "tenencias": {"ck_tenencia_precio_promedio": "precio_promedio >= 0"},
}
INDICES = {
    "idx_activo_tipo_moneda": "activos (tipo, moneda)",
    "idx_operacion_cuenta_fecha": "operaciones (cuenta_id, fecha DESC)",
    "idx_operacion_fecha_activo": "operaciones (fecha, activo_id)",
    "idx_favorito_activo": "favoritos (activo_id)",
    "idx_movimiento_cuenta_fecha": "movimientos (cuenta_id, fecha DESC)",
    "idx_dividendo_activo_fecha": "dividendos (activo_id, fecha_pago DESC)",
}


def aplicar(engine) -> None:
    insp = inspect(engine)
    with engine.begin() as c:
        # Inversores: confirmación del correo
        existentes = {col["name"] for col in insp.get_columns("inversores")}
        faltan = {k: v for k, v in COLUMNAS_INVERSOR.items() if k not in existentes}
        for nombre, tipo in faltan.items():
            c.execute(text(f"ALTER TABLE inversores ADD COLUMN {nombre} {tipo}"))
        if "email_verificado" in faltan:
            # Los administradores ya existentes quedan confirmados; el resto confirma al ingresar
            c.execute(text("UPDATE inversores SET email_verificado = true WHERE es_admin"))

        actuales = {col["name"] for col in insp.get_columns("activos")}
        for nombre, tipo in COLUMNAS_ACTIVO.items():
            if nombre not in actuales:
                c.execute(text(f"ALTER TABLE activos ADD COLUMN {nombre} {tipo}"))

        # Favoritos: cuándo se agregó cada uno (los anteriores quedan con la fecha de hoy).
        # SQLite no acepta DEFAULT CURRENT_TIMESTAMP al agregar una columna: se agrega y se completa aparte
        if "fecha_agregado" not in {col["name"] for col in insp.get_columns("favoritos")}:
            if engine.dialect.name == "postgresql":
                c.execute(text("ALTER TABLE favoritos ADD COLUMN fecha_agregado TIMESTAMP WITH TIME ZONE "
                               "NOT NULL DEFAULT CURRENT_TIMESTAMP"))
            else:
                c.execute(text("ALTER TABLE favoritos ADD COLUMN fecha_agregado TIMESTAMP"))
                c.execute(text("UPDATE favoritos SET fecha_agregado = CURRENT_TIMESTAMP"))

        # Restricciones CHECK (SQLite no permite agregarlas a una tabla existente: ahí ya las crea create_all)
        if engine.dialect.name == "postgresql":
            for tabla, checks in RESTRICCIONES.items():
                actuales = {ck["name"] for ck in insp.get_check_constraints(tabla)}
                for nombre, condicion in checks.items():
                    if nombre not in actuales:
                        c.execute(text(f"ALTER TABLE {tabla} ADD CONSTRAINT {nombre} CHECK ({condicion})"))

        for nombre, definicion in INDICES.items():
            c.execute(text(f"CREATE INDEX IF NOT EXISTS {nombre} ON {definicion}"))

        # Vistas para leer la base con nombres y tickers en lugar de IDs (ver src/db/vistas.py)
        vistas.crear(c)
