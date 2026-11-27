import type { Activo, Moneda, Perfil, TipoActivo, TipoMovimiento } from "./types";

export const FEE = 0.005; // comisión 0,5 %
export const RIESGO_MAX: Record<Perfil, number> = { conservador: 2, moderado: 4, agresivo: 5 };
export const TIPO_LBL: Record<TipoActivo, string> = { accion: "Acción", cedear: "CEDEAR", bono: "Bono" };
export const TIPO_PLURAL: Record<TipoActivo, string> = { accion: "Acciones", cedear: "CEDEARs", bono: "Bonos" };
export const COLORS: Record<string, string> = { accion: "#3F86C8", cedear: "#8CC4EE", bono: "#C9A227", ARS: "#3F86C8", USD: "#0A9F66" };
export const MOV_LBL: Record<TipoMovimiento, string> = { deposito: "Depósito", extraccion: "Extracción", dividendo: "Dividendo" };
export const PERFILES: Perfil[] = ["conservador", "moderado", "agresivo"];
export const TZ = "America/Argentina/Buenos_Aires";

const fmtARS = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtUSD = new Intl.NumberFormat("es-AR", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 });
const fmtNum = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 4 });
const fmtCompact = new Intl.NumberFormat("es-AR", { notation: "compact", maximumFractionDigits: 1 });

export function money(n: number | null | undefined, cur: Moneda | string = "ARS"): string {
  const v = Number(n) || 0;
  return cur === "USD" ? fmtUSD.format(v) : fmtARS.format(v);
}
export const signed = (n: number, cur: Moneda | string) => (n > 0 ? "+" : "") + money(n, cur);
export const num = (n: number | null | undefined) => fmtNum.format(Number(n) || 0);
export function pct(n: number | null | undefined): string {
  const v = Number(n) || 0;
  return (v > 0 ? "+" : "") + v.toFixed(2).replace(".", ",") + "%";
}
export const cls = (n: number | null | undefined) => (n == null ? "muted" : n > 0 ? "up" : n < 0 ? "down" : "muted");
export const round2 = (n: number) => Math.round(n * 100) / 100;
export const compacto = (n: number, cur: Moneda | string) => (cur === "USD" ? "US$ " : "$ ") + fmtCompact.format(Number(n) || 0);

export const fecha = (iso: string) =>
  new Date(iso).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
export const hora = (iso: string) => new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
export const horaAR = (ms: number) =>
  new Date(ms).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: TZ });
export const diaCorto = (iso: string) =>
  new Date(iso + "T12:00:00-03:00").toLocaleDateString("es-AR", { weekday: "short", day: "2-digit", month: "2-digit", timeZone: TZ });
export const hoyAR = () => new Date().toLocaleDateString("en-CA", { timeZone: TZ });

export function iniciales(nombre: string): string {
  return nombre.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");
}

export const permitido = (a: Pick<Activo, "nivel_riesgo">, perfil: Perfil) => a.nivel_riesgo <= RIESGO_MAX[perfil];
