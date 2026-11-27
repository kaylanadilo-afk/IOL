"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { cls, fecha, money, pct } from "@/lib/format";
import type { Activo, Alerta, AlertaCrear, TipoAlerta } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { IcoBorrar, IcoEditar, IcoPausa, IcoPlay } from "@/components/icons";
import { ErrorCard, FieldError, FuentePrecios, Head, Loading } from "@/components/ui";

const TIPOS: [TipoAlerta, string, string][] = [
  ["baja_pct", "Baja un porcentaje", "Ej.: avisame si baja 20 % desde hoy"],
  ["sube_pct", "Sube un porcentaje", "Ej.: avisame si sube 31 % desde hoy"],
  ["precio", "Llega a un precio", "Ej.: avisame si llega a $ 50.000"],
];
const ESTADO_LBL: Record<Alerta["estado"], string> = { activa: "Activa", pausada: "Pausada", ejecutada: "Ejecutada" };
const ESTADO_PILL: Record<Alerta["estado"], string> = { activa: "up", pausada: "warn", ejecutada: "neutral" };

export default function AlertasPage() {
  // useSearchParams necesita un Suspense alrededor para poder prerenderizar la página
  return <Suspense fallback={<Loading />}><Alertas /></Suspense>;
}

/** Objetivo que va a quedar configurado (la API hace el mismo cálculo al guardarla). */
function objetivo(tipo: TipoAlerta, valor: number, ref: number): number | null {
  if (!(valor > 0) || !(ref > 0)) return null;
  if (tipo === "sube_pct") return ref * (1 + valor / 100);
  if (tipo === "baja_pct") return valor < 100 ? ref * (1 - valor / 100) : null;
  return valor;
}

