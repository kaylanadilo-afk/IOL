"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { cls, money, num, pct, signed, TIPO_LBL } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { Donut } from "@/components/charts";
import { composicionParts, PortfolioChartCard } from "@/components/cards";
import { ErrorCard, Head, Loading } from "@/components/ui";

export default function CarteraPage() {
  const { cuentaId, reloadKey, liveTick } = useMe();
  const router = useRouter();
  const { data: cart, error, reload } = useAsync(() => api.cartera(cuentaId), [cuentaId, reloadKey, liveTick]);
  const head = <Head title="Mi cartera" sub="Tus tenencias valorizadas a precio actual" />;
  if (error) return <>{head}<ErrorCard message={error} onRetry={reload} /></>;
  if (!cart) return <>{head}<Loading /></>;

  return (
    <>
      {head}
      <div className="grid g4">
        <div className="card kpi"><small>Valorizado en pesos</small><strong>{money(cart.total_valorizado.ARS, "ARS")}</strong></div>
        <div className="card kpi"><small>Valorizado en dólares</small><strong>{money(cart.total_valorizado.USD, "USD")}</strong></div>
        <div className="card kpi"><small>Saldo disponible</small><strong>{money(cart.saldos_disponibles.ARS, "ARS")}</strong><span className="sub muted">+ {money(cart.saldos_disponibles.USD, "USD")}</span></div>
        <div className="card kpi">
          <small>Patrimonio total</small>
          <strong>{cart.patrimonio_total_ars != null ? money(cart.patrimonio_total_ars, "ARS") : "—"}</strong>
          <span className="sub muted">USD a MEP {cart.tipo_cambio_mep ? money(cart.tipo_cambio_mep, "ARS") : "—"}</span>
        </div>
      </div>

      <div className="card table-wrap" style={{ marginTop: 12 }}>
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

      <div className="home-grid" style={{ marginTop: 12 }}>
        <PortfolioChartCard title="Valor de la cartera" />
        <div className="card">
          <div className="ctitle"><h2>Composición por tipo</h2></div>
          <Donut parts={composicionParts(cart)} />
          <p className="muted" style={{ fontSize: 12, margin: "8px 0 0" }}>Los activos en dólares se pasan a pesos al dólar MEP.</p>
        </div>
      </div>
    </>
  );
}
