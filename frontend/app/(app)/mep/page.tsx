"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FEE, money, num, round2 } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { DolaresCardAuto } from "@/components/cards";
import { ErrorCard, Head, Loading, SummaryRows } from "@/components/ui";

export default function MepPage() {
  const { cuentaId, reloadKey, mercado, setMercado, activoByTicker } = useMe();
  const { confirm, toast } = useUI();
  const [amt, setAmt] = useState("150000");
  const [msg, setMsg] = useState("");
  const [nonce, setNonce] = useState(0);
  const { data, error, reload } = useAsync(
    () => Promise.all([api.cuenta(cuentaId), api.mercado(), api.activos({ tipo: "bono" })]),
    [cuentaId, reloadKey, nonce],
  );
  useEffect(() => { if (data) setMercado(data[1]); }, [data, setMercado]);

  const head = <Head title="Dólar MEP" sub="Comprás AL30 en pesos y lo vendés como AL30D en dólares, en una sola operación" />;
  if (error) return <>{head}<ErrorCard message={error} onRetry={reload} /></>;
  if (!data) return <>{head}<Loading /></>;

  const [c, m0, bonos] = data;
  const m = mercado ?? m0;
  // Precios frescos de AL30/AL30D (con precios reales, el contexto los actualiza cada 30 s)
  const bono = (t: string) => activoByTicker(t) ?? bonos.find((b) => b.ticker === t);
  const al30 = bono("AL30"), al30d = bono("AL30D");
  if (!al30 || !al30d) {
    return <>{head}<div className="card empty">Faltan los activos AL30 y/o AL30D en el catálogo. Cargalos desde Administración.</div></>;
  }
  const tc = al30.precio_actual / al30d.precio_actual;

  const monto = Number(amt) || 0;
  const n = Math.floor(monto / (al30.precio_actual * (1 + FEE)));
  const bruto = round2(n * al30.precio_actual);
  const pesos = bruto + round2(bruto * FEE);
  const brutoUsd = round2(n * al30d.precio_actual);
  const usd = brutoUsd - round2(brutoUsd * FEE);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!(monto > 0)) return setMsg("Ingresá un monto mayor a 0.");
    if (n < 1) return setMsg("El monto no alcanza para 1 nominal de AL30.");
    confirm({
      title: "Confirmar dólar MEP",
      body: <SummaryRows rows={[["1) Compra AL30", `${num(n)} nominales`], ["2) Venta AL30D", `${num(n)} nominales`], ["Pagás (aprox.)", money(pesos, "ARS")], ["Recibís (aprox.)", money(usd, "USD"), true]]} />,
      okText: "Confirmar",
      onOk: () => {
        api.mep(cuentaId, monto)
          .then((r) => {
            confirm({
              title: "Dólar MEP realizado",
              body: <SummaryRows rows={[["Tipo de cambio aplicado", money(r.tipo_cambio, "ARS")], ["Nominales", num(r.cantidad_nominales)], ["Pesos debitados", money(r.pesos_debitados, "ARS")], ["Dólares acreditados", money(r.dolares_acreditados, "USD"), true]]} />,
              okText: "Listo",
            });
            setNonce((x) => x + 1);
          })
          .catch((err: Error) => { setMsg(err.message); toast(err.message, true); });
      },
    });
  };

  return (
    <>
      {head}
      <div className="cols2">
        <div className="col">
          <div className="card">
            <div className="ctitle">
              <h2>Cotización</h2>
              {m.abierto ? <span className="pill up">Mercado abierto</span> : <span className="pill down">Mercado cerrado</span>}
            </div>
            <div className="grid g3">
              <div className="stat"><small>AL30 (pesos)</small><b>{money(al30.precio_actual, "ARS")}</b></div>
              <div className="stat"><small>AL30D (dólares)</small><b>{money(al30d.precio_actual, "USD")}</b></div>
              <div className="stat"><small>Tipo de cambio</small><b>{money(tc, "ARS")}</b></div>
            </div>
            <p className="muted" style={{ fontSize: 13 }}>Tipo de cambio = precio AL30 / precio AL30D. Se cobra 0,5 % de comisión en cada pata. Si alguna pata falla, no se registra ninguna.</p>
            {(!al30.activo || !al30d.activo) && <div className="notice">Uno de los bonos está suspendido: el MEP va a ser rechazado.</div>}
          </div>
          <DolaresCardAuto />
        </div>
        <form className="card" noValidate onSubmit={onSubmit}>
          <div className="ctitle"><h2>Comprar dólares</h2></div>
          <div className="field">
            <label htmlFor="mepAmt">Monto en pesos</label>
            <input id="mepAmt" type="number" min={1} step={0.01} value={amt} onChange={(e) => { setAmt(e.target.value); setMsg(""); }} />
          </div>
          <div className="summary">
            <div><span className="muted">Nominales AL30</span><b>{num(n)}</b></div>
            <div><span className="muted">Pesos a debitar</span><span>{money(pesos, "ARS")}</span></div>
            <div className="tot"><span>Dólares a recibir (aprox.)</span><span>{money(usd, "USD")}</span></div>
          </div>
          <button type="submit" className="btn btn-primary full">Revisar operación</button>
          <div className="form-msg" aria-live="polite">{msg}</div>
          <p className="muted" style={{ fontSize: 12, margin: "10px 0 0" }}>Disponible: {money(c.saldo_ars, "ARS")} y {money(c.saldo_usd, "USD")}</p>
        </form>
      </div>
    </>
  );
}
