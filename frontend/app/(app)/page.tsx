"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cls, compacto, money, pct, signed } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { DonutSvg, Legend, Sparkline } from "@/components/charts";
import { CashButton, composicionParts, DolaresCardAuto, InstallBanner, PortfolioChartCard } from "@/components/cards";
import { ErrorCard, Loading, MercadoPill, MontoHero, VarPill } from "@/components/ui";
import type { Activo } from "@/lib/types";

const CLAVE_OCULTAR = "iolAula_ocultarMontos";

/** Mostrar u ocultar los montos del inicio (se recuerda en este dispositivo). */
function useOcultarMontos(): [boolean, () => void] {
  const [ocultar, setOcultar] = useState(false);
  useEffect(() => {
    queueMicrotask(() => {
      try { setOcultar(localStorage.getItem(CLAVE_OCULTAR) === "1"); } catch { /* sin almacenamiento */ }
    });
  }, []);
  const alternar = () => setOcultar((v) => {
    try { localStorage.setItem(CLAVE_OCULTAR, v ? "0" : "1"); } catch { /* sin almacenamiento */ }
    return !v;
  });
  return [ocultar, alternar];
}

const OJO = <path d="M2.4 12.8a1.6 1.6 0 0 1 0-1.6C3.5 9.2 7 5 12 5s8.5 4.2 9.6 6.2a1.6 1.6 0 0 1 0 1.6C20.5 14.8 17 19 12 19s-8.5-4.2-9.6-6.2z" />;

export default function InicioPage() {
  const { me, cuentaId, favs, activoById, reloadKey, liveTick } = useMe();
  const router = useRouter();
  const [ocultar, alternarOcultar] = useOcultarMontos();
  const { data, error, reload } = useAsync(
    () => Promise.all([api.cartera(cuentaId), api.masOperados(), api.sparklines(30)]),
    [cuentaId, reloadKey, liveTick],
  );
  if (error) return <ErrorCard message={error} onRetry={reload} />;
  if (!data) return <Loading />;

  const [cart, masOp, sparks] = data;
  const spark = Object.fromEntries(sparks.map((s) => [s.activo_id, s.cierres]));
  const top = masOp.slice(0, 5);
  const favList = favs.map(activoById).filter(Boolean) as Activo[];
  const tc = cart.tipo_cambio_mep, pat = cart.patrimonio_total_ars;
  const abrir = (id: number) => router.push(`/mercado/${id}`);
  const rowProps = (id: number) => ({
    tabIndex: 0, role: "link",
    onClick: () => abrir(id),
    onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrir(id); } },
  });

  // Inversiones: total (en pesos equivalentes) en el centro del gráfico, y el detalle al costado
  const parts = composicionParts(cart);
  const invertido = parts.reduce((s, p) => s + p.value, 0);
  const res = { ARS: 0, USD: 0 }, costo = { ARS: 0, USD: 0 };
  cart.tenencias.forEach((t) => { res[t.moneda] += t.resultado; costo[t.moneda] += t.valor_actual - t.resultado; });
  const rendARS = costo.ARS ? (res.ARS / costo.ARS) * 100 : 0;

  return (
    <div className={ocultar ? "montos-ocultos" : undefined}>
      <InstallBanner />
      <div className="home-head">
        <div className="brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="brand-mark" src="/icons/icon-192.png" alt="" />
          <span className="wordmark">IOL <span>Aula</span></span>
        </div>
        <MercadoPill />
      </div>

      <section className="hero">
        <div>
          <div className="hero-label">
            Hola, {me.nombre.split(" ")[0]}. Tu patrimonio
            <button type="button" className="hide-btn" onClick={alternarOcultar} aria-pressed={ocultar}
              aria-label={ocultar ? "Mostrar montos" : "Ocultar montos"} title={ocultar ? "Mostrar montos" : "Ocultar montos"}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                {ocultar ? <><path d="M3 3l18 18" /><path d="M10.6 5.1A9.9 9.9 0 0 1 12 5c5 0 8.5 4.2 9.6 6.2a1.6 1.6 0 0 1 0 1.6 16 16 0 0 1-2.8 3.5" /><path d="M6.6 6.6A15.6 15.6 0 0 0 2.4 11.2a1.6 1.6 0 0 0 0 1.6C3.5 14.8 7 19 12 19a9.6 9.6 0 0 0 5.4-1.6" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></> : <>{OJO}<circle cx="12" cy="12" r="3" /></>}
              </svg>
            </button>
          </div>
          <div className="hero-num">{ocultar ? "$ ••••••" : pat != null ? <MontoHero n={pat} cur="ARS" /> : "—"}</div>
          <div className="hero-sub">{ocultar ? "≈ US$ ••••" : pat != null && tc ? `≈ ${money(pat / tc, "USD").replace(/,\d+$/, "")} al dólar MEP de ${money(tc, "ARS")}` : ""}</div>
        </div>
        <CashButton saldos={cart.saldos_disponibles} oculto={ocultar} />
      </section>

      <div className="home-grid">
        <PortfolioChartCard title="Tu cartera" />

        <div className="card">
          <div className="ctitle"><h2>Inversiones</h2><Link href="/cartera" className="btn btn-ghost btn-sm">Ver cartera</Link></div>
          {invertido > 0 ? (
            <div className="invest">
              <DonutSvg parts={parts} centro={<><small>Invertido</small><b className="priv">{compacto(invertido, "ARS")}</b></>} />
              <div>
                <div className="invest-figs priv">
                  <div>
                    <b>{money(cart.total_valorizado.ARS, "ARS")}</b>
                    {cart.total_valorizado.USD > 0 && <> <span className="muted">y {money(cart.total_valorizado.USD, "USD")}</span></>}
                  </div>
                  <div className={cls(res.ARS)} style={{ fontSize: 14 }}>{signed(res.ARS, "ARS")} ({pct(rendARS)}) sin realizar</div>
                </div>
                <Legend parts={parts} />
              </div>
            </div>
          ) : (
            <div className="empty">Todavía no invertiste. <Link href="/mercado" className="btn btn-primary btn-sm">Explorar el mercado</Link></div>
          )}
        </div>

        <div className="card only-d">
          <div className="ctitle"><h2>Favoritos</h2><Link href="/mercado" className="btn btn-ghost btn-sm">Mercado</Link></div>
          {favList.length ? favList.map((a) => (
            <div key={a.id} className="home-row row-click" {...rowProps(a.id)}>
              <div><span className="sym">{a.ticker}</span><div className="sname">{a.nombre}</div></div>
              <Sparkline valores={spark[a.id]} actual={a.precio_actual} />
              <div className="r"><b>{money(a.precio_actual, a.moneda)}</b><div><VarPill a={a} /></div></div>
            </div>
          )) : <div className="empty">Marcá activos con ☆ en el mercado.</div>}
        </div>

        <div className="card">
          <div className="ctitle"><h2>Más operados esta semana</h2><Link href="/rankings" className="btn btn-ghost btn-sm">Rankings</Link></div>
          {top.length ? top.map((t) => (
            <div key={t.activo_id} className="home-row row-click" {...rowProps(t.activo_id)}>
              <div><span className="sym">{t.ticker}</span><div className="sname">{t.operaciones} {t.operaciones === 1 ? "operación" : "operaciones"}</div></div>
              <Sparkline valores={spark[t.activo_id]} />
              <div className="r"><b>{compacto(t.volumen, t.moneda)}</b><div className="sname">operado</div></div>
            </div>
          )) : <div className="empty">Sin operaciones en los últimos 7 días.</div>}
        </div>

        <DolaresCardAuto />
      </div>
    </div>
  );
}
