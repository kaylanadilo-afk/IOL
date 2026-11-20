"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { cls, COLORS, diaCorto, hora, money, pct, TIPO_PLURAL, TZ } from "@/lib/format";
import type { Cartera, Dolares } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { LineChart, type DonutPart } from "./charts";

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
      <span key={flip} className={`amt${flip ? " flip" : ""}`}>{oculto ? `${cur === "USD" ? "US$" : "$"} ••••••` : money(saldos[cur], cur)}</span>
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
      <img src="/icons/icon-192.png" alt="" />
      <div style={{ flex: 1 }}>
        <b>Instalá IOL Aula</b>
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
