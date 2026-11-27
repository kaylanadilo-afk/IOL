"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cls, COLORS, compacto, diaCorto, hora, money, num, pct, TIPO_PLURAL, TZ } from "@/lib/format";
import type { Cartera, Dolares, Moneda } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { DonutSvg, LineChart, type DonutPart } from "./charts";
import { IcoIngresar, IcoLista, IcoRetirar } from "./icons";

export function composicionParts(cart: Cartera): DonutPart[] {
  return cart.composicion_por_tipo.map((c) => ({ label: TIPO_PLURAL[c.tipo], value: c.valor_ars, pct: c.porcentaje, color: COLORS[c.tipo] }));
}

/* ===================== DÓLAR HOY ===================== */
// A la vista: oficial, blue y MEP. El resto aparece con "Ver más opciones".
const DOLAR_PRINCIPALES: [string, string][] = [["oficial", "Oficial"], ["blue", "Blue"], ["bolsa", "MEP"]];
const DOLAR_MAS: [string, string][] = [["contadoconliqui", "CCL"], ["cripto", "Cripto"], ["tarjeta", "Tarjeta"], ["mayorista", "Mayorista"]];

export function DolaresCard({ dolares, error }: { dolares: Dolares | null; error?: string | null }) {
  const [mas, setMas] = useState(false);
  if (error) {
    return <div className="card"><div className="ctitle"><h2>Dólar hoy</h2></div><div className="empty">{error}</div></div>;
  }
  if (!dolares) return <div className="card"><div className="ctitle"><h2>Dólar hoy</h2></div><div className="empty">Cargando…</div></div>;
  const byCasa = Object.fromEntries(dolares.cotizaciones.map((c) => [c.casa, c]));
  const fila = ([casa, nombre]: [string, string]) => {
    const x = byCasa[casa];
    if (!x) return null;
    return (
      <div key={casa} className="dolar-row" title={x.fecha_actualizacion ? `Actualizado ${hora(x.fecha_actualizacion)}` : undefined}>
        <b>{nombre}</b>
        <span className="muted">{x.compra != null ? money(x.compra, "ARS") : "—"}</span>
        <span>{money(x.venta, "ARS")}</span>
      </div>
    );
  };
  return (
    <div className="card">
      <div className="ctitle"><h2>Dólar hoy</h2><span className="muted" style={{ fontSize: 12 }}>dolarapi.com</span></div>
      <div className="dolar-row dolar-head"><span /><span>Compra</span><span>Venta</span></div>
      {DOLAR_PRINCIPALES.map(fila)}
      {mas && (
        <div className="dolar-more">
          {DOLAR_MAS.map(fila)}
          {dolares.mep_broker_al30 && (
            <div className="dolar-row"><b>MEP de la app</b><span className="muted">AL30 / AL30D</span><span>{money(dolares.mep_broker_al30, "ARS")}</span></div>
          )}
        </div>
      )}
      <button type="button" className="link-btn" onClick={() => setMas(!mas)}>{mas ? "Ver menos" : "Ver más opciones"}</button>
    </div>
  );
}

/** Carga /mercado/dolares sin frenar la pantalla: si falla, la tarjeta lo dice y el resto sigue andando. */
export function DolaresCardAuto() {
  const { reloadKey } = useMe();
  const { data, error } = useAsync(() => api.dolares(), [reloadKey]);
  return <DolaresCard dolares={data} error={error} />;
}

/* ===================== VALOR DE LA CARTERA ===================== */
const RANGOS: [string, string][] = [["30", "1M"], ["90", "3M"], ["180", "6M"], ["365", "1A"]];

