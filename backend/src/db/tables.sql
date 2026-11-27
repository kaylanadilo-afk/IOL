-- =============================================================================
-- Zeno Investments (IOL) - tablas de la base de datos para PostgreSQL / pgAdmin
-- Generado desde los modelos con: python -m src.db.generar_tables_sql (no editar a mano)
-- La API las crea sola al arrancar; este script sirve para verlas o crearlas desde pgAdmin.
-- =============================================================================

-- activos
CREATE TABLE activos (
	id SERIAL NOT NULL, 
	ticker VARCHAR(12) NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	tipo VARCHAR(10) NOT NULL, 
	moneda VARCHAR(3) NOT NULL, 
	precio_actual NUMERIC(18, 4) NOT NULL, 
	nivel_riesgo INTEGER NOT NULL, 
	activo BOOLEAN NOT NULL, 
	variacion_pct NUMERIC(9, 2), 
	precio_actualizado TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_activo_tipo CHECK (tipo IN ('accion', 'cedear', 'bono')), 
	CONSTRAINT ck_activo_moneda CHECK (moneda IN ('ARS', 'USD')), 
	CONSTRAINT ck_activo_precio CHECK (precio_actual > 0), 
	CONSTRAINT ck_activo_riesgo CHECK (nivel_riesgo BETWEEN 1 AND 5), 
	UNIQUE (ticker)
);
CREATE INDEX idx_activo_tipo_moneda ON activos (tipo, moneda);

-- inversores
CREATE TABLE inversores (
	id SERIAL NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	cuit VARCHAR(11) NOT NULL, 
	perfil_riesgo VARCHAR(12) NOT NULL, 
	fecha_alta TIMESTAMP WITH TIME ZONE NOT NULL, 
	es_admin BOOLEAN DEFAULT 'false' NOT NULL, 
	password_hash VARCHAR(200), 
	email_verificado BOOLEAN DEFAULT 'false' NOT NULL, 
	codigo_hash VARCHAR(128), 
	codigo_expira TIMESTAMP WITH TIME ZONE, 
	codigo_enviado TIMESTAMP WITH TIME ZONE, 
	codigo_intentos INTEGER DEFAULT '0' NOT NULL, 
	pwd_nueva_hash VARCHAR(200), 
	pwd_codigo_hash VARCHAR(128), 
	pwd_codigo_expira TIMESTAMP WITH TIME ZONE, 
	pwd_intentos INTEGER DEFAULT '0' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_inversor_perfil CHECK (perfil_riesgo IN ('conservador', 'moderado', 'agresivo')), 
	CONSTRAINT ck_inversor_cuit CHECK (length(cuit) = 11), 
	UNIQUE (email), 
	UNIQUE (cuit)
);

-- alertas
CREATE TABLE alertas (
	id SERIAL NOT NULL, 
	inversor_id INTEGER NOT NULL, 
	activo_id INTEGER NOT NULL, 
	tipo VARCHAR(10) NOT NULL, 
	valor NUMERIC(18, 4) NOT NULL, 
	direccion VARCHAR(4) NOT NULL, 
	precio_referencia NUMERIC(18, 4) NOT NULL, 
	precio_objetivo NUMERIC(18, 4) NOT NULL, 
	estado VARCHAR(10) NOT NULL, 
	recurrente BOOLEAN NOT NULL, 
	aviso_email BOOLEAN NOT NULL, 
	aviso_app BOOLEAN NOT NULL, 
	cumplida BOOLEAN NOT NULL, 
	veces_disparada INTEGER NOT NULL, 
	creada TIMESTAMP WITH TIME ZONE NOT NULL, 
	ultima_vez TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_alerta_tipo CHECK (tipo IN ('sube_pct', 'baja_pct', 'precio')), 
	CONSTRAINT ck_alerta_estado CHECK (estado IN ('activa', 'pausada', 'ejecutada')), 
	CONSTRAINT ck_alerta_direccion CHECK (direccion IN ('sube', 'baja')), 
	CONSTRAINT ck_alerta_valor CHECK (valor > 0), 
	CONSTRAINT ck_alerta_precios CHECK (precio_referencia > 0 AND precio_objetivo > 0), 
	FOREIGN KEY(inversor_id) REFERENCES inversores (id) ON DELETE CASCADE, 
	FOREIGN KEY(activo_id) REFERENCES activos (id) ON DELETE CASCADE
);
CREATE INDEX idx_alerta_estado_activo ON alertas (estado, activo_id);
CREATE INDEX ix_alertas_inversor_id ON alertas (inversor_id);

