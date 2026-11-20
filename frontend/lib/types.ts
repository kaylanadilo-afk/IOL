// Tipos de las respuestas de la API del broker (backend/src/dtos y reportes de los services).

export type Perfil = "conservador" | "moderado" | "agresivo";
export type TipoActivo = "accion" | "cedear" | "bono";
export type Moneda = "ARS" | "USD";
export type TipoOperacion = "compra" | "venta";
export type TipoMovimiento = "deposito" | "extraccion" | "dividendo";

export interface Cuenta {
  id: number;
  inversor_id: number;
  numero_comitente: number;
  saldo_ars: number;
  saldo_usd: number;
}

export interface Inversor {
  id: number;
  email: string;
  nombre: string;
  cuit: string;
  perfil_riesgo: Perfil;
  fecha_alta: string;
  es_admin: boolean;
  /** false hasta que confirma el correo con el código que se le manda. */
  email_verificado: boolean;
  cuenta: Cuenta | null;
}

export interface Sesion {
  token: string;
  inversor: Inversor;
}

export interface Activo {
  id: number;
  ticker: string;
  nombre: string;
  tipo: TipoActivo;
  moneda: Moneda;
  precio_actual: number;
  nivel_riesgo: number;
  activo: boolean;
  variacion_pct: number | null;
  precio_actualizado: string | null;
}

export interface EstadoPrecios {
  modo: "reales" | "manuales";
  fuente: string;
  intervalo_segundos: number | null;
  ultima_sincronizacion: string | null;
  actualizados: number;
  sin_dato: string[];
  error: string | null;
}

export interface ResultadoHistorial {
  cierres: number;
  puntos_intradia: number;
  activos: number;
  errores: string[];
}

export interface EstadoHistorial {
  ultima_carga: string | null;
  resultado: ResultadoHistorial | null;
  error: string | null;
}

export interface EstadoMercado {
  abierto: boolean;
  en_horario: boolean;
  modo_demo: boolean;
  hora_argentina: string;
  horario: string;
  precios: EstadoPrecios;
  historial: EstadoHistorial;
}

export interface CotizacionDolar {
  casa: string;
  nombre: string;
  compra: number | null;
  venta: number;
  fecha_actualizacion: string | null;
}

export interface Dolares {
  cotizaciones: CotizacionDolar[];
  mep_broker_al30: number | null;
}

export type PorMoneda = Record<Moneda, number>;

export interface Tenencia {
  activo_id: number;
  ticker: string;
  nombre: string;
  tipo: TipoActivo;
  moneda: Moneda;
  nivel_riesgo: number;
  operable: boolean;
  cantidad: number;
  precio_promedio: number;
  precio_actual: number;
  valor_actual: number;
  resultado: number;
  rendimiento_pct: number;
}

export interface Cartera {
  cuenta_id: number;
  numero_comitente: number;
  tenencias: Tenencia[];
  total_valorizado: PorMoneda;
  saldos_disponibles: PorMoneda;
  composicion_por_tipo: { tipo: TipoActivo; valor_ars: number; porcentaje: number }[];
  tipo_cambio_mep: number | null;
  patrimonio_total_ars: number | null;
}

export interface MasOperado {
  activo_id: number;
  ticker: string;
  nombre: string;
  tipo: TipoActivo;
  moneda: Moneda;
  operaciones: number;
  cantidad_operada: number;
  volumen: number;
  volumen_ars: number;
}

export interface MasFavorito {
  activo_id: number;
  ticker: string;
  nombre: string;
  tipo: TipoActivo;
  moneda: Moneda;
  favoritos: number;
}

export interface Sparkline {
  activo_id: number;
  cierres: number[];
}

export interface Evolucion {
  cuenta_id: number;
  dias: number;
  puntos: { fecha: string; valor_ars: number }[];
  variacion_pct: number | null;
}

export interface CierreDiario {
  fecha: string;
  apertura: number;
  maximo: number;
  minimo: number;
  cierre: number;
  volumen: number | null;
}

export interface HistorialDiario {
  activo_id: number;
  ticker: string;
  moneda: Moneda;
  dias: number;
  cierres: CierreDiario[];
  variacion_pct: number | null;
  maximo: number | null;
  minimo: number | null;
}

export interface Intradia {
  activo_id: number;
  ticker: string;
  moneda: Moneda;
  fecha: string | null;
  dias_disponibles: string[];
  puntos: { t: string; precio: number }[];
  cierre_anterior: number | null;
  cierre: number | null;
  apertura: number | null;
  maximo: number | null;
  minimo: number | null;
  ultimo: number | null;
  variacion_pct: number | null;
}

export interface Operacion {
  id: number;
  cuenta_id: number;
  activo_id: number;
  ticker: string;
  moneda: Moneda;
  tipo: TipoOperacion;
  cantidad: number;
  precio_unitario: number;
  comision: number;
  total: number;
  fecha: string;
  estado: string;
  ganancia_realizada: number | null;
}

export interface HistorialOperaciones {
  operaciones: Operacion[];
  cantidad: number;
  total_comisiones: PorMoneda;
}

export interface FiltroOperaciones {
  desde: string;
  hasta: string;
  tipo: "" | TipoOperacion;
  ticker: string;
}

export interface Ganancias {
  cuenta_id: number;
  por_anio: { anio: number; ARS: number; USD: number; ventas: number }[];
}

export interface Movimiento {
  id: number;
  cuenta_id: number;
  tipo: TipoMovimiento;
  moneda: Moneda;
  monto: number;
  fecha: string;
  descripcion: string;
}

export interface MepResultado {
  tipo_cambio: number;
  cantidad_nominales: number;
  pesos_debitados: number;
  dolares_acreditados: number;
  compra: Operacion;
  venta: Operacion;
}

export interface DividendoResultado {
  id: number;
  activo_id: number;
  ticker: string;
  moneda: Moneda;
  monto_por_unidad: number;
  fecha_pago: string;
  cuentas_acreditadas: number;
  total_pagado: number;
}

export interface InversorCrear {
  nombre: string;
  email: string;
  cuit: string;
  perfil_riesgo: Perfil;
  password: string;
}

export interface ActivoCrear {
  ticker: string;
  nombre: string;
  tipo: TipoActivo;
  moneda: Moneda;
  precio_actual: number;
  nivel_riesgo: number;
}
