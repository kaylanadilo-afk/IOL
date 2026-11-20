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
    <>
      <span className="risk" title={`Nivel de riesgo ${n} de 5`}>
        {[1, 2, 3, 4, 5].map((i) => <i key={i} className={i <= n ? "on" : ""} />)}
      </span>{" "}
      <small className="muted">{n}</small>
    </>
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
  return m.en_horario ? "Mercado abierto" : "Abierto (demo)";
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

export function PasswordField({ id, label, autoComplete, value, onChange }: {
  id: string; label: string; autoComplete: string; value: string; onChange: (v: string) => void;
}) {
  const [ver, setVer] = useState(false);
  return (
    <div className="field pass-field">
      <label htmlFor={id}>{label}</label>
      <input id={id} type={ver ? "text" : "password"} autoComplete={autoComplete} value={value} onChange={(e) => onChange(e.target.value)} />
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
