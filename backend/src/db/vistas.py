"""Vistas para mirar la base desde pgAdmin con texto en lugar de números.

Las tablas guardan las relaciones con IDs enteros (cuenta_id, activo_id, inversor_id...) porque así la base
puede validar que existan, unirlas rápido y no repetir datos. Para leerlas cómodo están estas vistas: muestran
lo mismo pero con el nombre del inversor, el número de comitente y el ticker. En pgAdmin aparecen en
Schemas → public → Views (clic derecho → View/Edit Data). Son solo de lectura: no guardan nada aparte, siempre
muestran lo que hay en las tablas en ese momento. Nunca muestran contraseñas ni códigos.

Se crean (o actualizan) solas cada vez que arranca la API.
"""
from sqlalchemy import text

VISTAS: dict[str, str] = {
    "ver_inversores": """
        SELECT i.id, i.nombre, i.email, i.cuit, i.perfil_riesgo,
               CASE WHEN i.es_admin THEN 'Sí' ELSE 'No' END AS es_admin,
               CASE WHEN i.email_verificado THEN 'Sí' ELSE 'No' END AS email_confirmado,
               c.numero_comitente AS comitente, i.fecha_alta
        FROM inversores i
        LEFT JOIN cuentas c ON c.inversor_id = i.id""",
    "ver_cuentas": """
        SELECT c.numero_comitente AS comitente, i.nombre AS inversor, i.email,
               c.saldo_ars, c.saldo_usd
        FROM cuentas c
        JOIN inversores i ON i.id = c.inversor_id""",
    "ver_tenencias": """
        SELECT c.numero_comitente AS comitente, i.nombre AS inversor, a.ticker, a.nombre AS activo,
               a.tipo, a.moneda, t.cantidad, t.precio_promedio, a.precio_actual,
               t.cantidad * a.precio_actual AS valor_actual
        FROM tenencias t
        JOIN cuentas c ON c.id = t.cuenta_id
        JOIN inversores i ON i.id = c.inversor_id
        JOIN activos a ON a.id = t.activo_id""",
    "ver_operaciones": """
        SELECT o.id, o.fecha, c.numero_comitente AS comitente, i.nombre AS inversor, o.tipo,
               a.ticker, a.nombre AS activo, o.cantidad, o.precio_unitario, o.comision, o.total,
               o.ganancia_realizada, o.estado
        FROM operaciones o
        JOIN cuentas c ON c.id = o.cuenta_id
        JOIN inversores i ON i.id = c.inversor_id
        JOIN activos a ON a.id = o.activo_id""",
    "ver_movimientos": """
        SELECT m.id, m.fecha, c.numero_comitente AS comitente, i.nombre AS inversor, m.tipo,
               m.moneda, m.monto, m.descripcion
        FROM movimientos m
        JOIN cuentas c ON c.id = m.cuenta_id
        JOIN inversores i ON i.id = c.inversor_id""",
    "ver_dividendos": """
        SELECT d.id, d.fecha_pago, a.ticker, a.nombre AS activo, a.moneda, d.monto_por_unidad
        FROM dividendos d
        JOIN activos a ON a.id = d.activo_id""",
    "ver_favoritos": """
        SELECT i.nombre AS inversor, i.email, a.ticker, a.nombre AS activo, f.fecha_agregado
        FROM favoritos f
        JOIN inversores i ON i.id = f.inversor_id
        JOIN activos a ON a.id = f.activo_id""",
    "ver_alertas": """
        SELECT al.id, i.nombre AS inversor, a.ticker, a.nombre AS activo, al.tipo, al.valor,
               al.precio_referencia, al.precio_objetivo, a.precio_actual, al.estado,
               CASE WHEN al.recurrente THEN 'Sí' ELSE 'No' END AS recurrente,
               CASE WHEN al.aviso_email THEN 'Sí' ELSE 'No' END AS por_correo,
               CASE WHEN al.aviso_app THEN 'Sí' ELSE 'No' END AS en_la_app,
               al.veces_disparada, al.creada, al.ultima_vez
        FROM alertas al
        JOIN inversores i ON i.id = al.inversor_id
        JOIN activos a ON a.id = al.activo_id""",
    "ver_notificaciones": """
        SELECT n.id, n.fecha, i.nombre AS inversor, a.ticker, n.titulo, n.mensaje, n.precio,
               n.variacion_pct,
               CASE WHEN n.email_enviado THEN 'Sí' ELSE 'No' END AS correo_enviado,
               CASE WHEN n.leida THEN 'Sí' ELSE 'No' END AS leida
        FROM notificaciones n
        JOIN inversores i ON i.id = n.inversor_id
        LEFT JOIN activos a ON a.id = n.activo_id""",
    "ver_cierres_diarios": """
        SELECT a.ticker, a.nombre AS activo, cd.fecha, cd.apertura, cd.maximo, cd.minimo, cd.cierre, cd.volumen
        FROM cierres_diarios cd
        JOIN activos a ON a.id = cd.activo_id""",
}


def crear(conexion) -> None:
    """Borra y vuelve a crear cada vista (así toman los cambios de columnas)."""
    for nombre, consulta in VISTAS.items():
        conexion.execute(text(f"DROP VIEW IF EXISTS {nombre}"))
        conexion.execute(text(f"CREATE VIEW {nombre} AS {consulta.strip()}"))


def sql() -> str:
    """Las vistas como script SQL (para tables.sql)."""
    return "\n".join(f"\n-- {n}\nCREATE OR REPLACE VIEW {n} AS\n    {q.strip()};" for n, q in VISTAS.items())
