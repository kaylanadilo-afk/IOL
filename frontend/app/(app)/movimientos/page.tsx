"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { cls, fecha, money, MOV_LBL, signed } from "@/lib/format";
import type { Moneda } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { ErrorCard, Head, Loading } from "@/components/ui";

export default function MovimientosPage() {
  const { cuentaId, reloadKey } = useMe();
  const { toast } = useUI();
  const [tipo, setTipo] = useState<"depositos" | "extracciones">("depositos");
  const [moneda, setMoneda] = useState<Moneda>("ARS");
  const [monto, setMonto] = useState("100000");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const { data, error, reload } = useAsync(
    () => Promise.all([api.cuenta(cuentaId), api.movimientos(cuentaId)]),
    [cuentaId, reloadKey],
  );

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const n = Number(monto);
    if (!(n > 0)) return setMsg("El monto tiene que ser mayor a 0.");
    setBusy(true);
    setMsg("");
    try {
      const m = await api.moverDinero(cuentaId, tipo, moneda, n);
      toast(`${m.tipo === "deposito" ? "Depósito" : "Extracción"} de ${money(m.monto, m.moneda)} registrada.`);
      reload();
    } catch (err) {
      setMsg((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const head = <Head title="Movimientos" sub="Depósitos, extracciones y dividendos" />;
  if (error) return <>{head}<ErrorCard message={error} onRetry={reload} /></>;
  if (!data) return <>{head}<Loading /></>;
  const [c, movs] = data;

  return (
    <>
      {head}
      <div className="grid g3" style={{ marginBottom: 16 }}>
        <div className="card kpi"><small>Saldo en pesos</small><strong>{money(c.saldo_ars, "ARS")}</strong></div>
        <div className="card kpi"><small>Saldo en dólares</small><strong>{money(c.saldo_usd, "USD")}</strong></div>
        <form className="card" noValidate onSubmit={onSubmit}>
          <div className="inline-form">
            <div className="field">
              <label htmlFor="cashTipo">Operación</label>
              <select id="cashTipo" value={tipo} onChange={(e) => setTipo(e.target.value as typeof tipo)}>
                <option value="depositos">Depositar</option><option value="extracciones">Extraer</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="cashMon">Moneda</label>
              <select id="cashMon" value={moneda} onChange={(e) => setMoneda(e.target.value as Moneda)}><option>ARS</option><option>USD</option></select>
            </div>
            <div className="field">
              <label htmlFor="cashMonto">Monto</label>
              <input id="cashMonto" type="number" min={0.01} step={0.01} value={monto} onChange={(e) => setMonto(e.target.value)} />
            </div>
            <button className="btn btn-primary" type="submit" disabled={busy}>Confirmar</button>
          </div>
          <div className="form-msg" aria-live="polite">{msg}</div>
        </form>
      </div>
      <div className="card table-wrap">
        <table className="mt">
          <thead><tr><th className="hm">Fecha</th><th>Tipo</th><th className="hm">Detalle</th><th className="hm">Moneda</th><th className="num">Monto</th></tr></thead>
          <tbody>
            {movs.length ? movs.map((m) => {
              const sign = m.tipo === "extraccion" ? -1 : 1;
              return (
                <tr key={m.id}>
                  <td className="hm">{fecha(m.fecha)}</td>
                  <td><b>{MOV_LBL[m.tipo]}</b><div className="sname only-m">{fecha(m.fecha)}</div></td>
                  <td className="muted hm">{m.descripcion}</td>
                  <td className="hm">{m.moneda}</td>
                  <td className={`num ${cls(sign)}`}>{signed(sign * m.monto, m.moneda)}</td>
                </tr>
              );
            }) : <tr><td colSpan={5}><div className="empty">Sin movimientos. Hacé tu primer depósito.</div></td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
