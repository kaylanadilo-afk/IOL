"use client";

import Link from "next/link";
import { Fragment, useEffect, useId, useRef, useState } from "react";
import { chatAgente } from "@/lib/api";
import { money, pct } from "@/lib/format";
import type { InformeAgente, MensajeAgente, RecomendacionAgente } from "@/lib/types";

/* ===================== MARCA ANIMADA ===================== */
// La línea que sube del logo de Zeno. Mientras el agente analiza, la línea "recorre" el trazo.
export function ZenoLinea({ pensando = false, size = 40 }: { pensando?: boolean; size?: number }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg className={`zl${pensando ? " pensando" : ""}`} width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <defs>
        <linearGradient id={`zg${id}`} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#1F4E8C" />
          <stop offset=".55" stopColor="#2A8C93" />
          <stop offset="1" stopColor="#4CC38A" />
        </linearGradient>
      </defs>
      <path className="zl-base" d="M6 40 18 27l8 7L40 14" pathLength={100} />
      <path className="zl-trazo" d="M6 40 18 27l8 7L40 14" pathLength={100} stroke={`url(#zg${id})`} />
      <path className="zl-flecha" d="M31 13h10v10" stroke={`url(#zg${id})`} />
    </svg>
  );
}

/* ===================== ANÁLISIS EN CURSO ===================== */
const PASOS = ["Leyendo tu perfil de riesgo", "Revisando tu cartera y tu saldo", "Mirando el mercado de hoy", "Armando las recomendaciones"];

