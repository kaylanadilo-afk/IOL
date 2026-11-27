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
