-- =============================================================================
-- PROYECTO 6 — IOL (InvertirOnline)
-- Script de Creación de Base de Datos y Tablas para PostgreSQL / pgAdmin
-- =============================================================================

-- 1. CREACIÓN DE TIPOS ENUM PERSONALIZADOS
--------------------------------------------------------------------------------
CREATE TYPE perfil_riesgo_enum AS ENUM ('conservador', 'moderado', 'agresivo');
CREATE TYPE tipo_activo_enum AS ENUM ('accion', 'cedear', 'bono');
CREATE TYPE moneda_enum AS ENUM ('ARS', 'USD');
CREATE TYPE tipo_operacion_enum AS ENUM ('compra', 'venta');
CREATE TYPE estado_operacion_enum AS ENUM ('pendiente', 'completada', 'rechazada');
CREATE TYPE tipo_movimiento_enum AS ENUM ('deposito', 'extraccion', 'dividendo', 'compra', 'venta');

-- 2. TABLA INVERSOR (HU1, HU5)
--------------------------------------------------------------------------------
CREATE TABLE inversor (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    cuit VARCHAR(11) NOT NULL UNIQUE,
    perfil_riesgo perfil_riesgo_enum NOT NULL DEFAULT 'conservador',
    fecha_alta TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- CUIT debe ser exactamente de 11 dígitos numéricos
    CONSTRAINT chk_cuit_formato CHECK (cuit ~ '^[0-9]{11}$')
);

-- 3. TABLA CUENTA (HU1, HU3, HU10)
--------------------------------------------------------------------------------
CREATE TABLE cuenta (
    id BIGSERIAL PRIMARY KEY,
    inversor_id BIGINT NOT NULL UNIQUE,
    numero_comitente VARCHAR(50) NOT NULL UNIQUE,
    saldo_ars NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
    saldo_usd NUMERIC(18, 2) NOT NULL DEFAULT 0.00,

    CONSTRAINT fk_cuenta_inversor FOREIGN KEY (inversor_id) 
        REFERENCES inversor(id) ON DELETE RESTRICT ON UPDATE CASCADE,
        
    -- Los saldos en cuenta no pueden ser negativos
    CONSTRAINT chk_saldo_ars_no_negativo CHECK (saldo_ars >= 0),
    CONSTRAINT chk_saldo_usd_no_negativo CHECK (saldo_usd >= 0)
);

-- 4. TABLA ACTIVO (HU2, HU5, HU8, HU9)
--------------------------------------------------------------------------------
CREATE TABLE activo (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    tipo tipo_activo_enum NOT NULL,
    moneda moneda_enum NOT NULL,
    precio_actual NUMERIC(18, 4) NOT NULL,
    nivel_riesgo SMALLINT NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT chk_precio_actual_positivo CHECK (precio_actual > 0),
    CONSTRAINT chk_nivel_riesgo_rango CHECK (nivel_riesgo BETWEEN 1 AND 5)
);

