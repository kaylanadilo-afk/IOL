"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { compacto, iniciales } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { ErrorCard, Loading } from "@/components/ui";
import { IcoAdmin, IcoAjustes, IcoAlerta, IcoChevron, IcoLista, IcoMep, IcoOperaciones } from "@/components/icons";

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
  // [ruta, ícono, texto, se ve en la compu] (en la compu el resto ya está en el menú lateral)
  const secciones: [string, () => React.JSX.Element, string, boolean][] = [
    ["/movimientos", IcoLista, "Movimientos de la cuenta", true], ["/operaciones", IcoOperaciones, "Operaciones", false],
    ["/alertas", IcoAlerta, "Alertas de precios", false], ["/mep", IcoMep, "Dólar MEP", false],
  ];
  if (me.es_admin) secciones.push(["/admin", IcoAdmin, "Administración", false]);
  secciones.push(["/perfil/configuracion", IcoAjustes, "Configuración", true]);

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
        {secciones.map(([href, Ico, label, enCompu]) => (
          <Link key={href} href={href} className={`menu-item${enCompu ? "" : " only-m"}`}><span className="mi"><Ico /></span>{label}<span className="chev"><IcoChevron /></span></Link>
        ))}
      </div>

    </>
  );
}

