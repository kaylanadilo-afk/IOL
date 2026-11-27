"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  cls, diaCorto, FEE, hora, horaAR, hoyAR, money, num, pct, permitido, RIESGO_MAX, round2, signed, TIPO_LBL, TZ,
} from "@/lib/format";
import type { Activo, HistorialDiario, Intradia } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { LineChart, type ChartPoint } from "@/components/charts";
import { ErrorCard, EstadoPill, FuentePrecios, Loading, RiskDots, StarButton, SummaryRows, VarPill } from "@/components/ui";
import { IcoAlerta } from "@/components/icons";

type Lado = "buy" | "sell";
const RANGOS: [string, string][] = [["hoy", "Hoy"], ["7", "1S"], ["30", "1M"], ["90", "3M"], ["180", "6M"], ["365", "1A"]];

export default function ActivoPage() {
  const { id } = useParams<{ id: string }>();
  const activoId = Number(id);
  const { me, cuentaId, mercado, setMercado, activoById, reloadKey, liveTick } = useMe();
  const { confirm, toast, vibrar } = useUI();
  const [side, setSide] = useState<Lado>("buy");
  const [tradeOpen, setTradeOpen] = useState(false);
  const [qty, setQty] = useState("10");
  const [msg, setMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const { data, error, reload } = useAsync(
    () => Promise.all([api.activo(activoId), api.cartera(cuentaId), api.mercado()]),
    [activoId, cuentaId, reloadKey, nonce],
  );
  useEffect(() => { if (data) setMercado(data[2]); }, [data, setMercado]);

  // En el celular aparece la barra Comprar / Vender abajo
  useEffect(() => {
    document.body.classList.add("has-trade-bar");
    return () => document.body.classList.remove("has-trade-bar");
  }, []);

  if (error) return <ErrorCard message={error} onRetry={reload} />;
  if (!data) return <Loading />;

  // Con precios reales, el precio se actualiza solo cada 30 s (el contexto trae el catálogo nuevo)
  const a: Activo = { ...data[0], ...(activoById(activoId) ?? {}) };
  const cart = data[1];
  const h = cart.tenencias.find((t) => t.activo_id === a.id);
  const saldo = cart.saldos_disponibles[a.moneda];
  const m = mercado ?? data[2];

  const avisos: React.ReactNode[] = [];
  if (!m.abierto) avisos.push("El mercado está cerrado: las órdenes se rechazan fuera de lunes a viernes de 11 a 17.");
  if (!a.activo) avisos.push(`${a.ticker} está suspendido y no se puede operar.`);
  if (!permitido(a, me.perfil_riesgo) && side === "buy") {
    avisos.push(<>Nivel de riesgo {a.nivel_riesgo}: tu perfil {me.perfil_riesgo} no permite comprarlo. <Link href="/perfil">Actualizar perfil</Link></>);
  }

  const q = Number(qty) || 0;
  const gross = round2(Math.max(q, 0) * a.precio_actual), fee = round2(gross * FEE);
  const total = side === "buy" ? gross + fee : gross - fee;
  const ganancia = side === "sell" && h && q > 0 ? (a.precio_actual - h.precio_promedio) * q - fee : null;
  const verb = side === "buy" ? "Compra" : "Venta";

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!Number.isInteger(q) || q < 1) return setMsg("Ingresá una cantidad entera mayor a 0.");
    confirm({
      title: `Confirmar ${verb.toLowerCase()}`,
      body: <SummaryRows rows={[
        ["Activo", a.ticker], ["Operación", `${verb} a precio actual`], ["Cantidad", num(q)], ["Precio", money(a.precio_actual, a.moneda)],
        ["Comisión", money(fee, a.moneda)], [side === "buy" ? "Total a pagar" : "Total a cobrar", money(total, a.moneda), true],
      ]} />,
      okText: "Confirmar",
      onOk: () => {
        (side === "buy" ? api.comprar(cuentaId, a.id, q) : api.vender(cuentaId, a.id, q))
          .then((op) => {
            const extra = op.ganancia_realizada != null ? ` Resultado: ${signed(op.ganancia_realizada, op.moneda)}.` : "";
            toast(`${verb} de ${num(op.cantidad)} ${op.ticker} ejecutada por ${money(op.total, op.moneda)}.${extra}`);
            setTradeOpen(false);
            vibrar([12, 40, 12]);
            setNonce((n) => n + 1);
          })
          .catch((err: Error) => { setMsg(err.message); toast(err.message, true); });
      },
    });
  };

  const abrirTrade = (lado: Lado) => { setSide(lado); setTradeOpen(true); setMsg(""); };

  return (
    <>
      <div className="head">
        <div><Link href="/mercado" className="btn btn-ghost btn-sm">← Volver al mercado</Link></div>
        <Link href={`/alertas?activo=${a.id}`} className="btn btn-ghost btn-sm"><IcoAlerta />Crear alerta de precio</Link>
      </div>
      <div className="grid gtrade">
        <div className="grid" style={{ alignContent: "start" }}>
          <div className="card">
            <div className="asset-head">
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}><StarButton a={a} /><h1 style={{ margin: 0, fontSize: 24 }}>{a.ticker}</h1></div>
                <div className="muted asset-sub">{a.nombre} <span className="pill neutral">{TIPO_LBL[a.tipo]} en {a.moneda === "ARS" ? "pesos" : "dólares"}</span> <RiskDots n={a.nivel_riesgo} /></div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="big-price">{money(a.precio_actual, a.moneda)}</div>
                <VarPill a={a} /> <EstadoPill a={a} />
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{a.precio_actualizado ? `Precio de las ${hora(a.precio_actualizado)}` : ""}</div>
              </div>
            </div>
            <PriceChart a={a} liveTick={liveTick} reloadKey={reloadKey + nonce} preciosReales={m.precios?.modo === "reales"} />
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Tipo</th><th>Moneda</th><th>Tu perfil ({me.perfil_riesgo}) permite</th><th>Estado</th></tr></thead>
                <tbody>
                  <tr>
                    <td>{TIPO_LBL[a.tipo]}</td><td>{a.moneda === "ARS" ? "Pesos (ARS)" : "Dólares (USD)"}</td>
                    <td><RiskDots n={RIESGO_MAX[me.perfil_riesgo]} /></td>
                    <td><EstadoPill a={a} /></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <FuentePrecios />
          </div>
          <div className="card">
            <div className="ctitle"><h2>Tu posición</h2></div>
            {h ? (
              <>
                <div className="list-row"><span className="muted">Tu tenencia</span><b>{num(h.cantidad)} u. · {money(h.valor_actual, a.moneda)}</b></div>
                <div className="list-row"><span className="muted">Precio promedio</span><b>{money(h.precio_promedio, a.moneda)}</b></div>
                <div className="list-row"><span className="muted">Resultado</span><b className={cls(h.resultado)}>{signed(h.resultado, a.moneda)} ({pct(h.rendimiento_pct)})</b></div>
              </>
            ) : <div className="empty" style={{ padding: 14 }}>Todavía no tenés este activo.</div>}
          </div>
        </div>

        <div className={`card trade-card${tradeOpen ? " open" : ""}`} style={{ alignSelf: "start" }}>
          <div className="grabber only-m" onClick={() => setTradeOpen(false)} />
          <div className="ctitle">
            <h2>Operar {a.ticker} <span className="muted" style={{ fontWeight: 600, fontSize: 14 }}>· {money(a.precio_actual, a.moneda)}</span></h2>
            <button type="button" className="btn btn-ghost btn-sm only-m" aria-label="Cerrar" onClick={() => setTradeOpen(false)}>✕</button>
          </div>
          <form onSubmit={onSubmit} noValidate>
            <div className="side-tabs">
              <button type="button" className={`btn ${side === "buy" ? "on-buy" : ""}`} onClick={() => setSide("buy")}>Comprar</button>
              <button type="button" className={`btn ${side === "sell" ? "on-sell" : ""}`} onClick={() => setSide("sell")}>Vender</button>
            </div>
            {avisos.length > 0 && <div className="notice" style={{ margin: "0 0 6px" }}>{avisos.map((x, i) => <div key={i}>{x}</div>)}</div>}
            <div className="field">
              <label htmlFor="qty">Cantidad (unidades)</label>
              <input id="qty" type="number" inputMode="numeric" min={1} step={1} value={qty} onChange={(e) => { setQty(e.target.value); setMsg(""); }} />
            </div>
            <div className="summary">
              <div><span className="muted">Precio actual</span><b>{money(a.precio_actual, a.moneda)}</b></div>
              <div><span className="muted">Importe bruto</span><span>{money(gross, a.moneda)}</span></div>
              <div><span className="muted">Comisión (0,5 %)</span><span>{money(fee, a.moneda)}</span></div>
              <div className="tot"><span>{side === "buy" ? "Total a pagar" : "Total a cobrar"}</span><span>{money(total, a.moneda)}</span></div>
              {ganancia != null && <div><span className="muted">Ganancia estimada</span><span className={cls(ganancia)}>{signed(ganancia, a.moneda)}</span></div>}
              <div><span className="muted" style={{ fontSize: 12.5 }}>
                {side === "buy" ? `Disponible: ${money(saldo, a.moneda)}` : `Disponible para vender: ${num(h ? h.cantidad : 0)} u.`}
              </span></div>
            </div>
            <button type="submit" className={`btn full ${side === "buy" ? "btn-buy" : "btn-sell"}`}>{side === "buy" ? "Revisar compra" : "Revisar venta"}</button>
            <div className="form-msg" aria-live="polite">{msg}</div>
          </form>
          <p className="muted" style={{ fontSize: 12, margin: "10px 0 0" }}>Orden a precio actual. Comisión 0,5 % del monto operado. Se debita/acredita en {a.moneda}.</p>
        </div>
      </div>
      <div className={`sheet-bg${tradeOpen ? " open" : ""}`} onClick={() => setTradeOpen(false)} />
      <div className="trade-bar">
        <button type="button" className="btn btn-buy" onClick={() => abrirTrade("buy")}>Comprar</button>
        <button type="button" className="btn btn-sell" disabled={!h} title={h ? undefined : "No tenés este activo"} onClick={() => abrirTrade("sell")}>Vender</button>
      </div>
    </>
  );
}