-- 5. TABLA TENENCIA (Relación N a M entre Cuenta y Activo) (HU4, HU6, HU10)
--------------------------------------------------------------------------------
CREATE TABLE tenencia (
    cuenta_id BIGINT NOT NULL,
    activo_id BIGINT NOT NULL,
    cantidad NUMERIC(18, 6) NOT NULL DEFAULT 0,
    precio_promedio NUMERIC(18, 4) NOT NULL DEFAULT 0,

    PRIMARY KEY (cuenta_id, activo_id),
    
    CONSTRAINT fk_tenencia_cuenta FOREIGN KEY (cuenta_id) 
        REFERENCES cuenta(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_tenencia_activo FOREIGN KEY (activo_id) 
        REFERENCES activo(id) ON DELETE RESTRICT ON UPDATE CASCADE,
        
    CONSTRAINT chk_tenencia_cantidad CHECK (cantidad >= 0),
    CONSTRAINT chk_tenencia_precio_promedio CHECK (precio_promedio >= 0)
);

-- 6. TABLA FAVORITO (Relación N a M entre Inversor y Activo) (HU12)
--------------------------------------------------------------------------------
CREATE TABLE favorito (
    inversor_id BIGINT NOT NULL,
    activo_id BIGINT NOT NULL,
    fecha_agregado TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (inversor_id, activo_id),
    
    CONSTRAINT fk_favorito_inversor FOREIGN KEY (inversor_id) 
        REFERENCES inversor(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_favorito_activo FOREIGN KEY (activo_id) 
        REFERENCES activo(id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- 7. TABLA OPERACION (HU4, HU6, HU7, HU11, HU12)
--------------------------------------------------------------------------------
CREATE TABLE operacion (
    id BIGSERIAL PRIMARY KEY,
    cuenta_id BIGINT NOT NULL,
    activo_id BIGINT NOT NULL,
    tipo tipo_operacion_enum NOT NULL,
    cantidad NUMERIC(18, 6) NOT NULL,
    precio_unitario NUMERIC(18, 4) NOT NULL,
    comision NUMERIC(18, 2) NOT NULL,
    total NUMERIC(18, 2) NOT NULL,
    ganancia_realizada NUMERIC(18, 2) NULL, -- Guardado al vender (HU6)
    fecha TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado estado_operacion_enum NOT NULL DEFAULT 'completada',

    CONSTRAINT fk_operacion_cuenta FOREIGN KEY (cuenta_id) 
        REFERENCES cuenta(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_operacion_activo FOREIGN KEY (activo_id) 
        REFERENCES activo(id) ON DELETE RESTRICT ON UPDATE CASCADE,
        
    CONSTRAINT chk_operacion_cantidad CHECK (cantidad > 0),
    CONSTRAINT chk_operacion_precio CHECK (precio_unitario > 0),
    CONSTRAINT chk_operacion_comision CHECK (comision >= 0),
    CONSTRAINT chk_operacion_total CHECK (total > 0)
);

-- 8. TABLA MOVIMIENTO (HU3, HU9)
--------------------------------------------------------------------------------
CREATE TABLE movimiento (
    id BIGSERIAL PRIMARY KEY,
    cuenta_id BIGINT NOT NULL,
    tipo tipo_movimiento_enum NOT NULL,
    moneda moneda_enum NOT NULL,
    monto NUMERIC(18, 2) NOT NULL,
    fecha TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    descripcion TEXT,

    CONSTRAINT fk_movimiento_cuenta FOREIGN KEY (cuenta_id) 
        REFERENCES cuenta(id) ON DELETE RESTRICT ON UPDATE CASCADE,
        
    CONSTRAINT chk_movimiento_monto CHECK (monto > 0)
);

-- 9. TABLA DIVIDENDO (HU9)
--------------------------------------------------------------------------------
CREATE TABLE dividendo (
    id BIGSERIAL PRIMARY KEY,
    activo_id BIGINT NOT NULL,
    monto_por_unidad NUMERIC(18, 4) NOT NULL,
    fecha_pago TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_dividendo_activo FOREIGN KEY (activo_id) 
        REFERENCES activo(id) ON DELETE RESTRICT ON UPDATE CASCADE,
        
    CONSTRAINT chk_monto_por_unidad CHECK (monto_por_unidad > 0)
);

-- =============================================================================
-- ÍNDICES RECOMENDADOS PARA OPTIMIZAR LAS BUSQUEDAS Y REPORTES
-- =============================================================================

-- HU2: GET /activos filtra por tipo y moneda
CREATE INDEX idx_activo_tipo_moneda ON activo(tipo, moneda);

-- HU11: Historial de operaciones por cuenta, rango de fechas, tipo y activo
CREATE INDEX idx_operacion_cuenta_fecha ON operacion(cuenta_id, fecha DESC);
CREATE INDEX idx_operacion_activo_id ON operacion(activo_id);

-- HU12: Ranking de activos más operados en los últimos 7 días
CREATE INDEX idx_operacion_fecha_activo ON operacion(fecha, activo_id);

-- HU12: Ranking de favoritos
CREATE INDEX idx_favorito_activo ON favorito(activo_id);

-- HU11/HU12: Búsquedas por movimiento y dividendos por fecha
CREATE INDEX idx_movimiento_cuenta_fecha ON movimiento(cuenta_id, fecha DESC);
CREATE INDEX idx_dividendo_activo_fecha ON dividendo(activo_id, fecha_pago DESC);