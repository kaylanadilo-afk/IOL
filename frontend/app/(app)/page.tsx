"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { money, TIPO_LBL } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { Sparkline } from "@/components/charts";
import {
  CashButton, DineroBotones, DineroDialog, InstallBanner, PatrimonioCard, PortfolioChartCard, type AccionDinero,
} from "@/components/cards";
import { Badge } from "@/components/AppShell";
import { IcoAlerta } from "@/components/icons";
import { ErrorCard, Loading, MercadoPill, MontoHero, RiskDots, StarButton, VarPill } from "@/components/ui";
import type { Activo } from "@/lib/types";

const CLAVE_OCULTAR = "iolAula_ocultarMontos";
const MAX_FAVORITOS = 10;

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

export default function InicioPage() {
  const { me, cuentaId, favs, activoById, reloadKey, liveTick, avisos } = useMe();
  const router = useRouter();
  const [ocultar, alternarOcultar] = useOcultarMontos();
  const [dinero, setDinero] = useState<AccionDinero | null>(null);
  const { data, error, reload } = useAsync(
    () => Promise.all([api.cartera(cuentaId), api.sparklines(30)]),
    [cuentaId, reloadKey, liveTick],
  );
  if (error) return <ErrorCard message={error} onRetry={reload} />;
  if (!data) return <Loading />;

  const [cart, sparks] = data;
  const spark = Object.fromEntries(sparks.map((s) => [s.activo_id, s.cierres]));
  const favList = favs.map(activoById).filter(Boolean) as Activo[];
  const tc = cart.tipo_cambio_mep, pat = cart.patrimonio_total_ars;
  const abrir = (id: number) => router.push(`/mercado/${id}`);

  return (
    <div className={ocultar ? "montos-ocultos" : undefined}>
      <InstallBanner />
      <div className="home-head">
        <div className="brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="brand-mark" src="/brand/zeno-mark.png" alt="" />
          <span className="wordmark">Zeno <span>Investments</span></span>
        </div>
        <div className="home-head-r">
          <Link href="/alertas" className="icon-btn only-m" aria-label={avisos ? `Alertas: ${avisos} avisos sin leer` : "Alertas de precios"}>
            <IcoAlerta /><Badge n={avisos} />
          </Link>
          <MercadoPill />
        </div>
      </div>

      <section className="hero">
        <div>
          <div className="hero-label">
            Hola, {me.nombre.split(" ")[0]}. Tu patrimonio
            <button type="button" className="hide-btn" onClick={alternarOcultar} aria-pressed={ocultar}
              aria-label={ocultar ? "Mostrar montos" : "Ocultar montos"} title={ocultar ? "Mostrar montos" : "Ocultar montos"}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                {ocultar
                  ? <><path d="M3 3l18 18" /><path d="M10.6 5.1A9.9 9.9 0 0 1 12 5c5 0 8.5 4.2 9.6 6.2a1.6 1.6 0 0 1 0 1.6 16 16 0 0 1-2.8 3.5" /><path d="M6.6 6.6A15.6 15.6 0 0 0 2.4 11.2a1.6 1.6 0 0 0 0 1.6C3.5 14.8 7 19 12 19a9.6 9.6 0 0 0 5.4-1.6" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></>
                  : <><path d="M2.4 12.8a1.6 1.6 0 0 1 0-1.6C3.5 9.2 7 5 12 5s8.5 4.2 9.6 6.2a1.6 1.6 0 0 1 0 1.6C20.5 14.8 17 19 12 19s-8.5-4.2-9.6-6.2z" /><circle cx="12" cy="12" r="3" /></>}
              </svg>
            </button>
          </div>
          <div className="hero-num">{ocultar ? "$ ******" : pat != null ? <MontoHero n={pat} cur="ARS" /> : "—"}</div>
          <div className="hero-sub">{ocultar ? "≈ US$ ******" : pat != null && tc ? `≈ ${money(pat / tc, "USD").replace(/,\d+$/, "")} al dólar MEP de ${money(tc, "ARS")}` : ""}</div>
        </div>
        <div className="cash-box">
          <CashButton saldos={cart.saldos_disponibles} oculto={ocultar} />
          <DineroBotones onAccion={setDinero} />
        </div>
      </section>

      <div className="home-grid">
        <div className="area-chart"><PortfolioChartCard title="Tu cartera" /></div>
        <div className="area-patri"><PatrimonioCard cart={cart} oculto={ocultar} /></div>

        <div className="card area-favs">
          <div className="ctitle">
            <h2>Favoritos {favList.length > 0 && <span className="muted count">{favList.length}</span>}</h2>
            <Link href="/mercado" className="btn btn-ghost btn-sm">{favList.length ? "Ir al mercado" : "Agregar favoritos"}</Link>
          </div>
          {favList.length ? (
            <div className="table-wrap">
              <table className="mt fav-table">
                <thead>
                  <tr><th /><th>Activo</th><th className="hm">Tipo</th><th className="num">Precio</th><th className="num">Var. día</th><th className="hm">30 días</th><th className="hm">Riesgo</th></tr>
                </thead>
                <tbody>
                  {favList.slice(0, MAX_FAVORITOS).map((a) => (
                    <tr key={a.id} className="row-click" tabIndex={0} onClick={() => abrir(a.id)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrir(a.id); } }}>
                      <td><StarButton a={a} /></td>
                      <td><span className="sym">{a.ticker}</span><div className="sname">{a.nombre}</div></td>
                      <td className="muted hm">{TIPO_LBL[a.tipo]}</td>
                      <td className="num"><b>{money(a.precio_actual, a.moneda)}</b></td>
                      <td className="num"><VarPill a={a} /></td>
                      <td className="hm"><Sparkline valores={spark[a.id]} actual={a.precio_actual} /></td>
                      <td className="hm"><RiskDots n={a.nivel_riesgo} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {favList.length > MAX_FAVORITOS && (
                <Link href="/mercado?favoritos=1" className="link-btn">Ver los {favList.length} favoritos en el mercado</Link>
              )}
            </div>
          ) : (
            <div className="empty">
              Marcá activos con la estrella en el mercado para seguirlos desde acá.
              <div><Link href="/mercado" className="btn btn-primary btn-sm">Explorar el mercado</Link></div>
            </div>
          )}
        </div>
      </div>

      {dinero && <DineroDialog accion={dinero} onClose={() => setDinero(null)} />}
    </div>
  );
}