-- cierres_diarios
CREATE TABLE cierres_diarios (
	activo_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	apertura NUMERIC(18, 4) NOT NULL, 
	maximo NUMERIC(18, 4) NOT NULL, 
	minimo NUMERIC(18, 4) NOT NULL, 
	cierre NUMERIC(18, 4) NOT NULL, 
	volumen NUMERIC(20, 2), 
	PRIMARY KEY (activo_id, fecha), 
	CONSTRAINT ck_cierre_positivo CHECK (cierre > 0), 
	FOREIGN KEY(activo_id) REFERENCES activos (id) ON DELETE CASCADE
);

-- cotizaciones_intradia
CREATE TABLE cotizaciones_intradia (
	activo_id INTEGER NOT NULL, 
	fecha_hora TIMESTAMP WITH TIME ZONE NOT NULL, 
	precio NUMERIC(18, 4) NOT NULL, 
	PRIMARY KEY (activo_id, fecha_hora), 
	FOREIGN KEY(activo_id) REFERENCES activos (id) ON DELETE CASCADE
);

-- cuentas
CREATE TABLE cuentas (
	id SERIAL NOT NULL, 
	inversor_id INTEGER NOT NULL, 
	numero_comitente INTEGER NOT NULL, 
	saldo_ars NUMERIC(18, 2) NOT NULL, 
	saldo_usd NUMERIC(18, 2) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_cuenta_saldo_ars CHECK (saldo_ars >= 0), 
	CONSTRAINT ck_cuenta_saldo_usd CHECK (saldo_usd >= 0), 
	UNIQUE (inversor_id), 
	FOREIGN KEY(inversor_id) REFERENCES inversores (id), 
	UNIQUE (numero_comitente)
);

-- dividendos
CREATE TABLE dividendos (
	id SERIAL NOT NULL, 
	activo_id INTEGER NOT NULL, 
	monto_por_unidad NUMERIC(18, 4) NOT NULL, 
	fecha_pago DATE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_dividendo_monto CHECK (monto_por_unidad > 0), 
	FOREIGN KEY(activo_id) REFERENCES activos (id)
);
CREATE INDEX idx_dividendo_activo_fecha ON dividendos (activo_id, fecha_pago);
CREATE INDEX ix_dividendos_activo_id ON dividendos (activo_id);

-- favoritos
CREATE TABLE favoritos (
	inversor_id INTEGER NOT NULL, 
	activo_id INTEGER NOT NULL, 
	fecha_agregado TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (inversor_id, activo_id), 
	FOREIGN KEY(inversor_id) REFERENCES inversores (id) ON DELETE CASCADE, 
	FOREIGN KEY(activo_id) REFERENCES activos (id) ON DELETE CASCADE
);
CREATE INDEX idx_favorito_activo ON favoritos (activo_id);

-- movimientos
CREATE TABLE movimientos (
	id SERIAL NOT NULL, 
	cuenta_id INTEGER NOT NULL, 
	tipo VARCHAR(10) NOT NULL, 
	moneda VARCHAR(3) NOT NULL, 
	monto NUMERIC(18, 2) NOT NULL, 
	fecha TIMESTAMP WITH TIME ZONE NOT NULL, 
	descripcion VARCHAR(200) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_movimiento_tipo CHECK (tipo IN ('deposito', 'extraccion', 'dividendo')), 
	CONSTRAINT ck_movimiento_moneda CHECK (moneda IN ('ARS', 'USD')), 
	CONSTRAINT ck_movimiento_monto CHECK (monto > 0), 
	FOREIGN KEY(cuenta_id) REFERENCES cuentas (id)
);
CREATE INDEX idx_movimiento_cuenta_fecha ON movimientos (cuenta_id, fecha);
CREATE INDEX ix_movimientos_cuenta_id ON movimientos (cuenta_id);

