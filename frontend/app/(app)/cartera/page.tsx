"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { cls, money, num, pct, signed, TIPO_LBL } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { PieChart } from "@/components/charts";
import { distribucion, PortfolioChartCard } from "@/components/cards";
import type { Cartera } from "@/lib/types";
import { ErrorCard, Head, Loading } from "@/components/ui";

const ICO = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true } as const;
const IcoPatrimonio = () => <svg {...ICO}><path d="M3 10.5 12 4l9 6.5" /><path d="M5 10v9h14v-9" /><path d="M9.5 19v-5h5v5" /></svg>;
const IcoPesos = () => <svg {...ICO}><path d="M3 17l5.5-5.5 4 4L21 7" /><path d="M15 7h6v6" /></svg>;
const IcoDolares = () => <svg {...ICO}><path d="M12 3v18" /><path d="M16.5 7.5c0-1.7-2-3-4.5-3s-4.5 1.3-4.5 3 2 2.6 4.5 3 4.5 1.3 4.5 3-2 3-4.5 3-4.5-1.3-4.5-3" /></svg>;
const IcoCaja = () => <svg {...ICO}><rect x="3" y="6" width="18" height="13" rx="2.5" /><path d="M3 10h18" /><path d="M16 14.5h2" /></svg>;

export default function CarteraPage() {
  const { cuentaId, reloadKey, liveTick } = useMe();
  const router = useRouter();
  const { data: cart, error, reload } = useAsync(() => api.cartera(cuentaId), [cuentaId, reloadKey, liveTick]);
  const head = <Head title="Mi cartera" sub="Tus tenencias valorizadas a precio actual" />;
  if (error) return <>{head}<ErrorCard message={error} onRetry={reload} /></>;
  if (!cart) return <>{head}<Loading /></>;

  // Resultado sin realizar por moneda (valor actual contra lo que costó)
  const res = { ARS: 0, USD: 0 }, costo = { ARS: 0, USD: 0 };
  cart.tenencias.forEach((t) => { res[t.moneda] += t.resultado; costo[t.moneda] += t.valor_actual - t.resultado; });
  const rend = (m: "ARS" | "USD") => (costo[m] ? (res[m] / costo[m]) * 100 : 0);
  const tc = cart.tipo_cambio_mep, pat = cart.patrimonio_total_ars;

  return (
    <>
      {head}

      {/* Primero, cómo viene el valor de la cartera */}
      <div className="home-grid">
        <PortfolioChartCard title="Valor de la cartera" />
        <DistribucionCartera cart={cart} />
      </div>

      <div className="kpis">
        <div className="kpi2 feat">
          <span className="ico"><IcoPatrimonio /></span>
          <small>Patrimonio total</small>
          <strong>{pat != null ? money(pat, "ARS") : "—"}</strong>
          <span className="foot">{pat != null && tc ? `≈ ${money(pat / tc, "USD").replace(/,\d+$/, "")} · MEP ${money(tc, "ARS")}` : "Sin cotización MEP"}</span>
        </div>
        <div className="kpi2">
          <span className="ico"><IcoPesos /></span>
          <small>Invertido en pesos</small>
          <strong>{money(cart.total_valorizado.ARS, "ARS")}</strong>
          <span className="foot">
            {costo.ARS ? <><span className={`pill ${res.ARS >= 0 ? "up" : "down"}`}>{pct(rend("ARS"))}</span><span className={cls(res.ARS)}>{signed(res.ARS, "ARS")}</span></> : "Sin tenencias en pesos"}
          </span>
        </div>
        <div className="kpi2">
          <span className="ico usd"><IcoDolares /></span>
          <small>Invertido en dólares</small>
          <strong>{money(cart.total_valorizado.USD, "USD")}</strong>
          <span className="foot">
            {costo.USD ? <><span className={`pill ${res.USD >= 0 ? "up" : "down"}`}>{pct(rend("USD"))}</span><span className={cls(res.USD)}>{signed(res.USD, "USD")}</span></> : "Sin tenencias en dólares"}
          </span>
        </div>
        <div className="kpi2">
          <span className="ico cash"><IcoCaja /></span>
          <small>Disponible para operar</small>
          <strong>{money(cart.saldos_disponibles.ARS, "ARS")}</strong>
          <span className="foot">y {money(cart.saldos_disponibles.USD, "USD")}</span>
        </div>
      </div>

      <div className="cart-sec">
        <h2>Tenencias</h2>
        <span className="muted" style={{ fontSize: 13 }}>{cart.tenencias.length} {cart.tenencias.length === 1 ? "activo" : "activos"}</span>
      </div>
      <div className="card table-wrap">
        <table className="mt">
          <thead>
            <tr><th>Activo</th><th className="hm">Tipo</th><th className="num hm">Cantidad</th><th className="num hm">Precio prom.</th><th className="num hm">Precio actual</th><th className="num">Valor actual</th><th className="num hm">Resultado</th><th className="num">Rend. %</th></tr>
          </thead>
          <tbody>
            {cart.tenencias.length ? cart.tenencias.map((t) => (
              <tr key={t.activo_id} className="row-click" tabIndex={0} onClick={() => router.push(`/mercado/${t.activo_id}`)}
                onKeyDown={(e) => { if (e.key === "Enter") router.push(`/mercado/${t.activo_id}`); }}>
                <td><span className="sym">{t.ticker}</span><div className="sname"><span className="only-m">{num(t.cantidad)} u. · </span>{t.nombre}</div></td>
                <td className="muted hm">{TIPO_LBL[t.tipo]}</td>
                <td className="num hm">{num(t.cantidad)}</td>
                <td className="num hm">{money(t.precio_promedio, t.moneda)}</td>
                <td className="num hm">{money(t.precio_actual, t.moneda)}</td>
                <td className="num"><b>{money(t.valor_actual, t.moneda)}</b></td>
                <td className={`num hm ${cls(t.resultado)}`}>{signed(t.resultado, t.moneda)}</td>
                <td className="num"><span className={`pill ${t.rendimiento_pct >= 0 ? "up" : "down"}`}>{pct(t.rendimiento_pct)}</span></td>
              </tr>
            )) : (
              <tr><td colSpan={8}><div className="empty">Todavía no compraste activos. <Link href="/mercado" className="btn btn-primary btn-sm">Ir al mercado</Link></div></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

/* ===================== DISTRIBUCIÓN POR TIPO (torta) ===================== */
function DistribucionCartera({ cart }: { cart: Cartera }) {
  const [elegida, setElegida] = useState<string | null>(null);
  const cats = distribucion(cart);
  const total = cats.reduce((s, c) => s + c.value, 0);
  const sel = cats.find((c) => c.key === elegida) ?? null;
  const porc = (v: number) => `${((v / total) * 100).toFixed(1).replace(".", ",")}%`;
  return (
    <div className="card">
      <div className="ctitle"><h2>Distribución por tipo</h2></div>
      {total > 0 ? (
        <>
          <div className="pie-wrap">
            <PieChart parts={cats} selected={elegida} onSelect={setElegida} aria="Distribución del valor de la cartera por tipo de activo" />
            <div className="pie-legend">
              {cats.map((c) => (
                <button key={c.key} type="button" className={`pie-leg${elegida === c.key ? " on" : ""}`}
                  aria-pressed={elegida === c.key} onClick={() => setElegida(elegida === c.key ? null : c.key)}>
                  <span className="sw" style={{ background: c.color }} />{c.label}<b>{porc(c.value)}</b>
                </button>
              ))}
            </div>
          </div>
          {sel ? (
            <div className="pie-detalle">
              <div className="pie-detalle-head"><b>{sel.label}</b><span className="muted">{money(sel.value, "ARS")} · {porc(sel.value)} del total</span></div>
              {sel.items.sort((x, y) => y.valorArs - x.valorArs).map((i) => (
                <div key={i.clave} className="list-row">
                  <span><b>{i.titulo}</b><div className="sname">{i.detalle}</div></span>
                  <span className="r"><b>{i.nativo}</b><div className="sname">{porc(i.valorArs)}</div></span>
                </div>
              ))}
            </div>
          ) : <p className="muted pie-ayuda">Tocá una categoría para ver qué activos la componen.</p>}
          <p className="muted" style={{ fontSize: 12, margin: "8px 0 0" }}>
            Valor de cada tipo sobre el total (incluye el dinero disponible). Los dólares se pasan a pesos al MEP{cart.tipo_cambio_mep ? ` de ${money(cart.tipo_cambio_mep, "ARS")}` : ""}.
          </p>
        </>
      ) : <div className="empty">Todavía no tenés inversiones ni saldo.</div>}
    </div>
  );
}