/* ===================== GRÁFICO DE PRECIOS ===================== */
type Celda = [string, React.ReactNode, string?];

/** Datos del período del gráfico en una tabla de una fila (encabezado + valores). */
function TablaGrafico({ celdas }: { celdas: (Celda | false | null)[] }) {
  const cols = celdas.filter(Boolean) as Celda[];
  if (!cols.length) return null;
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr>{cols.map(([k]) => <th key={k}>{k}</th>)}</tr></thead>
        <tbody><tr>{cols.map(([k, v, klass]) => <td key={k} className={klass}>{v}</td>)}</tr></tbody>
      </table>
    </div>
  );
}

function PriceChart({ a, liveTick, reloadKey, preciosReales }: { a: Activo; liveTick: number; reloadKey: number; preciosReales: boolean }) {
  const [rango, setRango] = useState("hoy");
  const [dia, setDia] = useState("");
  const intradia = rango === "hoy" || rango === "dia";
  // El gráfico del día se mueve en vivo con los precios reales
  const tick = rango === "hoy" ? liveTick : 0;
  const { data, error } = useAsync<Intradia | HistorialDiario>(
    () => (intradia ? api.intradia(a.id, rango === "dia" ? dia : undefined) : api.historial(a.id, rango)),
    [a.id, rango, dia, tick, reloadKey],
  );
  const m = a.moneda;

  let pts: ChartPoint[] | null = null;
  let opt: Parameters<typeof LineChart>[0]["opt"] = { aria: "", vacio: "" };
  let celdas: (Celda | false | null)[] = [];
  let dias: string[] = [];
  let fechaDia: string | null = null;

  if (data && intradia && "puntos" in data && "dias_disponibles" in data) {
    const d = data as Intradia;
    dias = d.dias_disponibles;
    fechaDia = d.fecha;
    const x0 = d.fecha ? Date.parse(d.fecha + "T11:00:00-03:00") : 0;
    pts = d.puntos.map((p) => {
      const x = Date.parse(p.t);
      return { x, y: p.precio, label: <><b>{money(p.precio, m)}</b><br />{horaAR(x)} hs</> };
    });
    opt = {
      xMin: x0, xMax: x0 + 6 * 3600e3,
      xTicks: [11, 12, 13, 14, 15, 16, 17].map((hh) => ({ x: x0 + (hh - 11) * 3600e3, label: `${hh}:00` })),
      ref: d.cierre_anterior, aria: `Precio de ${a.ticker} durante el día`,
      vacio: preciosReales
        ? "Todavía no hay datos de este día. El gráfico se completa durante la rueda (11 a 17 hs)."
        : "Sin datos intradiarios. Activá los precios reales (PRECIOS_REALES=1) o cambiá el precio desde Administración.",
    };
    if (d.puntos.length && d.fecha) {
      celdas = [
        [rango === "hoy" && d.fecha === hoyAR() ? "Hoy" : "Día", diaCorto(d.fecha)],
        ["Apertura", money(d.apertura, m)], ["Máximo", money(d.maximo, m)], ["Mínimo", money(d.minimo, m)],
        d.fecha === hoyAR() || d.cierre == null ? ["Último", money(d.ultimo, m)] : ["Cierre", money(d.cierre, m)],
        d.cierre_anterior != null && ["Cierre anterior", money(d.cierre_anterior, m)],
        d.variacion_pct != null && ["Variación", pct(d.variacion_pct), cls(d.variacion_pct)],
      ];
    }
  } else if (data && !intradia && "cierres" in data) {
    const d = data as HistorialDiario;
    pts = d.cierres.map((c) => {
      const x = Date.parse(c.fecha + "T17:00:00-03:00");
      return { x, y: c.cierre, label: <><b>{money(c.cierre, m)}</b><br />{diaCorto(c.fecha)}<br /><small>Máx {num(c.maximo)} · Mín {num(c.minimo)}</small></> };
    });
    const ticks: { x: number; label: string }[] = [];
    for (let i = 0; pts.length && i < 5; i++) {
      const p = pts[Math.round((i * (pts.length - 1)) / 4)];
      if (!ticks.length || ticks[ticks.length - 1].x !== p.x) {
        ticks.push({ x: p.x, label: new Date(p.x).toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", timeZone: TZ }) });
      }
    }
    opt = { xTicks: ticks, aria: `Cierres diarios de ${a.ticker}`, vacio: "Todavía no hay cierres guardados para este período." };
    const c = d.cierres;
    if (c.length) {
      celdas = [
        ["Período", `${diaCorto(c[0].fecha)} → ${diaCorto(c[c.length - 1].fecha)}`],
        ["Ruedas", c.length], ["Máximo", money(d.maximo, m)], ["Mínimo", money(d.minimo, m)],
        ["Último cierre", money(c[c.length - 1].cierre, m)],
        d.variacion_pct != null && ["Variación", pct(d.variacion_pct), cls(d.variacion_pct)],
      ];
    }
  }

  return (
    <>
      <div className="chart-tools">
        <div className="tabs">
          {RANGOS.map(([v, l]) => (
            <button key={v} type="button" className={`tab${rango === v ? " active" : ""}`} onClick={() => { setRango(v); setDia(""); }}>{l}</button>
          ))}
        </div>
        <select aria-label="Ver otro día" value={rango === "dia" ? dia : ""} onChange={(e) => { if (e.target.value) { setRango("dia"); setDia(e.target.value); } }}>
          <option value="">Otro día…</option>
          {(intradia ? dias : []).map((f) => <option key={f} value={f}>{diaCorto(f)}</option>)}
          {rango === "dia" && dia && !dias.includes(dia) && <option value={dia}>{diaCorto(dia)}</option>}
        </select>
      </div>
      {error ? <div className="chart"><div className="msg">{error}</div></div> : <LineChart id="assetChart" pts={data ? pts : null} opt={opt} />}
      {fechaDia !== undefined && <TablaGrafico celdas={celdas} />}
    </>
  );
}
