"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, guardarToken } from "@/lib/api";
import { PERFILES, RIESGO_MAX } from "@/lib/format";
import type { Perfil } from "@/lib/types";
import { useMe } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { FieldError, PasswordField, RiskDots } from "@/components/ui";

const PERFILES_INFO: Record<Perfil, string> = {
  conservador: "Priorizás cuidar tu capital: bonos y activos defensivos.",
  moderado: "Buscás crecer con un riesgo medido: la mayoría de las acciones.",
  agresivo: "Aceptás más vaivenes para buscar más rendimiento: todo el mercado.",
};

export default function ConfiguracionPage() {
  const { me, setMe, salir } = useMe();
  const { confirm, toast, theme, setTheme, puedeInstalar, esIOS, esStandalone, instalar } = useUI();
  const router = useRouter();
  const cuit = `${me.cuit.slice(0, 2)}-${me.cuit.slice(2, 10)}-${me.cuit.slice(10)}`;
  const comitente = me.cuenta?.numero_comitente;

  // "Cambiar contraseña" desde el submenú del perfil lleva a /perfil/configuracion#password
  useEffect(() => {
    if (window.location.hash === "#password") {
      const p = document.getElementById("passActual");
      p?.scrollIntoView({ behavior: "smooth", block: "center" });
      p?.focus({ preventScroll: true });
    }
  }, []);

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

  return (
    <>
      <div className="head cfg-head">
        <div>
          <Link href="/perfil" className="back-link">‹ Mi perfil</Link>
          <h1>Configuración</h1>
        </div>
      </div>

      <div className="pf-grid">
        <div className="col">
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
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [general, setGeneral] = useState("");
  const [busy, setBusy] = useState(false);
  // Paso 2: a qué correo se mandó el código
  const [enviado, setEnviado] = useState<{ email: string; minutos: number } | null>(null);
  const [codigo, setCodigo] = useState("");

  const fallo = (err: unknown) => {
    const campos = err instanceof ApiError ? err.campos : {};
    if (Object.keys(campos).length) setErrores(campos);
    else setGeneral((err as Error).message);
  };

  // Paso 1: se revisa la contraseña actual y llega un código al correo (la contraseña todavía no cambia)
  const pedir = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setGeneral("");
    const errs: Record<string, string> = {};
    if (!actual) errs.actual = "Ingresá tu contraseña actual";
    if (nueva.length < 8) errs.nueva = "La contraseña nueva tiene que tener al menos 8 caracteres";
    else if (nueva !== rep) errs.rep = "Las contraseñas nuevas no coinciden";
    setErrores(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      const r = await api.pedirCambioPassword(inversorId, actual, nueva);
      setEnviado({ email: r.email, minutos: r.minutos });
      setCodigo("");
      toast(`Te mandamos un código a ${r.email}.`);
    } catch (err) {
      fallo(err);
    } finally {
      setBusy(false);
    }
  };

  // Paso 2: con el código del correo se aplica el cambio
  const confirmar = async (e: React.FormEvent) => {
    e.preventDefault();
    setGeneral("");
    if (!/^\d{6}$/.test(codigo)) return setErrores({ codigo: "Ingresá los 6 dígitos del código" });
    setBusy(true);
    try {
      const r = await api.confirmarCambioPassword(inversorId, codigo);
      guardarToken(r.token); // las otras sesiones dejan de valer; esta sigue con un token nuevo
      setActual(""); setNueva(""); setRep(""); setCodigo(""); setEnviado(null); setErrores({});
      toast("Listo: tu contraseña cambió. Te avisamos por correo.");
    } catch (err) {
      fallo(err);
    } finally {
      setBusy(false);
    }
  };

  if (enviado) {
    return (
      <form className="card" noValidate onSubmit={confirmar} id="password">
        <div className="ctitle"><h2>Confirmá el cambio</h2></div>
        <p className="pf-sub">
          Te mandamos un código de 6 dígitos a <b>{enviado.email}</b>. Vence en {enviado.minutos} minutos.
          Tu contraseña no cambia hasta que lo ingreses.
        </p>
        <div className={`field${errores.codigo ? " invalid" : ""}`}>
          <label htmlFor="pwdCodigo">Código del correo</label>
          <input id="pwdCodigo" className="otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus
            placeholder="000000" value={codigo} aria-invalid={!!errores.codigo}
            aria-describedby={errores.codigo ? "pwdCodigo-err" : undefined}
            onChange={(e) => { setCodigo(e.target.value.replace(/\D/g, "").slice(0, 6)); setErrores({}); }} />
          <FieldError id="pwdCodigo" error={errores.codigo} />
        </div>
        <div className="err" role="alert">{general}</div>
        <div className="form-actions">
          <button type="button" className="btn btn-ghost" onClick={() => { setEnviado(null); setErrores({}); setGeneral(""); }}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Confirmando…" : "Cambiar contraseña"}</button>
        </div>
        <button type="button" className="link-btn" disabled={busy} onClick={() => pedir()}>¿No te llegó? Mandar otro código</button>
      </form>
    );
  }

  return (
    <form className="card" noValidate onSubmit={pedir} id="password">
      <div className="ctitle"><h2>Contraseña</h2></div>
      <p className="pf-sub">Para cambiarla te vamos a mandar un código a tu correo. Al confirmarlo se cierran las otras sesiones abiertas.</p>
      <PasswordField id="passActual" label="Contraseña actual" autoComplete="current-password" value={actual}
        error={errores.actual} onChange={(v) => { setActual(v); setErrores((x) => ({ ...x, actual: "" })); }} />
      <div className="g2e grid" style={{ gap: 10 }}>
        <PasswordField id="passNueva" label="Nueva (mínimo 8)" autoComplete="new-password" value={nueva}
          error={errores.nueva} onChange={(v) => { setNueva(v); setErrores((x) => ({ ...x, nueva: "" })); }} />
        <PasswordField id="passRepetir" label="Repetir la nueva" autoComplete="new-password" value={rep}
          error={errores.rep} onChange={(v) => { setRep(v); setErrores((x) => ({ ...x, rep: "" })); }} />
      </div>
      <div className="err" role="alert">{general}</div>
      <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Enviando código…" : "Enviarme un código"}</button>
    </form>
  );
}