export function PortfolioChartCard({ title }: { title: string }) {
  const { cuentaId, reloadKey, liveTick } = useMe();
  const [rango, setRango] = useState("90");
  const { data, error } = useAsync(() => api.evolucion(cuentaId, rango), [cuentaId, rango, reloadKey, liveTick]);
  const pts = data
    ? data.puntos.map((p) => {
        const x = Date.parse(p.fecha + "T17:00:00-03:00");
        return { x, y: p.valor_ars, label: <><b>{money(p.valor_ars, "ARS")}</b><br />{diaCorto(p.fecha)}</> };
      })
    : null;
  const ticks: { x: number; label: string }[] = [];
  if (pts?.length) {
    for (let i = 0; i < 4; i++) {
      const p = pts[Math.round((i * (pts.length - 1)) / 3)];
      if (!ticks.length || ticks[ticks.length - 1].x !== p.x) {
        ticks.push({ x: p.x, label: new Date(p.x).toLocaleDateString("es-AR", { day: "2-digit", month: "short", timeZone: TZ }) });
      }
    }
  }
  return (
    <div className="card span2">
      <div className="ctitle">
        <div>
          <h2>{title}</h2>
          {data?.variacion_pct != null && (
            <div className="chart-var"><b className={cls(data.variacion_pct)}>{pct(data.variacion_pct)}</b></div>
          )}
        </div>
        <div className="tabs">
          {RANGOS.map(([v, l]) => (
            <button key={v} type="button" className={`tab${rango === v ? " active" : ""}`} onClick={() => setRango(v)}>{l}</button>
          ))}
        </div>
      </div>
      {error ? (
        <div className="chart home-chart"><div className="msg">{error}</div></div>
      ) : (
        <LineChart className="chart home-chart" pts={pts} opt={{ xTicks: ticks, aria: "Valor de tu cartera", vacio: "Cuando tengas inversiones vas a ver acá cómo cambia su valor." }} />
      )}
    </div>
  );
}

/* ===================== DISPONIBLE (ARS / USD) ===================== */
export function CashButton({ saldos, oculto = false }: { saldos: Cartera["saldos_disponibles"]; oculto?: boolean }) {
  const [cur, setCur] = useState<"ARS" | "USD">("ARS");
  const [flip, setFlip] = useState(0);
  const { vibrar } = useUI();
  return (
    <button
      type="button"
      className="cash"
      aria-label={`Disponible para operar en ${cur === "ARS" ? "pesos" : "dólares"}. Tocá para cambiar de moneda.`}
      onClick={() => { setCur(cur === "ARS" ? "USD" : "ARS"); setFlip((f) => f + 1); vibrar(6); }}
    >
      <small>Disponible para operar <span className="seg"><i className={cur === "ARS" ? "on" : ""}>ARS</i><i className={cur === "USD" ? "on" : ""}>USD</i></span></small>
      <span key={flip} className={`amt${flip ? " flip" : ""}`}>{oculto ? `${cur === "USD" ? "US$" : "$"} ******` : money(saldos[cur], cur)}</span>
    </button>
  );
}

/* ===================== INSTALAR (celular) ===================== */
export function InstallBanner() {
  const { puedeInstalar, esIOS, esStandalone, instalar } = useUI();
  const [cerrado, setCerrado] = useState(() => {
    try {
      return typeof window !== "undefined" && localStorage.getItem("iolAula_installCerrado") === "1";
    } catch {
      return false;
    }
  });
  if (cerrado || esStandalone || (!puedeInstalar && !esIOS)) return null;
  return (
    <div className="install-banner only-m">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/icons/icon-192.png" alt="" style={{ background: "#fff" }} />
      <div style={{ flex: 1 }}>
        <b>Instalá Zeno Investments</b>
        <div style={{ fontSize: 12.5, opacity: 0.85 }}>{puedeInstalar ? "Abrila como una app, a pantalla completa." : 'Tocá Compartir ⎋ y después "Agregar a inicio".'}</div>
      </div>
      {puedeInstalar && <button type="button" className="btn btn-sm" onClick={instalar}>Instalar</button>}
      <button type="button" className="x" aria-label="Cerrar" onClick={() => {
        try { localStorage.setItem("iolAula_installCerrado", "1"); } catch { /* sin almacenamiento */ }
        setCerrado(true);
      }}>×</button>
    </div>
  );
}


/* ===================== DISTRIBUCIÓN DEL PATRIMONIO ===================== */
export interface ItemCategoria { clave: string; titulo: string; detalle: string; valorArs: number; nativo: string }
export interface Categoria { key: string; label: string; value: number; color: string; items: ItemCategoria[] }

const COLOR_PESOS = "#94A3B8";

/**
 * Todo el patrimonio por categoría, en pesos (los dólares se pasan al MEP de la app).
 * Cada peso se cuenta una sola vez: tenencias por tipo de activo + saldo en dólares + saldo en pesos.
 */
