"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { compacto, iniciales } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { ErrorCard, Loading } from "@/components/ui";

export default function PerfilPage() {
  const { me, cuentaId, favs, reloadKey } = useMe();
  const { data, error, reload } = useAsync(
    () => Promise.all([api.cartera(cuentaId), api.operaciones(cuentaId)]),
    [cuentaId, reloadKey],
  );

  if (error) return <ErrorCard message={error} onRetry={reload} />;
  if (!data) return <Loading />;
  const [cart, ops] = data;
  const comitente = me.cuenta?.numero_comitente;

  // En el celular, las secciones que no están en el menú de abajo
  const secciones: [string, string, string][] = [["/operaciones", "☰", "Operaciones"], ["/movimientos", "⇄", "Movimientos y depósitos"], ["/mep", "$", "Dólar MEP"], ["/rankings", "▲", "Rankings del mercado"]];
  if (me.es_admin) secciones.push(["/admin", "⚙", "Administración"]);
  secciones.push(["/perfil/configuracion", "⚙", "Configuración"]);

  return (
    <>
      <section className="pf-hero">
        <div className="avatar avatar-lg">{iniciales(me.nombre)}</div>
        <div style={{ minWidth: 0 }}>
          <h1 className="pf-name">{me.nombre}</h1>
          <div className="pf-mail">{me.email}</div>
          <div className="chips">
            <span className={`chip c-${me.perfil_riesgo}`}>Perfil {me.perfil_riesgo}</span>
            <span className="chip">Comitente N° {comitente}</span>
            {me.es_admin && <span className="chip">Administrador</span>}
          </div>
        </div>
        <div className="pf-stats">
          <div><b>{cart.patrimonio_total_ars != null ? compacto(cart.patrimonio_total_ars, "ARS") : "—"}</b><small>patrimonio</small></div>
          <div><b>{cart.tenencias.length}</b><small>activos</small></div>
          <div><b>{ops.cantidad}</b><small>operaciones</small></div>
          <div><b>{favs.length}</b><small>favoritos</small></div>
        </div>
        <Link href="/perfil/configuracion" className="pf-gear" aria-label="Configuración" title="Configuración">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
          </svg>
        </Link>
      </section>

      <div className="card menu-list only-m" style={{ padding: "2px 16px", marginBottom: 12 }}>
        {secciones.map(([href, ico, label]) => (
          <Link key={href} href={href} className="menu-item"><span className="mi">{ico}</span>{label}<span className="chev">›</span></Link>
        ))}
      </div>

    </>
  );
}