-- notificaciones
CREATE TABLE notificaciones (
	id SERIAL NOT NULL, 
	inversor_id INTEGER NOT NULL, 
	alerta_id INTEGER, 
	activo_id INTEGER, 
	titulo VARCHAR(120) NOT NULL, 
	mensaje VARCHAR(400) NOT NULL, 
	precio NUMERIC(18, 4), 
	variacion_pct NUMERIC(9, 2), 
	email_enviado BOOLEAN NOT NULL, 
	leida BOOLEAN NOT NULL, 
	fecha TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(inversor_id) REFERENCES inversores (id) ON DELETE CASCADE, 
	FOREIGN KEY(alerta_id) REFERENCES alertas (id) ON DELETE SET NULL, 
	FOREIGN KEY(activo_id) REFERENCES activos (id) ON DELETE SET NULL
);
CREATE INDEX idx_notificacion_inversor_fecha ON notificaciones (inversor_id, fecha);

-- operaciones
CREATE TABLE operaciones (
	id SERIAL NOT NULL, 
	cuenta_id INTEGER NOT NULL, 
	activo_id INTEGER NOT NULL, 
	tipo VARCHAR(6) NOT NULL, 
	cantidad INTEGER NOT NULL, 
	precio_unitario NUMERIC(18, 4) NOT NULL, 
	comision NUMERIC(18, 2) NOT NULL, 
	total NUMERIC(18, 2) NOT NULL, 
	fecha TIMESTAMP WITH TIME ZONE NOT NULL, 
	estado VARCHAR(10) NOT NULL, 
	ganancia_realizada NUMERIC(18, 2), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_operacion_tipo CHECK (tipo IN ('compra', 'venta')), 
	CONSTRAINT ck_operacion_cantidad CHECK (cantidad > 0), 
	CONSTRAINT ck_operacion_precio CHECK (precio_unitario > 0), 
	CONSTRAINT ck_operacion_comision CHECK (comision >= 0), 
	CONSTRAINT ck_operacion_total CHECK (total > 0), 
	CONSTRAINT ck_operacion_estado CHECK (estado IN ('ejecutada', 'pendiente', 'rechazada')), 
	FOREIGN KEY(cuenta_id) REFERENCES cuentas (id), 
	FOREIGN KEY(activo_id) REFERENCES activos (id)
);
CREATE INDEX idx_operacion_cuenta_fecha ON operaciones (cuenta_id, fecha);
CREATE INDEX idx_operacion_fecha_activo ON operaciones (fecha, activo_id);
CREATE INDEX ix_operaciones_activo_id ON operaciones (activo_id);
CREATE INDEX ix_operaciones_cuenta_id ON operaciones (cuenta_id);
CREATE INDEX ix_operaciones_fecha ON operaciones (fecha);

-- tenencias
CREATE TABLE tenencias (
	cuenta_id INTEGER NOT NULL, 
	activo_id INTEGER NOT NULL, 
	cantidad INTEGER NOT NULL, 
	precio_promedio NUMERIC(18, 4) NOT NULL, 
	PRIMARY KEY (cuenta_id, activo_id), 
	CONSTRAINT ck_tenencia_cantidad CHECK (cantidad > 0), 
	CONSTRAINT ck_tenencia_precio_promedio CHECK (precio_promedio >= 0), 
	FOREIGN KEY(cuenta_id) REFERENCES cuentas (id), 
	FOREIGN KEY(activo_id) REFERENCES activos (id)
);

-- =============================================================================
-- Vistas para leer la base con nombres y tickers en lugar de IDs (solo lectura)
-- =============================================================================

-- ver_inversores
CREATE OR REPLACE VIEW ver_inversores AS
    SELECT i.id, i.nombre, i.email, i.cuit, i.perfil_riesgo,
               CASE WHEN i.es_admin THEN 'Sí' ELSE 'No' END AS es_admin,
               CASE WHEN i.email_verificado THEN 'Sí' ELSE 'No' END AS email_confirmado,
               c.numero_comitente AS comitente, i.fecha_alta
        FROM inversores i
        LEFT JOIN cuentas c ON c.inversor_id = i.id;

