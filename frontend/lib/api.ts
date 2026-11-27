// Cliente de la API del broker. Todas las rutas van a /api/* y next.config.ts las reenvía al backend.
import type {
  Activo, ActivoCrear, Alerta, AlertaCrear, Avisos, Cartera, Cuenta, DividendoResultado, Dolares, EstadoHistorial, EstadoMercado,
  EstadoPrecios, Evolucion, FiltroOperaciones, Ganancias, HistorialDiario, HistorialOperaciones, Intradia,
  InformeAgente, Inversor, InversorCrear, MensajeAgente, MepResultado, Moneda, Movimiento, Operacion, Perfil, Sesion,
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
  constructor(message: string, public status: number, public campos: Record<string, string> = {}, public codigo = "") {
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
    const d = data as { detail?: unknown; message?: unknown; campos?: Record<string, string>; error?: string } | null;
    const msg = d?.detail ?? d?.message;
    const texto = msg == null ? (res.status >= 500 ? "No se pudo conectar con la API. ¿Está corriendo el backend?" : `Error ${res.status}`)
      : typeof msg === "string" ? msg : JSON.stringify(msg);
    throw new ApiError(texto, res.status, d?.campos ?? {}, d?.error ?? "");
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
  verificarEmail: (email: string, codigo: string) => request<Sesion>("POST", "/auth/verificar-email", { email, codigo }),
  reenviarCodigo: (email: string) => request<{ ok: boolean; espera: number }>("POST", "/auth/reenviar-codigo", { email }),
  validarEmail: (email: string) => request<{ valido: boolean; email: string; mensaje: string | null }>("POST", "/inversores/validar-email", { email }),
  inversor: (id: number) => request<Inversor>("GET", `/inversores/${id}`),
  cambiarPerfil: (id: number, perfil_riesgo: Perfil) => request<Inversor>("PATCH", `/inversores/${id}/perfil`, { perfil_riesgo }),
  // Olvidé mi contraseña (sin sesión): código al correo → permiso → contraseña nueva (abre la sesión)
  olvidePedir: (email: string) =>
    request<{ enviado: boolean; email: string; minutos: number }>("POST", "/auth/olvide", { email }),
  olvideVerificar: (email: string, codigo: string) =>
    request<{ permiso: string; minutos: number }>("POST", "/auth/olvide/verificar", { email, codigo }),
  olvideCambiar: (email: string, permiso: string, nueva: string) =>
    request<Sesion>("POST", "/auth/olvide/cambiar", { email, permiso, nueva }),
  // Cambio de contraseña: 1) llega un código al correo, 2) se confirma (da un permiso), 3) se elige la nueva
  pedirCodigoPassword: (id: number) =>
    request<{ enviado: boolean; email: string; minutos: number }>("POST", `/inversores/${id}/password/codigo`),
  verificarCodigoPassword: (id: number, codigo: string) =>
    request<{ permiso: string; minutos: number }>("POST", `/inversores/${id}/password/verificar`, { codigo }),
  cambiarPassword: (id: number, permiso: string, nueva: string) =>
    request<{ ok: boolean; token: string }>("POST", `/inversores/${id}/password`, { permiso, nueva }),
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

  // Alertas de precio y avisos (cada uno ve solo las suyas: van con el token de la sesión)
  alertas: () => request<Alerta[]>("GET", "/alertas"),
  crearAlerta: (datos: AlertaCrear) => request<Alerta>("POST", "/alertas", datos),
  editarAlerta: (id: number, datos: Partial<AlertaCrear>) => request<Alerta>("PUT", `/alertas/${id}`, datos),
  estadoAlerta: (id: number, estado: "activa" | "pausada") => request<Alerta>("PATCH", `/alertas/${id}/estado`, { estado }),
  borrarAlerta: (id: number) => request<null>("DELETE", `/alertas/${id}`),
  avisos: () => request<Avisos>("GET", "/notificaciones"),
  leerAvisos: () => request<null>("POST", "/notificaciones/leidas"),

  // Agente de inversiones (Zeno AI)
  agenteEstado: () => request<{ configurado: boolean; modelo: string }>("GET", "/agente/estado"),
  agenteInforme: (actualizar = false) => request<InformeAgente>("GET", `/agente/informe${actualizar ? "?actualizar=true" : ""}`),
};

/**
 * Chat con el agente: la respuesta llega de a pedazos (Server-Sent Events) y se va pasando a `alTexto`.
 * Devuelve el texto completo. Se puede cortar con `signal`.
 */
export async function chatAgente(mensajes: MensajeAgente[], alTexto: (parcial: string) => void, signal?: AbortSignal): Promise<string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}/agente/chat`, { method: "POST", headers, body: JSON.stringify({ mensajes }), signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("No se pudo conectar con la API. ¿Está corriendo el backend?", 0);
  }
  if (!res.ok || !res.body) {
    const d = await res.json().catch(() => null) as { detail?: string; error?: string } | null;
    throw new ApiError(d?.detail ?? `Error ${res.status}`, res.status, {}, d?.error ?? "");
  }
  const lector = res.body.getReader();
  const deco = new TextDecoder();
  let pendiente = "", texto = "";
  for (;;) {
    const { value, done } = await lector.read();
    if (done) break;
    pendiente += deco.decode(value, { stream: true });
    const eventos = pendiente.split(/\r?\n\r?\n/);
    pendiente = eventos.pop() ?? "";
    for (const ev of eventos) {
      const dato = ev.replace(/^data: /, "").trim();
      if (!dato || dato === "[FIN]") continue;
      const j = JSON.parse(dato) as { texto?: string; error?: string };
      if (j.error) throw new ApiError(j.error, 502);
      if (j.texto) {
        texto += j.texto;
        alTexto(texto);
      }
    }
  }
  return texto;
}
