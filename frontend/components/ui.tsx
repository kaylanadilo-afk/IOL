"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { cls, money, pct, permitido, signed } from "@/lib/format";
import type { Activo, Ganancias } from "@/lib/types";
import { useMe, useSession } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";

export function Head({ title, sub, extra }: { title: React.ReactNode; sub?: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <div className="head">
      <div>
        <h1>{title}</h1>
        {sub && <p>{sub}</p>}
      </div>
      {extra}
    </div>
  );
}

export const Loading = () => <div className="empty">Cargando…</div>;

export function ErrorCard({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { reloadAll } = useSession();
  return (
    <div className="card">
      <h2>No se pudo cargar esta pantalla</h2>
      <p className="muted">{message}</p>
      <button type="button" className="btn btn-primary" onClick={() => (onRetry ? onRetry() : reloadAll())}>Reintentar</button>
    </div>
  );
}

export function RiskDots({ n }: { n: number }) {
  return (
    <span className="risk" role="img" aria-label={`Riesgo ${n} de 5`} title={`Riesgo ${n} de 5`}>
      {[1, 2, 3, 4, 5].map((i) => <i key={i} className={i <= n ? "on" : ""} />)}
    </span>
  );
}

/** Cuándo llegaron los últimos precios y de dónde salen (en vivo, con demora o cargados a mano). */
export function FuentePrecios() {
  const { mercado } = useSession();
  const p = mercado?.precios;
  if (!p) return null;
  if (p.modo !== "reales") return <p className="fuente">Precios cargados manualmente por la administración (no son cotizaciones en vivo).</p>;
  const cuando = p.ultima_sincronizacion
    ? new Date(p.ultima_sincronizacion).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23", timeZone: "America/Argentina/Buenos_Aires" })
    : null;
  return (
    <p className={`fuente${p.error ? " warn" : ""}`}>
      <span className={`dot${p.error ? "" : " on"}`} />
      {p.error
        ? <>No se pudieron actualizar los precios{cuando ? ` desde las ${cuando}` : ""}: se muestran los últimos disponibles.</>
        : <>Cotizaciones de BYMA vía data912 · actualizadas a las {cuando ?? "—"} · se refrescan cada {p.intervalo_segundos ?? 60} s y pueden tener demora respecto del mercado.</>}
    </p>
  );
}

/** Controles de página: anterior, números y siguiente. */
export function Paginacion({ pagina, paginas, total, porPagina, onCambio }: {
  pagina: number; paginas: number; total: number; porPagina: number; onCambio: (p: number) => void;
}) {
  if (paginas <= 1) return null;
  const desde = (pagina - 1) * porPagina + 1, hasta = Math.min(pagina * porPagina, total);
  const numeros = Array.from({ length: paginas }, (_, i) => i + 1)
    .filter((n) => n === 1 || n === paginas || Math.abs(n - pagina) <= 1);
  return (
    <nav className="paginacion" aria-label="Páginas">
      <span className="muted">{desde}–{hasta} de {total}</span>
      <div className="pag-btns">
        <button type="button" className="btn btn-ghost btn-sm" disabled={pagina === 1} onClick={() => onCambio(pagina - 1)}>Anterior</button>
        {numeros.map((n, i) => (
          <span key={n} className="pag-n">
            {i > 0 && n - numeros[i - 1] > 1 && <span className="muted" aria-hidden="true">…</span>}
            <button type="button" className={`btn btn-sm ${n === pagina ? "btn-primary" : "btn-ghost"}`} aria-current={n === pagina ? "page" : undefined}
              aria-label={`Página ${n}`} onClick={() => onCambio(n)}>{n}</button>
          </span>
        ))}
        <button type="button" className="btn btn-ghost btn-sm" disabled={pagina === paginas} onClick={() => onCambio(pagina + 1)}>Siguiente</button>
      </div>
    </nav>
  );
}

export function VarPill({ a }: { a: Pick<Activo, "variacion_pct"> }) {
  if (a.variacion_pct == null) return <span className="muted">—</span>;
  return <span className={`pill ${a.variacion_pct >= 0 ? "up" : "down"}`}>{pct(a.variacion_pct)}</span>;
}

export function EstadoPill({ a }: { a: Activo }) {
  const { me } = useMe();
  if (!a.activo) return <span className="pill down">Suspendido</span>;
  if (!permitido(a, me.perfil_riesgo)) return <span className="pill warn">Fuera de tu perfil</span>;
  return <span className="pill up">Operable</span>;
}

export function StarButton({ a }: { a: Activo }) {
  const { me, favs, setFavs } = useMe();
  const { toast } = useUI();
  const on = favs.includes(a.id);
  return (
    <button
      type="button"
      className={`star${on ? " on" : ""}`}
      aria-label={on ? "Quitar de favoritos" : "Agregar a favoritos"}
      onClick={(e) => {
        e.stopPropagation();
        (on ? api.quitarFavorito(me.id, a.id) : api.marcarFavorito(me.id, a.id))
          .then((list) => {
            setFavs(list.map((x) => x.id));
            toast(a.ticker + (on ? " quitado de favoritos." : " agregado a favoritos."));
          })
          .catch((err: Error) => toast(err.message, true));
      }}
    >
      {on ? "★" : "☆"}
    </button>
  );
}

export function textoMercado(m: { abierto: boolean; en_horario: boolean } | null): string {
  if (!m) return "…";
  if (!m.abierto) return "Mercado cerrado";
  return m.en_horario ? "Mercado abierto" : "Mercado abierto 24 h";
}

export function MercadoPill() {
  const { mercado } = useSession();
  return (
    <span className="live" title="Se opera de lunes a viernes de 11 a 17 (hora argentina)">
      <span className={`dot${mercado?.abierto ? " on" : ""}`} />
      <span>{textoMercado(mercado)}</span>
    </span>
  );
}

/** Monto grande con los centavos chicos: "$ 18.190.193" + ",69" */
export function MontoHero({ n, cur }: { n: number; cur: string }) {
  const s = money(n, cur);
  const i = s.lastIndexOf(",");
  if (i < 0) return <>{s}</>;
  return <>{s.slice(0, i)}<span className="cts">{s.slice(i)}</span></>;
}

/** Mensaje de error debajo de un campo, con ícono (se lee en voz alta al aparecer). */
export function FieldError({ id, error }: { id: string; error?: string | null }) {
  if (!error) return null;
  return (
    <p className="field-err" id={`${id}-err`} role="alert">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1 5h2v7h-2zm0 9h2v2h-2z" /></svg>
      {error}
    </p>
  );
}

type InputProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "id" | "onChange" | "value">;

/** Campo de texto con etiqueta y error: si hay error, el borde y la etiqueta se ponen en rojo. */
export function TextField({ id, label, value, onChange, error, hint, ...input }: InputProps & {
  id: string; label: string; value: string; onChange: (v: string) => void; error?: string | null; hint?: string;
}) {
  return (
    <div className={`field${error ? " invalid" : ""}`}>
      <label htmlFor={id}>{label}</label>
      <input id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-invalid={!!error}
        aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined} {...input} />
      {error ? <FieldError id={id} error={error} /> : hint && <p className="field-hint" id={`${id}-hint`}>{hint}</p>}
    </div>
  );
}