-- ver_cuentas
CREATE OR REPLACE VIEW ver_cuentas AS
    SELECT c.numero_comitente AS comitente, i.nombre AS inversor, i.email,
               c.saldo_ars, c.saldo_usd
        FROM cuentas c
        JOIN inversores i ON i.id = c.inversor_id;

-- ver_tenencias
CREATE OR REPLACE VIEW ver_tenencias AS
    SELECT c.numero_comitente AS comitente, i.nombre AS inversor, a.ticker, a.nombre AS activo,
               a.tipo, a.moneda, t.cantidad, t.precio_promedio, a.precio_actual,
               t.cantidad * a.precio_actual AS valor_actual
        FROM tenencias t
        JOIN cuentas c ON c.id = t.cuenta_id
        JOIN inversores i ON i.id = c.inversor_id
        JOIN activos a ON a.id = t.activo_id;

-- ver_operaciones
CREATE OR REPLACE VIEW ver_operaciones AS
    SELECT o.id, o.fecha, c.numero_comitente AS comitente, i.nombre AS inversor, o.tipo,
               a.ticker, a.nombre AS activo, o.cantidad, o.precio_unitario, o.comision, o.total,
               o.ganancia_realizada, o.estado
        FROM operaciones o
        JOIN cuentas c ON c.id = o.cuenta_id
        JOIN inversores i ON i.id = c.inversor_id
        JOIN activos a ON a.id = o.activo_id;

-- ver_movimientos
CREATE OR REPLACE VIEW ver_movimientos AS
    SELECT m.id, m.fecha, c.numero_comitente AS comitente, i.nombre AS inversor, m.tipo,
               m.moneda, m.monto, m.descripcion
        FROM movimientos m
        JOIN cuentas c ON c.id = m.cuenta_id
        JOIN inversores i ON i.id = c.inversor_id;

-- ver_dividendos
CREATE OR REPLACE VIEW ver_dividendos AS
    SELECT d.id, d.fecha_pago, a.ticker, a.nombre AS activo, a.moneda, d.monto_por_unidad
        FROM dividendos d
        JOIN activos a ON a.id = d.activo_id;

-- ver_favoritos
CREATE OR REPLACE VIEW ver_favoritos AS
    SELECT i.nombre AS inversor, i.email, a.ticker, a.nombre AS activo, f.fecha_agregado
        FROM favoritos f
        JOIN inversores i ON i.id = f.inversor_id
        JOIN activos a ON a.id = f.activo_id;

-- ver_alertas
CREATE OR REPLACE VIEW ver_alertas AS
    SELECT al.id, i.nombre AS inversor, a.ticker, a.nombre AS activo, al.tipo, al.valor,
               al.precio_referencia, al.precio_objetivo, a.precio_actual, al.estado,
               CASE WHEN al.recurrente THEN 'Sí' ELSE 'No' END AS recurrente,
               CASE WHEN al.aviso_email THEN 'Sí' ELSE 'No' END AS por_correo,
               CASE WHEN al.aviso_app THEN 'Sí' ELSE 'No' END AS en_la_app,
               al.veces_disparada, al.creada, al.ultima_vez
        FROM alertas al
        JOIN inversores i ON i.id = al.inversor_id
        JOIN activos a ON a.id = al.activo_id;

-- ver_notificaciones
CREATE OR REPLACE VIEW ver_notificaciones AS
    SELECT n.id, n.fecha, i.nombre AS inversor, a.ticker, n.titulo, n.mensaje, n.precio,
               n.variacion_pct,
               CASE WHEN n.email_enviado THEN 'Sí' ELSE 'No' END AS correo_enviado,
               CASE WHEN n.leida THEN 'Sí' ELSE 'No' END AS leida
        FROM notificaciones n
        JOIN inversores i ON i.id = n.inversor_id
        LEFT JOIN activos a ON a.id = n.activo_id;

-- ver_cierres_diarios
CREATE OR REPLACE VIEW ver_cierres_diarios AS
    SELECT a.ticker, a.nombre AS activo, cd.fecha, cd.apertura, cd.maximo, cd.minimo, cd.cierre, cd.volumen
        FROM cierres_diarios cd
        JOIN activos a ON a.id = cd.activo_id;