export function distribucion(cart: Cartera): Categoria[] {
  const tc = cart.tipo_cambio_mep ?? 0;
  const aArs = (v: number, m: Moneda) => (m === "USD" ? v * tc : v);
  const cats: Categoria[] = (["accion", "cedear", "bono"] as const).map((tipo) => {
    const items = cart.tenencias.filter((t) => t.tipo === tipo).map((t) => ({
      clave: String(t.activo_id), titulo: t.ticker, detalle: `${num(t.cantidad)} u. · ${t.nombre}`,
      valorArs: aArs(t.valor_actual, t.moneda), nativo: money(t.valor_actual, t.moneda),
    }));
    return { key: tipo, label: TIPO_PLURAL[tipo], color: COLORS[tipo], items, value: items.reduce((s, i) => s + i.valorArs, 0) };
  });
  const usd = cart.saldos_disponibles.USD, ars = cart.saldos_disponibles.ARS;
  if (usd > 0 && tc) {
    cats.push({ key: "usd", label: "Dólares", color: COLORS.USD, value: usd * tc,
      items: [{ clave: "usd", titulo: "Disponible en dólares", detalle: `al MEP de ${money(tc, "ARS")}`, valorArs: usd * tc, nativo: money(usd, "USD") }] });
  }
  if (ars > 0) {
    cats.push({ key: "ars", label: "Pesos", color: COLOR_PESOS, value: ars,
      items: [{ clave: "ars", titulo: "Disponible en pesos", detalle: "Para operar", valorArs: ars, nativo: money(ars, "ARS") }] });
  }
  return cats.filter((c) => c.value > 0).sort((a, b) => b.value - a.value);
}

