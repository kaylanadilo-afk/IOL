// Cliente de la API del broker. Todas las rutas van a /api/* y next.config.ts las reenvía al backend.
import type {
  Activo, ActivoCrear, Cartera, Cuenta, DividendoResultado, Dolares, EstadoHistorial, EstadoMercado,
  EstadoPrecios, Evolucion, FiltroOperaciones, Ganancias, HistorialDiario, HistorialOperaciones, Intradia,
  Inversor, InversorCrear, MasFavorito, MasOperado, MepResultado, Moneda, Movimiento, Operacion, Perfil, Sesion,
  Sparkline, TipoActivo,
} from "./types";

const BASE = "/api";
const SESSION_KEY = "iolAula_token"; // token firmado que devuelve /auth/ingresar

let token: string | null = null;

export function leerToken(): string | null {
  try {
    token = localStorage.getItem(SESSION_KEY);
  } catch {
    /* sin almacenamiento */
  }
  return token;
}

export function guardarToken(t: string | null): void {
  token = t;
  try {
    if (t) localStorage.setItem(SESSION_KEY, t);
    else localStorage.removeItem(SESSION_KEY);
  } catch {
    /* sin almacenamiento */
  }
}

export class ApiError extends Error {
  /** Errores por campo del formulario (por ejemplo { email: "Ya existe una cuenta con este correo" }). */
  constructor(message: string, public status: number, public campos: Record<string, string> = {}) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError("No se pudo conectar con la API. ¿Está corriendo el backend?", 0);
  }
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const d = data as { detail?: unknown; message?: unknown; campos?: Record<string, string> } | null;
    const msg = d?.detail ?? d?.message;
    const texto = msg == null ? (res.status >= 500 ? "No se pudo conectar con la API. ¿Está corriendo el backend?" : `Error ${res.status}`)
      : typeof msg === "string" ? msg : JSON.stringify(msg);
    throw new ApiError(texto, res.status, d?.campos ?? {});
  }
  return data as T;
}

function qs(params: Record<string, string | number | null | undefined>): string {
  const p = Object.entries(params)
    .filter(([, v]) => v !== "" && v != null)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return p.length ? `?${p.join("&")}` : "";
}

export const api = {
  // Sesión e inversores
  ingresar: (email: string, password: string) => request<Sesion>("POST", "/auth/ingresar", { email, password }),
  yo: () => request<Inversor>("GET", "/auth/yo"),
  crearInversor: (datos: InversorCrear) => request<Inversor>("POST", "/inversores", datos),
  validarEmail: (email: string) => request<{ valido: boolean; email: string; mensaje: string | null }>("POST", "/inversores/validar-email", { email }),
  inversor: (id: number) => request<Inversor>("GET", `/inversores/${id}`),
  cambiarPerfil: (id: number, perfil_riesgo: Perfil) => request<Inversor>("PATCH", `/inversores/${id}/perfil`, { perfil_riesgo }),
  cambiarPassword: (id: number, actual: string, nueva: string) =>
    request<{ ok: boolean; token: string }>("POST", `/inversores/${id}/password`, { actual, nueva }),
  favoritos: (id: number) => request<Activo[]>("GET", `/inversores/${id}/favoritos`),
  marcarFavorito: (id: number, activoId: number) => request<Activo[]>("POST", `/inversores/${id}/favoritos/${activoId}`),
  quitarFavorito: (id: number, activoId: number) => request<Activo[]>("DELETE", `/inversores/${id}/favoritos/${activoId}`),

  // Mercado
  mercado: () => request<EstadoMercado>("GET", "/mercado/estado"),
  dolares: () => request<Dolares>("GET", "/mercado/dolares"),
  sincronizar: () => request<EstadoPrecios>("POST", "/mercado/sincronizar"),
  cargarHistorial: () => request<EstadoHistorial>("POST", "/mercado/historial"),

  // Activos
  activos: (filtro: { tipo?: TipoActivo | ""; moneda?: Moneda | "" } = {}) => request<Activo[]>("GET", `/activos${qs(filtro)}`),
  activo: (id: number) => request<Activo>("GET", `/activos/${id}`),
  crearActivo: (datos: ActivoCrear) => request<Activo>("POST", "/activos", datos),
  cambiarPrecio: (id: number, precio: number) => request<Activo>("PATCH", `/activos/${id}/precio`, { precio }),
  cambiarEstado: (id: number, activo: boolean) => request<Activo>("PATCH", `/activos/${id}/estado`, { activo }),
  sparklines: (dias = 30) => request<Sparkline[]>("GET", `/activos/sparklines?dias=${dias}`),
  masOperados: () => request<MasOperado[]>("GET", "/activos/mas-operados"),
  masFavoritos: () => request<MasFavorito[]>("GET", "/activos/mas-favoritos"),
  historial: (id: number, dias: number | string) => request<HistorialDiario>("GET", `/activos/${id}/historial?dias=${dias}`),
  intradia: (id: number, fecha?: string) => request<Intradia>("GET", `/activos/${id}/intradia${qs({ fecha })}`),
  pagarDividendo: (datos: { activo_id: number; monto_por_unidad: number; fecha_pago?: string }) =>
    request<DividendoResultado>("POST", "/dividendos", datos),

  // Cuentas y operaciones
  cuenta: (id: number) => request<Cuenta>("GET", `/cuentas/${id}`),
  cartera: (id: number) => request<Cartera>("GET", `/cuentas/${id}/cartera`),
  evolucion: (id: number, dias: number | string) => request<Evolucion>("GET", `/cuentas/${id}/evolucion?dias=${dias}`),
  movimientos: (id: number) => request<Movimiento[]>("GET", `/cuentas/${id}/movimientos`),
  moverDinero: (id: number, tipo: "depositos" | "extracciones", moneda: Moneda, monto: number) =>
    request<Movimiento>("POST", `/cuentas/${id}/${tipo}`, { moneda, monto }),
  comprar: (id: number, activoId: number, cantidad: number) =>
    request<Operacion>("POST", `/cuentas/${id}/compras`, { activo_id: activoId, cantidad }),
  vender: (id: number, activoId: number, cantidad: number) =>
    request<Operacion>("POST", `/cuentas/${id}/ventas`, { activo_id: activoId, cantidad }),
  mep: (id: number, monto_ars: number) => request<MepResultado>("POST", `/cuentas/${id}/mep`, { monto_ars }),
  operaciones: (id: number, filtro: Partial<FiltroOperaciones> = {}) =>
    request<HistorialOperaciones>("GET", `/cuentas/${id}/operaciones${qs(filtro)}`),
  ganancias: (id: number) => request<Ganancias>("GET", `/cuentas/${id}/ganancias-realizadas`),
};