function Alertas() {
  const { activos, refreshAvisos, preciosReales } = useMe();
  const { toast, confirm } = useUI();
  const params = useSearchParams();
  const [vista, setVista] = useState<"abiertas" | "historial">("abiertas");
  const [editando, setEditando] = useState<Alerta | null>(null);
  const [nonce, setNonce] = useState(0);
  const { data, error, reload } = useAsync(() => Promise.all([api.alertas(), api.avisos()]), [nonce]);

  // Al entrar a esta pantalla, los avisos quedan leídos
  useEffect(() => {
    if (data && data[1].no_leidas > 0) api.leerAvisos().then(refreshAvisos).catch(() => {});
  }, [data, refreshAvisos]);

  const recargar = () => setNonce((n) => n + 1);
  const head = <Head title="Alertas de precios" sub="Te avisamos por correo y en la app cuando un activo llega al precio que elegiste." />;
  if (error) return <>{head}<ErrorCard message={error} onRetry={reload} /></>;
  if (!data) return <>{head}<Loading /></>;
  const [alertas, avisos] = data;
  const abiertas = alertas.filter((a) => a.estado !== "ejecutada");
  const ejecutadas = alertas.filter((a) => a.estado === "ejecutada");

  const cambiarEstado = (a: Alerta) => {
    const nuevo = a.estado === "activa" ? "pausada" : "activa";
    api.estadoAlerta(a.id, nuevo)
      .then(() => { toast(nuevo === "pausada" ? `Alerta de ${a.ticker} pausada.` : `Alerta de ${a.ticker} activa de nuevo.`); recargar(); })
      .catch((e: Error) => toast(e.message, true));
  };
  const borrar = (a: Alerta) => confirm({
    title: "Borrar alerta",
    body: <p className="muted">Se borra la alerta de {a.ticker} ({a.condicion}). Los avisos que ya recibiste quedan en el historial.</p>,
    okText: "Borrar",
    onOk: () => api.borrarAlerta(a.id)
      .then(() => { toast("Alerta borrada."); if (editando?.id === a.id) setEditando(null); recargar(); })
      .catch((e: Error) => toast(e.message, true)),
  });

  return (
    <>
      {head}
      <div className="alertas-grid">
        <AlertaForm key={editando?.id ?? "nueva"} activos={activos} editando={editando} inicialId={Number(params.get("activo")) || null}
          onListo={() => { setEditando(null); recargar(); }} onCancelar={() => setEditando(null)} />

        <div className="card">
          <div className="ctitle">
            <div className="tabs">
              <button type="button" className={`tab${vista === "abiertas" ? " active" : ""}`} onClick={() => setVista("abiertas")}>Mis alertas ({alertas.length})</button>
              <button type="button" className={`tab${vista === "historial" ? " active" : ""}`} onClick={() => setVista("historial")}>Historial ({avisos.items.length})</button>
            </div>
          </div>

          {vista === "abiertas" ? (
            abiertas.length || ejecutadas.length ? (
              <div className="table-wrap">
                <table className="mt alertas-table">
                  <thead>
                    <tr><th>Activo</th><th className="hm">Condición</th><th className="num">Objetivo</th><th className="num hm">Precio actual</th><th className="hm">Estado</th><th className="num"><span className="sr-only">Acciones</span></th></tr>
                  </thead>
                  <tbody>
                    {[...abiertas, ...ejecutadas].map((a) => (
                      <tr key={a.id} className={a.estado === "ejecutada" ? "apagada" : undefined}>
                        <td><span className="sym">{a.ticker}</span><div className="sname hm">{a.nombre}</div>
                          <div className="sname only-m">{a.condicion}</div>
                          <div className="only-m"><span className={`pill ${ESTADO_PILL[a.estado]}`}>{ESTADO_LBL[a.estado]}</span></div></td>
                        <td className="hm">{a.condicion}{a.recurrente && <div className="sname">Recurrente</div>}<div className="sname">{[a.aviso_email && "Correo", a.aviso_app && "App"].filter(Boolean).join(" + ")}</div></td>
                        <td className="num"><b>{money(a.precio_objetivo, a.moneda)}</b><div className="sname">desde {money(a.precio_referencia, a.moneda)}</div></td>
                        <td className="num hm">{money(a.precio_actual, a.moneda)}
                          {a.estado !== "ejecutada" && a.distancia_pct != null && <div className={`sname ${cls(a.distancia_pct)}`}>faltan {pct(a.distancia_pct)}</div>}
                        </td>
                        <td className="hm"><span className={`pill ${ESTADO_PILL[a.estado]}`}>{ESTADO_LBL[a.estado]}</span>
                          {a.ultima_vez && <div className="sname">{fecha(a.ultima_vez)}</div>}</td>
                        <td className="num">
                          <div className="acciones">
                            <button type="button" className="icon-btn" title="Editar" aria-label={`Editar alerta de ${a.ticker}`} onClick={() => { setEditando(a); window.scrollTo({ top: 0, behavior: "smooth" }); }}><IcoEditar /></button>
                            <button type="button" className="icon-btn" title={a.estado === "activa" ? "Pausar" : "Activar"}
                              aria-label={`${a.estado === "activa" ? "Pausar" : "Activar"} alerta de ${a.ticker}`} onClick={() => cambiarEstado(a)}>
                              {a.estado === "activa" ? <IcoPausa /> : <IcoPlay />}
                            </button>
                            <button type="button" className="icon-btn danger" title="Borrar" aria-label={`Borrar alerta de ${a.ticker}`} onClick={() => borrar(a)}><IcoBorrar /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="empty">Todavía no configuraste alertas. Creá la primera con el formulario.</div>
          ) : avisos.items.length ? (
            <div className="table-wrap">
              <table className="mt">
                <thead><tr><th>Fecha y hora</th><th>Aviso</th><th className="num">Precio</th><th className="num">Variación</th><th className="hm">Correo</th></tr></thead>
                <tbody>
                  {avisos.items.map((n) => (
                    <tr key={n.id}>
                      <td className="nowrap">{fecha(n.fecha)}</td>
                      <td><b>{n.titulo}</b><div className="sname">{n.mensaje}</div></td>
                      <td className="num">{n.precio != null ? money(n.precio, "ARS") : "—"}</td>
                      <td className={`num ${cls(n.variacion_pct)}`}>{n.variacion_pct != null ? pct(n.variacion_pct) : "—"}</td>
                      <td className="hm">{n.email_enviado ? <span className="pill up">Enviado</span> : <span className="pill neutral">Solo app</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="empty">Todavía no se cumplió ninguna alerta.</div>}
        </div>
      </div>

      <div className="card alertas-info">
        <b>Cómo funcionan</b>
        <ul>
          <li>El porcentaje se mide desde el precio que tiene el activo en el momento en que creás (o cambiás) la alerta.</li>
          <li>{preciosReales
            ? "El servidor revisa las alertas cada vez que llegan precios nuevos (cada minuto), aunque no tengas la página abierta."
            : "Ahora los precios se cargan a mano: las alertas se revisan cada vez que cambia un precio. Con PRECIOS_REALES=1 se revisan cada minuto con precios de BYMA."}</li>
          <li>Cada alerta avisa una sola vez y queda como ejecutada. Las recurrentes vuelven a avisar en el próximo cruce.</li>
          <li>Las alertas son informativas: no compran ni venden por vos ni garantizan que una operación convenga.</li>
        </ul>
        <FuentePrecios />
      </div>
    </>
  );
}

/* ===================== FORMULARIO (crear o editar) ===================== */
function AlertaForm({ activos, editando, inicialId, onListo, onCancelar }: {
  activos: Activo[]; editando: Alerta | null; inicialId: number | null; onListo: () => void; onCancelar: () => void;
}) {
  const { toast } = useUI();
  const inicial = editando ? activos.find((a) => a.id === editando.activo_id) ?? null : activos.find((a) => a.id === inicialId) ?? null;
  const [activo, setActivo] = useState<Activo | null>(inicial);
  const [busqueda, setBusqueda] = useState(inicial ? `${inicial.ticker} · ${inicial.nombre}` : "");
  const [abierta, setAbierta] = useState(false);
  const [tipo, setTipo] = useState<TipoAlerta>(editando?.tipo ?? "baja_pct");
  const [valor, setValor] = useState(editando ? String(editando.valor) : "");
  const [email, setEmail] = useState(editando?.aviso_email ?? true);
  const [app, setApp] = useState(editando?.aviso_app ?? true);
  const [recurrente, setRecurrente] = useState(editando?.recurrente ?? false);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const q = busqueda.trim().toLowerCase();
  const opciones = useMemo(() => activos
    .filter((a) => !q || `${a.ticker} ${a.nombre}`.toLowerCase().includes(q))
    .slice(0, 8), [activos, q]);
  const n = Number(valor.replace(",", "."));
  const obj = activo ? objetivo(tipo, n, activo.precio_actual) : null;

  const elegir = (a: Activo) => {
    setActivo(a);
    setBusqueda(`${a.ticker} · ${a.nombre}`);
    setAbierta(false);
    setErrores((e) => ({ ...e, activo_id: "" }));
  };

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!activo) errs.activo_id = "Elegí un activo de la lista";
    if (!(n > 0)) errs.valor = tipo === "precio" ? "Ingresá el precio objetivo" : "Ingresá el porcentaje";
    else if (tipo === "baja_pct" && n >= 100) errs.valor = "Una baja tiene que ser menor al 100 %";
    else if (tipo !== "precio" && n > 1000) errs.valor = "El porcentaje puede ser de hasta 1000 %";
    else if (tipo === "precio" && activo && n === activo.precio_actual) errs.valor = "El activo ya está en ese precio";
    if (!email && !app) errs.aviso = "Elegí al menos una forma de aviso";
    setErrores(errs);
    if (Object.keys(errs).length || !activo) return;
    const datos: AlertaCrear = { activo_id: activo.id, tipo, valor: n, recurrente, aviso_email: email, aviso_app: app };
    setBusy(true);
    try {
      if (editando) {
        await api.editarAlerta(editando.id, { tipo, valor: n, recurrente, aviso_email: email, aviso_app: app });
        toast(`Alerta de ${activo.ticker} actualizada.`);
      } else {
        await api.crearAlerta(datos);
        toast(`Alerta de ${activo.ticker} creada.`);
        setValor("");
      }
      onListo();
    } catch (err) {
      const campos = err instanceof ApiError ? err.campos : {};
      if (Object.keys(campos).length) setErrores(campos);
      else setErrores({ general: (err as Error).message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card alerta-form" onSubmit={guardar} noValidate>
      <div className="ctitle"><h2>{editando ? `Editar alerta de ${editando.ticker}` : "Nueva alerta"}</h2></div>

      <div className={`field combo f-activo${errores.activo_id ? " invalid" : ""}`}>
        <label htmlFor="alertaActivo">Activo</label>
        <div className="combo-in">
        <input id="alertaActivo" role="combobox" aria-expanded={abierta} aria-controls="alertaOpciones" autoComplete="off"
          placeholder="Buscá por ticker o nombre (YPFD, Galicia…)" value={busqueda} disabled={!!editando}
          aria-invalid={!!errores.activo_id} aria-describedby={errores.activo_id ? "alertaActivo-err" : undefined}
          onFocus={() => setAbierta(true)} onBlur={() => setTimeout(() => setAbierta(false), 150)}
          onChange={(e) => { setBusqueda(e.target.value); setActivo(null); setAbierta(true); }}
          onKeyDown={(e) => { if (e.key === "Enter" && abierta && opciones[0]) { e.preventDefault(); elegir(opciones[0]); } }} />
        {abierta && !editando && (
          <ul className="combo-list" id="alertaOpciones" role="listbox">
            {opciones.length ? opciones.map((a) => (
              <li key={a.id} role="option" aria-selected={activo?.id === a.id} onMouseDown={(e) => { e.preventDefault(); elegir(a); }}>
                <span><b>{a.ticker}</b> <span className="muted">{a.nombre}</span></span><span>{money(a.precio_actual, a.moneda)}</span>
              </li>
            )) : <li className="muted">No se encontraron activos.</li>}
          </ul>
        )}
        </div>
        <FieldError id="alertaActivo" error={errores.activo_id} />
        {activo && <p className="field-hint">Precio actual: <b>{money(activo.precio_actual, activo.moneda)}</b> · se toma como referencia</p>}
      </div>

      <div className="field f-tipo">
        <span className="field-label">Avisame cuando</span>
        <div className="opciones-tipo" role="radiogroup" aria-label="Condición">
          {TIPOS.map(([t, titulo, ayuda]) => (
            <button key={t} type="button" role="radio" aria-checked={tipo === t} className={`opcion${tipo === t ? " on" : ""}`}
              onClick={() => { setTipo(t); setErrores((e) => ({ ...e, valor: "" })); }}>
              <b>{titulo}</b><small>{ayuda}</small>
            </button>
          ))}
        </div>
      </div>

      <div className={`field f-valor${errores.valor ? " invalid" : ""}`}>
        <label htmlFor="alertaValor">{tipo === "precio" ? `Precio objetivo${activo ? ` (${activo.moneda})` : ""}` : "Porcentaje (%)"}</label>
        <input id="alertaValor" inputMode="decimal" placeholder={tipo === "precio" ? "50000" : "20"} value={valor}
          aria-invalid={!!errores.valor} aria-describedby={errores.valor ? "alertaValor-err" : undefined}
          onChange={(e) => { setValor(e.target.value); setErrores((x) => ({ ...x, valor: "" })); }} />
        <FieldError id="alertaValor" error={errores.valor} />
        {activo && obj != null && !errores.valor && (
          <p className="field-hint">Te avisamos cuando {activo.ticker} {obj >= activo.precio_actual ? "suba" : "baje"} a <b>{money(obj, activo.moneda)}</b> ({pct((obj / activo.precio_actual - 1) * 100)} desde hoy).</p>
        )}
      </div>

      <div className={`field f-aviso${errores.aviso ? " invalid" : ""}`}>
        <span className="field-label">Cómo avisarte</span>
        <label className="check"><input type="checkbox" checked={email} onChange={(e) => setEmail(e.target.checked)} /> Por correo electrónico</label>
        <label className="check"><input type="checkbox" checked={app} onChange={(e) => setApp(e.target.checked)} /> En la app (campana de alertas)</label>
        <label className="check"><input type="checkbox" checked={recurrente} onChange={(e) => setRecurrente(e.target.checked)} /> Recurrente: volver a avisar en cada nuevo cruce</label>
        <FieldError id="alertaAviso" error={errores.aviso} />
      </div>

      <div className="err f-err" role="alert">{errores.general}</div>
      <div className="form-actions f-acc">
        {editando && <button type="button" className="btn btn-ghost" onClick={onCancelar}>Cancelar</button>}
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Guardando…" : editando ? "Guardar cambios" : "Crear alerta"}</button>
      </div>
      {editando && <p className="muted f-nota" style={{ fontSize: 12, margin: "8px 0 0" }}>Si cambiás la condición, el porcentaje se vuelve a medir desde el precio actual.</p>}
    </form>
  );
}
