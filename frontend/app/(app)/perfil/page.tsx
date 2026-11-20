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

  // Secciones que no están en el menú de abajo del celular, y la configuración
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
      </section>

      <div className="card menu-list" style={{ padding: "2px 16px", marginBottom: 12 }}>
        {secciones.map(([href, ico, label]) => (
          // En la compu esas secciones ya están en el menú lateral: ahí solo queda Configuración
          <Link key={href} href={href} className={`menu-item${href === "/perfil/configuracion" ? "" : " only-m"}`}><span className="mi">{ico}</span>{label}<span className="chev">›</span></Link>
        ))}
      </div>

    </>
  );
}

