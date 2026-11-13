"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { cls, fecha, money, num, signed } from "@/lib/format";
import type { FiltroOperaciones } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { ErrorCard, GananciasCard, Head, Loading } from "@/components/ui";

const VACIO: FiltroOperaciones = { desde: "", hasta: "", tipo: "", ticker: "" };

export default function OperacionesPage() {
  const { cuentaId, reloadKey } = useMe();
  const [filtro, setFiltro] = useState<FiltroOperaciones>(VACIO); // el que se aplicó
  const [form, setForm] = useState<FiltroOperaciones>(VACIO);     // lo que está escrito
  const { data, error, reload } = useAsync(
    () => Promise.all([api.operaciones(cuentaId, filtro), api.ganancias(cuentaId)]),
    [cuentaId, filtro, reloadKey],
  );
  const set = (k: keyof FiltroOperaciones) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <Head title="Operaciones" sub="Historial ordenado por fecha descendente" />
      <form className="card tools" noValidate style={{ marginBottom: 16 }}
        onSubmit={(e) => { e.preventDefault(); setFiltro({ ...form, ticker: form.ticker.trim() }); }}>
        <label className="muted" style={{ fontSize: 13 }}>Desde <input type="date" value={form.desde} onChange={set("desde")} /></label>
        <label className="muted" style={{ fontSize: 13 }}>Hasta <input type="date" value={form.hasta} onChange={set("hasta")} /></label>
        <select aria-label="Tipo" value={form.tipo} onChange={set("tipo")}>
          <option value="">Compras y ventas</option><option value="compra">Compras</option><option value="venta">Ventas</option>
        </select>
        <input className="search" style={{ maxWidth: 160 }} placeholder="Ticker" value={form.ticker} onChange={set("ticker")} />
        <button className="btn btn-primary btn-sm" type="submit">Filtrar</button>
        <button className="btn btn-ghost btn-sm" type="button" onClick={() => { setForm(VACIO); setFiltro(VACIO); }}>Limpiar</button>
      </form>

      {error ? <ErrorCard message={error} onRetry={reload} /> : !data ? <Loading /> : (() => {
        const [res, gan] = data;
        return (
          <>
            <div className="grid g3" style={{ marginBottom: 16 }}>
              <div className="card kpi"><small>Operaciones en el período</small><strong>{res.cantidad}</strong></div>
              <div className="card kpi"><small>Comisiones pagadas (ARS)</small><strong>{money(res.total_comisiones.ARS, "ARS")}</strong></div>
              <div className="card kpi"><small>Comisiones pagadas (USD)</small><strong>{money(res.total_comisiones.USD, "USD")}</strong></div>
            </div>
            <div className="card table-wrap">
              <table className="mt">
                <thead>
                  <tr><th className="hm">N°</th><th className="hm">Fecha</th><th className="hm">Operación</th><th>Activo</th><th className="num hm">Cantidad</th><th className="num hm">Precio</th><th className="num hm">Comisión</th><th className="num">Total</th><th className="num hm">Ganancia realizada</th></tr>
                </thead>
                <tbody>
                  {res.operaciones.length ? res.operaciones.map((o) => {
                    const compra = o.tipo === "compra";
                    return (
                      <tr key={o.id}>
                        <td className="hm">#{o.id}</td>
                        <td className="hm">{fecha(o.fecha)}</td>
                        <td className="hm"><span className={`pill ${compra ? "up" : "down"}`}>{compra ? "Compra" : "Venta"}</span></td>
                        <td>
                          <span className="sym">{o.ticker}</span>
                          <div className="sname only-m"><span className={compra ? "up" : "down"}>{compra ? "Compra" : "Venta"}</span> · {num(o.cantidad)} u. · {fecha(o.fecha)}</div>
                        </td>
                        <td className="num hm">{num(o.cantidad)}</td>
                        <td className="num hm">{money(o.precio_unitario, o.moneda)}</td>
                        <td className="num hm">{money(o.comision, o.moneda)}</td>
                        <td className="num"><b>{money(o.total, o.moneda)}</b></td>
                        <td className={`num hm ${cls(o.ganancia_realizada)}`}>{o.ganancia_realizada != null ? signed(o.ganancia_realizada, o.moneda) : "—"}</td>
                      </tr>
                    );
                  }) : <tr><td colSpan={9}><div className="empty">No hay operaciones con esos filtros.</div></td></tr>}
                </tbody>
              </table>
            </div>
            <GananciasCard gan={gan} />
          </>
        );
      })()}
    </>
  );
}