/** Inversiones, dólares y cotización del dólar en un solo lugar (Inicio). */
export function PatrimonioCard({ cart, oculto }: { cart: Cartera; oculto: boolean }) {
  const { reloadKey } = useMe();
  const { data: dol } = useAsync(() => api.dolares(), [reloadKey]);
  const cats = distribucion(cart);
  const total = cats.reduce((s, c) => s + c.value, 0);
  const tc = cart.tipo_cambio_mep;
  const tapar = (t: string) => (oculto ? t.replace(/[\d.,]+/g, "****") : t);
  const casas = dol ? Object.fromEntries(dol.cotizaciones.map((c) => [c.casa, c])) : {};
  return (
    <div className="card patrimonio-card">
      <div className="ctitle"><h2>Inversiones y dólares</h2><Link href="/cartera" className="btn btn-ghost btn-sm">Ver cartera</Link></div>
      {total > 0 ? (
        <div className="dist">
          <DonutSvg parts={cats} centro={<><small>Total</small><b>{oculto ? "$ ****" : compacto(total, "ARS")}</b></>} />
          <table className="compact dist-table">
            <thead><tr><th>Categoría</th><th className="num">Valor</th><th className="num">%</th></tr></thead>
            <tbody>
              {cats.map((c) => (
                <tr key={c.key}>
                  <td><span className="sw" style={{ background: c.color }} />{c.label}</td>
                  <td className="num">{tapar(c.key === "usd" ? c.items[0].nativo : money(c.value, "ARS"))}</td>
                  <td className="num">{((c.value / total) * 100).toFixed(1).replace(".", ",")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted dist-nota">
            {tc ? <>Total en pesos, con los dólares al MEP de {money(tc, "ARS")}{oculto ? "." : <> · ≈ {money(total / tc, "USD").replace(/,\d+$/, "")}.</>}</> : "Sin cotización MEP: los dólares no se suman al total."}
          </p>
        </div>
      ) : (
        <div className="empty">Todavía no tenés saldo ni inversiones. Ingresá dinero para empezar.</div>
      )}
      <div className="dolar-mini">
        <div className="dolar-mini-head"><b>Dólar hoy</b><span className="muted">compra / venta · dolarapi.com</span></div>
        {dol ? ([["oficial", "Oficial"], ["blue", "Blue"], ["bolsa", "MEP"]] as const).map(([casa, nombre]) => {
          const x = casas[casa];
          return x ? (
            <div key={casa} className="dolar-row"><b>{nombre}</b><span className="muted">{x.compra != null ? money(x.compra, "ARS") : "—"}</span><span>{money(x.venta, "ARS")}</span></div>
          ) : null;
        }) : <div className="muted" style={{ fontSize: 13 }}>Cargando cotizaciones…</div>}
      </div>
    </div>
  );
}

/* ===================== INGRESAR / RETIRAR DINERO ===================== */
export type AccionDinero = "ingresar" | "retirar";

/** Botones de dinero: Ingresar y Retirar abren una ventana; Ver movimientos va a la tabla. */
export function DineroBotones({ onAccion, verMovimientos = true }: { onAccion: (a: AccionDinero) => void; verMovimientos?: boolean }) {
  return (
    <div className="dinero-botones">
      <button type="button" className="btn btn-ghost" onClick={() => onAccion("ingresar")}><IcoIngresar />Ingresar dinero</button>
      <button type="button" className="btn btn-ghost" onClick={() => onAccion("retirar")}><IcoRetirar />Retirar dinero</button>
      {verMovimientos && <Link href="/movimientos" className="btn btn-ghost"><IcoLista />Ver movimientos</Link>}
    </div>
  );
}

/** Ventana para ingresar o retirar dinero. Es una operación simulada: no mueve dinero real. */
export function DineroDialog({ accion, onClose, onListo }: { accion: AccionDinero; onClose: () => void; onListo?: () => void }) {
  const { cuentaId, reloadAll } = useMe();
  const { toast } = useUI();
  const { data: cuenta } = useAsync(() => api.cuenta(cuentaId), [cuentaId]);
  const [moneda, setMoneda] = useState<Moneda>("ARS");
  const [monto, setMonto] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const ingresar = accion === "ingresar";
  const saldo = cuenta ? (moneda === "ARS" ? cuenta.saldo_ars : cuenta.saldo_usd) : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    const texto = monto.trim();
    const n = Number(texto.replace(",", "."));
    if (!(n > 0)) return setError("Ingresá un monto mayor a 0");
    if (!/^\d+([.,]\d{1,2})?$/.test(texto)) return setError("Escribí solo números, con hasta 2 decimales");
    if (!ingresar && saldo != null && n > saldo) return setError(`No te alcanza: tenés ${money(saldo, moneda)} disponibles`);
    setBusy(true);
    setError("");
    try {
      const m = await api.moverDinero(cuentaId, ingresar ? "depositos" : "extracciones", moneda, n);
      toast(`${ingresar ? "Ingreso" : "Retiro"} de ${money(m.monto, m.moneda)} registrado (operación simulada).`);
      await reloadAll();
      onListo?.();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-bg" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <form className="modal" role="dialog" aria-modal="true" aria-labelledby="dineroTitulo" onSubmit={enviar} noValidate>
        <h3 id="dineroTitulo">{ingresar ? "Ingresar dinero" : "Retirar dinero"}</h3>
        <div className="sim-badge">Operación simulada · no se mueve dinero real</div>
        <div className="field">
          <span className="field-label">Moneda</span>
          <div className="tabs" role="group" aria-label="Moneda">
            {(["ARS", "USD"] as const).map((m) => (
              <button key={m} type="button" className={`tab${moneda === m ? " active" : ""}`} aria-pressed={moneda === m}
                onClick={() => { setMoneda(m); setError(""); }}>
                {m === "ARS" ? "Pesos" : "Dólares"}
              </button>
            ))}
          </div>
        </div>
        <div className={`field${error ? " invalid" : ""}`}>
          <label htmlFor="dineroMonto">Monto</label>
          <input id="dineroMonto" inputMode="decimal" autoFocus placeholder={moneda === "ARS" ? "100000" : "500"} value={monto}
            aria-invalid={!!error} aria-describedby={error ? "dineroMonto-err" : "dineroMonto-hint"}
            onChange={(e) => { setMonto(e.target.value); setError(""); }} />
          {error
            ? <p className="field-err" id="dineroMonto-err" role="alert">{error}</p>
            : <p className="field-hint" id="dineroMonto-hint">Disponible: {saldo != null ? money(saldo, moneda) : "…"}</p>}
        </div>
        <p className="muted" style={{ fontSize: 12.5, margin: "4px 0 0" }}>
          Zeno todavía no está conectado a bancos ni medios de pago: el saldo cambia en la app, pero no se transfiere dinero.
        </p>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Procesando…" : ingresar ? "Ingresar" : "Retirar"}</button>
        </div>
      </form>
    </div>
  );
}
