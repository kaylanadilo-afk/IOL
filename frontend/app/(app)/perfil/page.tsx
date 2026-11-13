"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, guardarToken } from "@/lib/api";
import { compacto, iniciales, PERFILES, RIESGO_MAX } from "@/lib/format";
import type { Perfil } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { ErrorCard, Loading, PasswordField, RiskDots } from "@/components/ui";

const PERFILES_INFO: Record<Perfil, string> = {
  conservador: "Priorizás cuidar tu capital: bonos y activos defensivos.",
  moderado: "Buscás crecer con un riesgo medido: la mayoría de las acciones.",
  agresivo: "Aceptás más vaivenes para buscar más rendimiento: todo el mercado.",
};

export default function PerfilPage() {
  const { me, cuentaId, favs, reloadKey, setMe, salir } = useMe();
  const { confirm, toast, theme, setTheme, puedeInstalar, esIOS, esStandalone, instalar } = useUI();
  const router = useRouter();
  const { data, error, reload } = useAsync(
    () => Promise.all([api.cartera(cuentaId), api.operaciones(cuentaId)]),
    [cuentaId, reloadKey],
  );

  // "Cambiar contraseña" desde el submenú del perfil lleva a /perfil#password
  useEffect(() => {
    if (data && window.location.hash === "#password") {
      const p = document.getElementById("passActual");
      p?.scrollIntoView({ behavior: "smooth", block: "center" });
      p?.focus({ preventScroll: true });
    }
  }, [data]);

  if (error) return <ErrorCard message={error} onRetry={reload} />;
  if (!data) return <Loading />;
  const [cart, ops] = data;
  const cuit = `${me.cuit.slice(0, 2)}-${me.cuit.slice(2, 10)}-${me.cuit.slice(10)}`;
  const comitente = me.cuenta?.numero_comitente;

  const elegirPerfil = (nuevo: Perfil) => {
    if (nuevo === me.perfil_riesgo) return;
    confirm({
      title: `Cambiar a perfil ${nuevo}`,
      body: <p className="muted">Vas a poder comprar activos con nivel de riesgo hasta {RIESGO_MAX[nuevo]}. Las ventas no tienen restricción.</p>,
      okText: "Cambiar perfil",
      onOk: () => api.cambiarPerfil(me.id, nuevo)
        .then((inv) => { setMe(inv); toast(`Tu perfil ahora es ${inv.perfil_riesgo}.`); })
        .catch((err: Error) => toast(err.message, true)),
    });
  };

  const copiar = (v: string) => (
    <button type="button" className="copy" aria-label={`Copiar ${v}`} onClick={() => {
      (navigator.clipboard ? navigator.clipboard.writeText(v) : Promise.reject()).then(() => toast(`Copiado: ${v}`), () => toast(v));
    }}>Copiar</button>
  );

  // En el celular, las secciones que no están en el menú de abajo
  const secciones: [string, string, string][] = [["/operaciones", "☰", "Operaciones"], ["/movimientos", "⇄", "Movimientos y depósitos"], ["/mep", "$", "Dólar MEP"], ["/rankings", "▲", "Rankings del mercado"]];
  if (me.es_admin) secciones.push(["/admin", "⚙", "Administración"]);

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

      <div className="card menu-list only-m" style={{ padding: "2px 16px", marginBottom: 12 }}>
        {secciones.map(([href, ico, label]) => (
          <Link key={href} href={href} className="menu-item"><span className="mi">{ico}</span>{label}<span className="chev">›</span></Link>
        ))}
      </div>

      <div className="pf-grid">
        <div className="col">
          <div className="card">
            <div className="ctitle"><h2>Perfil de inversor</h2></div>
            <p className="pf-sub">Define qué podés comprar. Las ventas no tienen restricción.</p>
            <div className="risk-opts">
              {PERFILES.map((p) => (
                <button key={p} type="button" className={`risk-opt${p === me.perfil_riesgo ? " on" : ""}`} aria-pressed={p === me.perfil_riesgo} onClick={() => elegirPerfil(p)}>
                  <b>{p[0].toUpperCase() + p.slice(1)}</b>
                  <span><RiskDots n={RIESGO_MAX[p]} /></span>
                  <small>{PERFILES_INFO[p]}</small>
                </button>
              ))}
            </div>
          </div>
          <div className="card">
            <div className="ctitle"><h2>Preferencias</h2></div>
            <div className="pref-row">
              <div>Tema<small>Claro u oscuro, en este dispositivo</small></div>
              <div className="tabs">
                <button type="button" className={`tab${theme !== "dark" ? " active" : ""}`} onClick={() => setTheme("light")}>Claro</button>
                <button type="button" className={`tab${theme === "dark" ? " active" : ""}`} onClick={() => setTheme("dark")}>Oscuro</button>
              </div>
            </div>
            {!esStandalone && (puedeInstalar || esIOS) && (
              <div className="pref-row">
                <div>App en el celular<small>Instalala para abrirla como una app</small></div>
                <button type="button" className="btn btn-ghost btn-sm" onClick={instalar}>Instalar</button>
              </div>
            )}
            <div className="pref-row">
              <div>Sesión<small>Vas a tener que ingresar tu contraseña de nuevo</small></div>
              <button type="button" className="btn btn-ghost btn-sm" style={{ color: "var(--down)" }} onClick={() => { salir(); router.replace("/login"); }}>Cerrar sesión</button>
            </div>
          </div>
        </div>
        <div className="col">
          <div className="card">
            <div className="ctitle"><h2>Datos de la cuenta</h2></div>
            <dl className="kv">
              <dt>Email</dt><dd>{me.email}</dd>{copiar(me.email)}
              <dt>CUIT</dt><dd>{cuit}</dd>{copiar(cuit)}
              <dt>Comitente</dt><dd>N° {comitente}</dd>{copiar(String(comitente))}
              <dt>Cliente desde</dt><dd>{new Date(me.fecha_alta).toLocaleDateString("es-AR", { day: "numeric", month: "long", year: "numeric" })}</dd><span />
            </dl>
          </div>
          <PasswordCard inversorId={me.id} />
        </div>
      </div>
    </>
  );
}

