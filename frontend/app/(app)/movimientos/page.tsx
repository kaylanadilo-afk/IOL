"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { api } from "@/lib/api";
import { cls, fecha, money, signed } from "@/lib/format";
import type { Movimiento } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { DineroBotones, DineroDialog, type AccionDinero } from "@/components/cards";
import { ErrorCard, Head, Loading } from "@/components/ui";

const TIPO: Record<Movimiento["tipo"], string> = { deposito: "Ingreso de dinero", extraccion: "Retiro de dinero", dividendo: "Cobro de dividendo" };

export default function MovimientosPage() {
  // useSearchParams necesita un Suspense alrededor para poder prerenderizar la página
  return <Suspense fallback={<Loading />}><Movimientos /></Suspense>;
}

function Movimientos() {
  const { cuentaId, reloadKey } = useMe();
  const router = useRouter();
  const path = usePathname();
  const params = useSearchParams();
  // ?accion=ingresar o ?accion=retirar abre la ventana directamente (desde el menú del celular)
  const accionUrl = params.get("accion");
  const dinero: AccionDinero | null = accionUrl === "ingresar" || accionUrl === "retirar" ? accionUrl : null;
  const abrir = (a: AccionDinero | null) => router.replace(a ? `${path}?accion=${a}` : path, { scroll: false });

  const { data, error, reload } = useAsync(
    () => Promise.all([api.cuenta(cuentaId), api.movimientos(cuentaId)]),
    [cuentaId, reloadKey],
  );

  const head = <Head title="Movimientos" sub="Ingresos, retiros y dividendos de tu cuenta" extra={<DineroBotones onAccion={abrir} verMovimientos={false} />} />;
  if (error) return <>{head}<ErrorCard message={error} onRetry={reload} /></>;
  if (!data) return <>{head}<Loading /></>;
  const [c, movs] = data;
  // Del más reciente al más antiguo
  const lista = [...movs].sort((a, b) => Date.parse(b.fecha) - Date.parse(a.fecha) || b.id - a.id);

  return (
    <>
      {head}
      <div className="grid g3 mov-kpis">
        <div className="card kpi"><small>Saldo en pesos</small><strong>{money(c.saldo_ars, "ARS")}</strong></div>
        <div className="card kpi"><small>Saldo en dólares</small><strong>{money(c.saldo_usd, "USD")}</strong></div>
        <div className="card kpi sim-kpi">
          <small>Modo de operación</small>
          <strong className="sim-badge">Simulado</strong>
          <span className="sub muted">Zeno todavía no está conectado a bancos ni medios de pago: los ingresos y retiros cambian el saldo en la app, pero no mueven dinero real.</span>
        </div>
      </div>

      <div className="card table-wrap">
        <table className="mt">
          <thead>
            <tr><th>Fecha y hora</th><th>Tipo</th><th className="hm">Descripción</th><th className="num">Importe</th><th>Estado</th></tr>
          </thead>
          <tbody>
            {lista.length ? lista.map((m) => {
              const sign = m.tipo === "extraccion" ? -1 : 1;
              const simulado = m.tipo !== "dividendo";
              return (
                <tr key={m.id}>
                  <td className="nowrap">{fecha(m.fecha)}</td>
                  <td><b>{TIPO[m.tipo]}</b><div className="sname only-m">{m.descripcion}</div></td>
                  <td className="muted hm">{m.descripcion}</td>
                  <td className={`num nowrap ${cls(sign)}`}>{signed(sign * m.monto, m.moneda)}</td>
                  <td>
                    <span className={`pill ${sign > 0 ? "up" : "neutral"}`}>{sign > 0 ? "Acreditado" : "Debitado"}</span>
                    {simulado && <span className="pill neutral sim-pill">Simulado</span>}
                  </td>
                </tr>
              );
            }) : <tr><td colSpan={5}><div className="empty">Sin movimientos todavía. Ingresá dinero para empezar a operar.</div></td></tr>}
          </tbody>
        </table>
      </div>

      {dinero && <DineroDialog accion={dinero} onClose={() => abrir(null)} onListo={reload} />}
    </>
  );
}
