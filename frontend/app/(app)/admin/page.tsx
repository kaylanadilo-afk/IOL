"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { hora, money, num, TIPO_LBL } from "@/lib/format";
import type { Activo, ActivoCrear, Moneda, TipoActivo } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { ErrorCard, Head, Loading, RiskDots } from "@/components/ui";

export default function AdminPage() {
  const { me, mercado, preciosReales, reloadAll, reloadKey } = useMe();
  const { toast } = useUI();
  const { data: list, error, reload } = useAsync(() => api.activos(), [reloadKey], me.es_admin);
  const [precios, setPrecios] = useState<Record<number, string>>({});
  const [syncing, setSyncing] = useState(false);
  const [cargando, setCargando] = useState(false);

  const head = <Head title="Administración" sub="Catálogo de activos, precios y dividendos" />;
  if (!me.es_admin) {
    return (
      <>
        <Head title="Administración" />
        <div className="card empty">Esta sección es solo para perfiles autorizados. <Link href="/" className="btn btn-primary btn-sm">Volver al inicio</Link></div>
      </>
    );
  }
  if (error) return <>{head}<ErrorCard message={error} onRetry={reload} /></>;
  if (!list) return <>{head}<Loading /></>;

  const despues = (msg: string) => { toast(msg); reloadAll(); };
  const fallo = (err: Error) => toast(err.message, true);

  const guardarPrecio = (a: Activo) => {
    const val = Number(precios[a.id] ?? a.precio_actual);
    if (!(val > 0)) return toast("El precio tiene que ser mayor a 0.", true);
    api.cambiarPrecio(a.id, val).then((x) => despues(`${x.ticker}: nuevo precio ${money(x.precio_actual, x.moneda)}`)).catch(fallo);
  };

  const p = mercado?.precios;
  const h = mercado?.historial;

  return (
    <>
      {head}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="ctitle">
          <h2>Precios de mercado</h2>
          <div className="row-actions">
            {preciosReales && (
              <button type="button" className="btn btn-primary btn-sm" disabled={syncing} onClick={() => {
                setSyncing(true);
                api.sincronizar().then((r) => despues(`${r.actualizados} precios actualizados.`)).catch(fallo).finally(() => setSyncing(false));
              }}>Sincronizar ahora</button>
            )}
            <button type="button" className="btn btn-ghost btn-sm" disabled={cargando} onClick={() => {
              setCargando(true);
              api.cargarHistorial()
                .then((r) => despues(`Historial cargado: ${num(r.resultado?.cierres)} cierres y ${num(r.resultado?.puntos_intradia)} puntos intradiarios.`))
                .catch(fallo).finally(() => setCargando(false));
            }}>{cargando ? "Cargando…" : "Cargar historial"}</button>
          </div>
        </div>
        {h?.error ? <p className="down" style={{ margin: "0 0 8px", fontSize: 13 }}>Historial: {h.error}</p>
          : !h?.ultima_carga ? <p className="muted" style={{ margin: "0 0 8px", fontSize: 13 }}>Historial para los gráficos: todavía no se cargó.</p>
          : (
            <p className="muted" style={{ margin: "0 0 8px", fontSize: 13 }}>
              Historial cargado a las {hora(h.ultima_carga)}: {num(h.resultado?.cierres)} cierres diarios (data912) y {num(h.resultado?.puntos_intradia)} puntos intradiarios nuevos (Yahoo).
              {h.resultado?.errores.length ? ` Con errores: ${h.resultado.errores.join(", ")}.` : ""}
            </p>
          )}
        {preciosReales && p ? (
          <p className="muted" style={{ margin: 0 }}>
            Precios reales de BYMA vía data912.com, cada {p.intervalo_segundos} s.{" "}
            {p.ultima_sincronizacion && `Última actualización: ${hora(p.ultima_sincronizacion)} (${p.actualizados} activos).`}
            {p.sin_dato.length > 0 && ` Sin cotización: ${p.sin_dato.join(", ")}.`}
            {p.error && <><br /><span className="down">Último intento falló: {p.error}</span></>}
            <br />Si cambiás un precio a mano, se va a pisar en la próxima actualización.
          </p>
        ) : (
          <p className="muted" style={{ margin: 0 }}>Los precios se cargan a mano en la tabla de abajo. Para usar precios reales, levantá la API con <code>PRECIOS_REALES=1</code>.</p>
        )}
      </div>

      <div className="grid g2e" style={{ marginBottom: 16 }}>
        <NuevoActivoForm onDone={despues} />
        <DividendoForm activos={list.filter((a) => a.tipo !== "bono")} onDone={despues} />
      </div>

      <div className="card table-wrap">
        <table>
          <thead><tr><th>Activo</th><th>Tipo · moneda</th><th>Riesgo</th><th className="num">Precio actual</th><th>Estado</th><th /></tr></thead>
          <tbody>
            {list.map((a) => (
              <tr key={a.id}>
                <td><span className="sym">{a.ticker}</span><div className="sname">{a.nombre}</div></td>
                <td className="muted">{TIPO_LBL[a.tipo]} · {a.moneda}</td>
                <td><RiskDots n={a.nivel_riesgo} /></td>
                <td className="num">
                  <input className="price-input" type="number" min={0.0001} step={0.0001} aria-label={`Precio de ${a.ticker}`}
                    value={precios[a.id] ?? String(a.precio_actual)} onChange={(e) => setPrecios({ ...precios, [a.id]: e.target.value })} />{" "}
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => guardarPrecio(a)}>Guardar</button>
                </td>
                <td>{a.activo ? <span className="pill up">Activo</span> : <span className="pill down">Suspendido</span>}</td>
                <td>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => {
                    api.cambiarEstado(a.id, !a.activo).then((x) => despues(x.ticker + (x.activo ? " habilitado." : " suspendido."))).catch(fallo);
                  }}>{a.activo ? "Suspender" : "Habilitar"}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function NuevoActivoForm({ onDone }: { onDone: (msg: string) => void }) {
  const [f, setF] = useState({ ticker: "", nombre: "", tipo: "accion" as TipoActivo, moneda: "ARS" as Moneda, precio: "", riesgo: "3" });
  const [msg, setMsg] = useState("");
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <form className="card" noValidate onSubmit={(e) => {
      e.preventDefault();
      const datos: ActivoCrear = { ticker: f.ticker, nombre: f.nombre, tipo: f.tipo, moneda: f.moneda, precio_actual: Number(f.precio), nivel_riesgo: Number(f.riesgo) };
      api.crearActivo(datos).then((a) => { setMsg(""); onDone(`${a.ticker} agregado al catálogo.`); }).catch((err: Error) => setMsg(err.message));
    }}>
      <div className="ctitle"><h2>Nuevo activo</h2></div>
      <div className="inline-form">
        <div className="field"><label htmlFor="naTicker">Ticker</label><input id="naTicker" placeholder="GGAL" value={f.ticker} onChange={set("ticker")} /></div>
        <div className="field" style={{ flex: 2 }}><label htmlFor="naNombre">Nombre</label><input id="naNombre" value={f.nombre} onChange={set("nombre")} /></div>
      </div>
      <div className="inline-form" style={{ marginTop: 10 }}>
        <div className="field"><label htmlFor="naTipo">Tipo</label>
          <select id="naTipo" value={f.tipo} onChange={set("tipo")}><option value="accion">Acción</option><option value="cedear">CEDEAR</option><option value="bono">Bono</option></select>
        </div>
        <div className="field"><label htmlFor="naMoneda">Moneda</label>
          <select id="naMoneda" value={f.moneda} onChange={set("moneda")}><option>ARS</option><option>USD</option></select>
        </div>
        <div className="field"><label htmlFor="naPrecio">Precio</label><input id="naPrecio" type="number" min={0.0001} step={0.0001} value={f.precio} onChange={set("precio")} /></div>
        <div className="field"><label htmlFor="naRiesgo">Riesgo (1-5)</label><input id="naRiesgo" type="number" min={1} max={5} value={f.riesgo} onChange={set("riesgo")} /></div>
      </div>
      <button className="btn btn-primary" type="submit" style={{ marginTop: 12 }}>Crear activo</button>
      <div className="form-msg">{msg}</div>
    </form>
  );
}

function DividendoForm({ activos, onDone }: { activos: Activo[]; onDone: (msg: string) => void }) {
  const [activoId, setActivoId] = useState("");
  const [monto, setMonto] = useState("10");
  const [fechaPago, setFechaPago] = useState("");
  const [msg, setMsg] = useState("");
  const elegido = activoId || String(activos[0]?.id ?? "");
  return (
    <form className="card" noValidate onSubmit={(e) => {
      e.preventDefault();
      api.pagarDividendo({ activo_id: Number(elegido), monto_por_unidad: Number(monto), ...(fechaPago ? { fecha_pago: fechaPago } : {}) })
        .then((r) => { setMsg(""); onDone(`Dividendo de ${r.ticker}: ${money(r.total_pagado, r.moneda)} acreditados a ${r.cuentas_acreditadas} cuenta(s).`); })
        .catch((err: Error) => setMsg(err.message));
    }}>
      <div className="ctitle"><h2>Registrar pago de dividendo</h2></div>
      <div className="field">
        <label htmlFor="dvActivo">Activo (solo acciones y CEDEARs)</label>
        <select id="dvActivo" value={elegido} onChange={(e) => setActivoId(e.target.value)}>
          {activos.map((a) => <option key={a.id} value={a.id}>{a.ticker} ({a.moneda})</option>)}
        </select>
      </div>
      <div className="inline-form">
        <div className="field"><label htmlFor="dvMonto">Monto por unidad</label><input id="dvMonto" type="number" min={0.0001} step={0.0001} value={monto} onChange={(e) => setMonto(e.target.value)} /></div>
        <div className="field"><label htmlFor="dvFecha">Fecha de pago</label><input id="dvFecha" type="date" value={fechaPago} onChange={(e) => setFechaPago(e.target.value)} /></div>
      </div>
      <p className="muted" style={{ fontSize: 12 }}>Se acredita cantidad × monto a cada cuenta que tenga el activo, en su moneda.</p>
      <button className="btn btn-primary" type="submit">Pagar dividendo</button>
      <div className="form-msg">{msg}</div>
    </form>
  );
}