function PasswordCard({ inversorId }: { inversorId: number }) {
  const { toast } = useUI();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [rep, setRep] = useState("");
  const [msg, setMsg] = useState<{ text: string; ok: boolean }>({ text: "", ok: false });
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (nueva.length < 8) return setMsg({ text: "La contraseña nueva tiene que tener al menos 8 caracteres.", ok: false });
    if (nueva !== rep) return setMsg({ text: "Las contraseñas nuevas no coinciden.", ok: false });
    setBusy(true);
    try {
      const r = await api.cambiarPassword(inversorId, actual, nueva);
      guardarToken(r.token); // las otras sesiones dejan de valer; esta sigue con un token nuevo
      setActual(""); setNueva(""); setRep("");
      setMsg({ text: "Listo: tu contraseña cambió.", ok: true });
      toast("Contraseña actualizada.");
    } catch (err) {
      setMsg({ text: (err as Error).message, ok: false });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card" noValidate onSubmit={onSubmit} id="password">
      <div className="ctitle"><h2>Contraseña</h2></div>
      <p className="pf-sub">Al cambiarla, se cierran las otras sesiones abiertas.</p>
      <PasswordField id="passActual" label="Contraseña actual" autoComplete="current-password" value={actual} onChange={setActual} />
      <div className="g2e grid" style={{ gap: 10 }}>
        <PasswordField id="passNueva" label="Nueva (mínimo 8)" autoComplete="new-password" value={nueva} onChange={setNueva} />
        <PasswordField id="passRepetir" label="Repetir la nueva" autoComplete="new-password" value={rep} onChange={setRep} />
      </div>
      <button className="btn btn-primary" type="submit" disabled={busy}>Cambiar contraseña</button>
      <div className={`form-msg${msg.ok ? " up" : ""}`}>{msg.text}</div>
    </form>
  );
}