export function Analizando() {
  const [paso, setPaso] = useState(0);
  useEffect(() => {
    if (paso >= PASOS.length - 1) return;
    const t = setTimeout(() => setPaso((p) => p + 1), 1100);
    return () => clearTimeout(t);
  }, [paso]);
  return (
    <div className="ag-analizando" role="status" aria-live="polite">
      <ZenoLinea pensando size={64} />
      <div>
        <p className="ag-analizando-tit">Zeno AI está analizando</p>
        <ol className="ag-pasos">
          {PASOS.map((p, i) => (
            <li key={p} className={i < paso ? "hecho" : i === paso ? "activo" : ""}>
              <span className="ag-paso-ico" aria-hidden="true">
                {i < paso ? <svg viewBox="0 0 16 16"><path d="m3.5 8.5 3 3 6-7" /></svg> : <i />}
              </span>
              {p}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

/* ===================== INFORME ===================== */
const POSTURA = {
  defensiva: { txt: "Postura defensiva", d: "M12 3l7.5 3v5.5c0 4.6-3.2 8.3-7.5 9.5-4.3-1.2-7.5-4.9-7.5-9.5V6z" },
  neutral: { txt: "Postura neutral", d: "M4 12h16M12 4v16" },
  ofensiva: { txt: "Postura ofensiva", d: "M4 17l6-6 4 4 6-8M15 7h5v5" },
} as const;

export function Briefing({ inf }: { inf: InformeAgente }) {
  const p = POSTURA[inf.postura] ?? POSTURA.neutral;
  const hora = new Date(inf.generado).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  return (
    <section className="ag-brief">
      <div className="ag-brief-top">
        <span className={`ag-postura ${inf.postura}`}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d={p.d} /></svg>{p.txt}
        </span>
        <span className="ag-hora">Análisis de las {hora}</span>
      </div>
      <h2 className="ag-titular">{inf.titular}</h2>
      <div className="ag-brief-cols">
        <div>
          <h3>El mercado hoy</h3>
          <p>{inf.resumen_mercado}</p>
        </div>
        <div>
          <h3>Tu cartera</h3>
          <p>{inf.lectura_cartera}</p>
        </div>
        <RiesgoMedidor n={inf.puntaje_riesgo} perfil={inf.perfil} />
      </div>
    </section>
  );
}

function RiesgoMedidor({ n, perfil }: { n: number; perfil: string }) {
  const nivel = n <= 3 ? "bajo" : n <= 6 ? "medio" : "alto";
  return (
    <div className="ag-medidor">
      <h3>Riesgo del día para tu perfil</h3>
      <div className="ag-medidor-num"><b>{n}</b><span>/10 · {nivel}</span></div>
      <div className="ag-medidor-barras" role="img" aria-label={`Riesgo ${n} de 10 para un perfil ${perfil}`}>
        {Array.from({ length: 10 }, (_, i) => (
          <i key={i} className={i < n ? `on r${Math.min(3, Math.ceil((i + 1) / 3.4))}` : ""} style={{ animationDelay: `${300 + i * 45}ms` }} />
        ))}
      </div>
      <small>Perfil {perfil}</small>
    </div>
  );
}

const ACCION = { comprar: "Comprar", vender: "Vender", mantener: "Mantener" } as const;

export function Recomendaciones({ recs, descartadas, situacion }: {
  recs: RecomendacionAgente[]; descartadas: string[]; situacion: InformeAgente["situacion"];
}) {
  const nueva = situacion === "cuenta_nueva_sin_saldo";
  return (
    <section className="ag-recs" aria-label="Recomendaciones">
      {nueva && (
        <div className="ag-inicio">
          <div>
            <b>Todavía no depositaste</b>
            <p>Este es un plan para tu primera inversión según tu perfil. Cuando deposites, Zeno AI te dice cuánto poner en cada uno.</p>
          </div>
          <Link href="/movimientos" className="btn btn-primary btn-sm">Depositar</Link>
        </div>
      )}
      <div className="ag-sec-head">
        <h2>{nueva ? "Tu plan para empezar" : situacion === "sin_inversiones" ? "Tu primera cartera" : "Qué haría hoy"}</h2>
        <span className="muted">{recs.length} {recs.length === 1 ? "recomendación" : "recomendaciones"}</span>
      </div>
      {recs.length ? (
        <ul>
          {recs.map((r, i) => (
            <li key={`${r.ticker}${i}`} className={`ag-rec ${r.accion}`} style={{ animationDelay: `${i * 90}ms` }}>
              <span className="ag-accion">{ACCION[r.accion]}</span>
              <div className="ag-rec-activo">
                <b>{r.ticker}</b>
                <small>{r.activo.nombre}</small>
              </div>
              <div className="ag-rec-monto">
                {r.accion === "mantener" ? <b className="muted">Sin cambios</b>
                  : r.idea ? <b>{r.porcentaje.toLocaleString("es-AR")} %</b>
                  : <b>{money(r.monto, r.moneda)}</b>}
                <small>
                  {r.idea && <>de tu primer depósito · </>}
                  {r.cantidad_estimada > 0 && <>≈ {r.cantidad_estimada} u. a {money(r.activo.precio, r.moneda)}</>}
                  {r.activo.variacion_pct != null && <span className={r.activo.variacion_pct >= 0 ? "up" : "down"}> {pct(r.activo.variacion_pct)} hoy</span>}
                </small>
              </div>
              <p className="ag-motivo">{r.motivo}</p>
              <div className="ag-rec-pie">
                <span className={`ag-confianza ${r.confianza}`} title={`Confianza ${r.confianza}`}>
                  <i /><i /><i /> Confianza {r.confianza}
                </span>
                <Link href={`/mercado/${r.activo.id}`} className="ag-ir">Ver {r.ticker}</Link>
              </div>
            </li>
          ))}
        </ul>
      ) : <div className="empty">Hoy no hay movimientos sugeridos para tu cartera.</div>}
      {descartadas.length > 0 && (
        <details className="ag-descartadas">
          <summary>{descartadas.length} {descartadas.length === 1 ? "idea quedó afuera" : "ideas quedaron afuera"} por las reglas de tu perfil</summary>
          <ul>{descartadas.map((d) => <li key={d}>{d}</li>)}</ul>
        </details>
      )}
    </section>
  );
}

export function RiesgosYPasos({ riesgos, pasos }: { riesgos: string[]; pasos: string[] }) {
  return (
    <div className="ag-dos">
      <section className="ag-lista">
        <h2>Qué vigilar</h2>
        <ul className="ag-riesgos">{riesgos.map((r) => <li key={r}>{r}</li>)}</ul>
      </section>
      <section className="ag-lista">
        <h2>Próximos pasos</h2>
        <ol className="ag-proximos">{pasos.map((p) => <li key={p}>{p}</li>)}</ol>
      </section>
    </div>
  );
}

/* ===================== CHAT ===================== */
const SUGERENCIAS = [
  "Explicame el informe de hoy en simple",
  "¿Me conviene comprar dólar MEP hoy?",
  "¿Cómo diversifico mejor mi cartera?",
  "¿Qué hago con los activos que vienen en pérdida?",
];

/** Texto con **negritas** y viñetas ("- ") convertido a elementos (sin HTML crudo). */
function Rico({ texto }: { texto: string }) {
  const negritas = (t: string) => t.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? <b key={i}>{p.slice(2, -2)}</b> : <Fragment key={i}>{p}</Fragment>);
  const bloques: React.ReactNode[] = [];
  let lista: string[] = [];
  const cerrarLista = () => {
    if (lista.length) bloques.push(<ul key={`l${bloques.length}`}>{lista.map((l, i) => <li key={i}>{negritas(l)}</li>)}</ul>);
    lista = [];
  };
  for (const linea of texto.split("\n")) {
    const l = linea.trim();
    if (/^([-*•]|\d+\.)\s+/.test(l)) {
      lista.push(l.replace(/^([-*•]|\d+\.)\s+/, ""));
      continue;
    }
    cerrarLista();
    if (l) bloques.push(<p key={`p${bloques.length}`}>{negritas(l.replace(/^#+\s*/, ""))}</p>);
  }
  cerrarLista();
  return <>{bloques}</>;
}

export function ChatAgente({ habilitado }: { habilitado: boolean }) {
  const [mensajes, setMensajes] = useState<MensajeAgente[]>([]);
  const [escribiendo, setEscribiendo] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [texto, setTexto] = useState("");
  const lista = useRef<HTMLDivElement>(null);
  const corte = useRef<AbortController | null>(null);

  useEffect(() => {
    lista.current?.scrollTo({ top: lista.current.scrollHeight, behavior: "smooth" });
  }, [mensajes, escribiendo]);
  useEffect(() => () => corte.current?.abort(), []);

  const enviar = async (pregunta: string) => {
    const q = pregunta.trim();
    if (!q || escribiendo != null) return;
    const historial: MensajeAgente[] = [...mensajes, { role: "user", content: q }];
    setMensajes(historial);
    setTexto("");
    setError("");
    setEscribiendo("");
    corte.current = new AbortController();
    try {
      const final = await chatAgente(historial, (parcial) => setEscribiendo(parcial), corte.current.signal);
      setMensajes([...historial, { role: "assistant", content: final }]);
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      setEscribiendo(null);
    }
  };

  return (
    <section className="ag-chat" aria-label="Conversar con Zeno AI">
      <header className="ag-chat-head">
        <ZenoLinea pensando={escribiendo != null} size={30} />
        <div>
          <b>Preguntale a Zeno AI</b>
          <small>Conoce tu perfil, tu cartera y el mercado de hoy</small>
        </div>
      </header>
      <div className="ag-chat-lista" ref={lista}>
        {!mensajes.length && (
          <div className="ag-sugerencias">
            {SUGERENCIAS.map((s) => (
              <button key={s} type="button" disabled={!habilitado} onClick={() => enviar(s)}>{s}</button>
            ))}
          </div>
        )}
        {mensajes.map((m, i) => (
          <div key={i} className={`ag-msg ${m.role}`}>{m.role === "assistant" ? <Rico texto={m.content} /> : m.content}</div>
        ))}
        {escribiendo != null && (
          <div className="ag-msg assistant vivo">
            {escribiendo ? <Rico texto={escribiendo} /> : <span className="ag-puntos" aria-label="Escribiendo"><i /><i /><i /></span>}
          </div>
        )}
        {error && <div className="ag-chat-error" role="alert">{error}</div>}
      </div>
      <form className="ag-chat-form" onSubmit={(e) => { e.preventDefault(); enviar(texto); }}>
        <textarea rows={1} value={texto} disabled={!habilitado} placeholder={habilitado ? "Escribí tu pregunta…" : "Configurá el agente para chatear"}
          onChange={(e) => setTexto(e.target.value)} aria-label="Tu pregunta"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(texto); } }} />
        {escribiendo != null
          ? <button type="button" className="ag-enviar" onClick={() => corte.current?.abort()} aria-label="Detener respuesta"><svg viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" rx="2" /></svg></button>
          : <button type="submit" className="ag-enviar" disabled={!habilitado || !texto.trim()} aria-label="Enviar"><svg viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6" /></svg></button>}
      </form>
    </section>
  );
}
