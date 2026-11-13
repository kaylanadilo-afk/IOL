"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { money, num, RIESGO_MAX, TIPO_LBL } from "@/lib/format";
import type { Moneda, TipoActivo } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { Sparkline } from "@/components/charts";
import { ErrorCard, EstadoPill, Head, Loading, RiskDots, StarButton, VarPill } from "@/components/ui";

const TABS: [string, string][] = [["", "Todos"], ["fav", "★ Favoritos"], ["accion", "Acciones"], ["cedear", "CEDEARs"], ["bono", "Bonos"]];

export default function MercadoPage() {
  const { me, cuentaId, favs, activoById, reloadKey } = useMe();
  const router = useRouter();
  const [tipo, setTipo] = useState<TipoActivo | "">("");
  const [soloFavs, setSoloFavs] = useState(false);
  const [moneda, setMoneda] = useState<Moneda | "">("");
  const [search, setSearch] = useState("");

  // El filtro por tipo y moneda lo resuelve la API: GET /activos?tipo=&moneda=  (HU2)
  const { data, error, reload } = useAsync(
    () => Promise.all([api.activos({ tipo, moneda }), api.cartera(cuentaId), api.sparklines(30)]),
    [tipo, moneda, cuentaId, reloadKey],
  );

  const head = <Head title="Mercado" sub={`Tocá un activo para ver el detalle y operar. Tu perfil ${me.perfil_riesgo} permite riesgo hasta ${RIESGO_MAX[me.perfil_riesgo]}.`} />;
  if (error) return <>{head}<ErrorCard message={error} onRetry={reload} /></>;

  let rows: React.ReactNode = null;
  if (data) {
    const [lista, cart, sparks] = data;
    const spark = Object.fromEntries(sparks.map((s) => [s.activo_id, s.cierres]));
    const held = Object.fromEntries(cart.tenencias.map((t) => [t.activo_id, t.cantidad]));
    const q = search.trim().toLowerCase();
    // Con precios reales, el catálogo del contexto se actualiza cada 30 s: se usan esos precios
    const list = lista.map((a) => activoById(a.id) ?? a).filter((a) => {
      if (soloFavs && !favs.includes(a.id)) return false;
      return !q || `${a.ticker} ${a.nombre}`.toLowerCase().includes(q);
    });
    const abrir = (id: number) => router.push(`/mercado/${id}`);
    rows = list.length ? list.map((a) => (
      <tr key={a.id} className="row-click" tabIndex={0} onClick={() => abrir(a.id)}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrir(a.id); } }}>
        <td><StarButton a={a} /></td>
        <td><span className="sym">{a.ticker}</span><div className="sname">{a.nombre}</div></td>
        <td className="muted hm">{TIPO_LBL[a.tipo]}</td>
        <td className="muted hm">{a.moneda}</td>
        <td className="num"><b>{money(a.precio_actual, a.moneda)}</b></td>
        <td className="num"><VarPill a={a} /></td>
        <td className="hm"><Sparkline valores={spark[a.id]} actual={a.precio_actual} /></td>
        <td className="hm"><RiskDots n={a.nivel_riesgo} /></td>
        <td className="hm"><EstadoPill a={a} /></td>
        <td className="num hm">{held[a.id] ? <span className="pill neutral">{num(held[a.id])} u.</span> : <span className="muted">—</span>}</td>
      </tr>
    )) : <tr><td colSpan={10}><div className="empty">No se encontraron activos.</div></td></tr>;
  }

  return (
    <>
      {head}
      <div className="tools">
        <div className="tabs">
          {TABS.map(([t, l]) => {
            const active = t === "fav" ? soloFavs : !soloFavs && tipo === t;
            return (
              <button key={t} type="button" className={`tab${active ? " active" : ""}`} onClick={() => {
                if (t === "fav") { setSoloFavs(true); setTipo(""); } else { setSoloFavs(false); setTipo(t as TipoActivo | ""); }
              }}>{l}</button>
            );
          })}
        </div>
        <select aria-label="Moneda" value={moneda} onChange={(e) => setMoneda(e.target.value as Moneda | "")}>
          <option value="">Todas las monedas</option>
          <option value="ARS">Pesos (ARS)</option>
          <option value="USD">Dólares (USD)</option>
        </select>
        <input className="search" type="search" placeholder="Buscar por ticker o nombre…" aria-label="Buscar activo" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      {data ? (
        <div className="card table-wrap">
          <table className="mt">
            <thead>
              <tr>
                <th /><th>Activo</th><th className="hm">Tipo</th><th className="hm">Moneda</th><th className="num">Precio</th><th className="num">Var. día</th>
                <th className="hm">30 días</th><th className="hm">Riesgo</th><th className="hm">Estado</th><th className="num hm">Tenencia</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
      ) : <Loading />}
    </>
  );
}