export function PasswordField({ id, label, autoComplete, value, onChange, error, hint, onBlur }: {
  id: string; label: string; autoComplete: string; value: string; onChange: (v: string) => void;
  error?: string | null; hint?: string; onBlur?: () => void;
}) {
  const [ver, setVer] = useState(false);
  return (
    <div className={`field pass-field${error ? " invalid" : ""}`}>
      <label htmlFor={id}>{label}</label>
      <div className="input-wrap">
        <input id={id} type={ver ? "text" : "password"} autoComplete={autoComplete} value={value} onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur} aria-invalid={!!error} aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined} />
        <button type="button" className="eye" aria-label={ver ? "Ocultar contraseña" : "Mostrar contraseña"} onClick={() => setVer(!ver)}>
        {ver ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 3l18 18" /><path d="M10.6 5.1A9.9 9.9 0 0 1 12 5c5 0 8.5 4.2 9.6 6.2a1.6 1.6 0 0 1 0 1.6 16 16 0 0 1-2.8 3.5" />
            <path d="M6.6 6.6A15.6 15.6 0 0 0 2.4 11.2a1.6 1.6 0 0 0 0 1.6C3.5 14.8 7 19 12 19a9.6 9.6 0 0 0 5.4-1.6" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M2.4 12.8a1.6 1.6 0 0 1 0-1.6C3.5 9.2 7 5 12 5s8.5 4.2 9.6 6.2a1.6 1.6 0 0 1 0 1.6C20.5 14.8 17 19 12 19s-8.5-4.2-9.6-6.2z" /><circle cx="12" cy="12" r="3" />
          </svg>
        )}
        </button>
      </div>
      {error ? <FieldError id={id} error={error} /> : hint && <p className="field-hint" id={`${id}-hint`}>{hint}</p>}
    </div>
  );
}

export function GananciasCard({ gan }: { gan: Ganancias }) {
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="ctitle"><h2>Ganancia o pérdida realizada por año</h2></div>
      {gan.por_anio.length ? (
        <table className="compact">
          <thead><tr><th>Año</th><th className="num">Ventas</th><th className="num">En pesos</th><th className="num">En dólares</th></tr></thead>
          <tbody>
            {gan.por_anio.map((g) => (
              <tr key={g.anio}>
                <td><b>{g.anio}</b></td>
                <td className="num">{g.ventas}</td>
                <td className={`num ${cls(g.ARS)}`}>{signed(g.ARS, "ARS")}</td>
                <td className={`num ${cls(g.USD)}`}>{signed(g.USD, "USD")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <div className="empty">Todavía no vendiste activos.</div>}
    </div>
  );
}

export function SummaryRows({ rows }: { rows: [string, React.ReactNode, boolean?][] }) {
  return (
    <div className="summary">
      {rows.map(([k, v, tot]) => (
        <div key={k} className={tot ? "tot" : undefined}><span className="muted">{k}</span><b>{v}</b></div>
      ))}
    </div>
  );
}

export function GoLink({ href, className, children }: { href: string; className?: string; children: React.ReactNode }) {
  return <Link href={href} className={className}>{children}</Link>;
}
