"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Perfil, Sesion } from "@/lib/types";
import { errorCuit, errorEmail, errorNombre, errorPassword, formatoCuit } from "@/lib/validaciones";
import { useSession } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { FieldError, PasswordField, TextField } from "@/components/ui";

type CampoAlta = "nombre" | "email" | "cuit" | "password" | "perfil_riesgo";
type Errores = Partial<Record<CampoAlta, string>>;
const ORDEN: CampoAlta[] = ["nombre", "email", "cuit", "password"];
const ID: Record<CampoAlta, string> = { nombre: "altaNombre", email: "altaEmail", cuit: "altaCuit", password: "altaPass", perfil_riesgo: "altaPerfil" };

export default function LoginPage() {
  const { estado, ingresar } = useSession();
  const { toast } = useUI();
  const router = useRouter();
  const [tab, setTab] = useState<"in" | "alta" | "admin">("in");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [loginErr, setLoginErr] = useState<{ email?: string; pass?: string }>({});
  const [alta, setAlta] = useState({ nombre: "", email: "", cuit: "", password: "", perfil_riesgo: "moderado" as Perfil });
  const [errores, setErrores] = useState<Errores>({});
  const [revisandoEmail, setRevisandoEmail] = useState(false);
  const emailRevisado = useRef("");
  // Correo pendiente de confirmar: mientras haya uno, se muestra la pantalla del código
  const [verificando, setVerificando] = useState<string | null>(null);

  // Con sesión abierta se va directo a la app (el administrador, a su sección)
  useEffect(() => {
    if (estado === "listo") router.replace(tab === "admin" ? "/admin" : "/");
  }, [estado, router, tab]);

  const irA = (t: typeof tab) => {
    setTab(t);
    setErr("");
    setPass("");
    setLoginErr({});
    setErrores({});
    if (t === "admin") setEmail("");
  };

  const enfocar = (id: string) => requestAnimationFrame(() => document.getElementById(id)?.focus());

  const onLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    const errs = { email: errorEmail(email) ?? undefined, pass: pass ? undefined : "Ingresá tu contraseña" };
    setLoginErr(errs);
    if (errs.email || errs.pass) return enfocar(errs.email ? "loginEmail" : "loginPass");
    setBusy(true);
    try {
      const sesion = await api.ingresar(email, pass);
      // El acceso de administración es solo para cuentas con ese permiso
      if (tab === "admin" && !sesion.inversor.es_admin) {
        setErr("Esta cuenta no tiene permisos de administrador.");
        return;
      }
      await ingresar(sesion);
      setPass("");
    } catch (error) {
      if (error instanceof ApiError && error.codigo === "EmailNoVerificadoError") {
        setVerificando(email.trim().toLowerCase());
      } else {
        setErr((error as Error).message);
      }
    } finally {
      setBusy(false);
    }
  };

  // Cada campo se revisa al salir de él; el error se va apenas se corrige
  const validar = (k: CampoAlta, v: string): string | null =>
    k === "nombre" ? errorNombre(v) : k === "email" ? errorEmail(v) : k === "cuit" ? errorCuit(v) : k === "password" ? errorPassword(v) : null;

  const setA = (k: CampoAlta) => (v: string) => {
    const valor = k === "cuit" ? formatoCuit(v) : v;
    setAlta((a) => ({ ...a, [k]: valor }));
    if (errores[k]) setErrores((er) => ({ ...er, [k]: validar(k, valor) ?? undefined }));
  };

  const alSalir = (k: CampoAlta) => {
    const v = alta[k];
    if (!v) return; // no se marca en rojo un campo que todavía no se llenó
    const msg = validar(k, v);
    setErrores((er) => ({ ...er, [k]: msg ?? undefined }));
    // El formato está bien: la API revisa que el dominio del correo exista y reciba emails
    if (k === "email" && !msg && emailRevisado.current !== v) {
      emailRevisado.current = v;
      setRevisandoEmail(true);
      api.validarEmail(v)
        .then((r) => { if (!r.valido && r.mensaje) setErrores((er) => ({ ...er, email: r.mensaje ?? undefined })); })
        .catch(() => { /* si no se puede revisar ahora, lo revisa la API al crear la cuenta */ })
        .finally(() => setRevisandoEmail(false));
    }
  };

  const onAlta = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    const errs: Errores = {};
    for (const k of ORDEN) {
      const m = validar(k, alta[k]);
      if (m) errs[k] = m;
    }
    setErrores(errs);
    const primero = ORDEN.find((k) => errs[k]);
    if (primero) return enfocar(ID[primero]);
    setBusy(true);
    try {
      // Se crea la cuenta; si hay que confirmar el correo, se pide el código que le llegó
      const datos = { ...alta, cuit: alta.cuit.replace(/\D/g, "") };
      const inv = await api.crearInversor(datos);
      if (!inv.email_verificado) {
        setVerificando(inv.email);
        return;
      }
      toast(`Cuenta comitente N° ${inv.cuenta?.numero_comitente} creada.`);
      await ingresar(await api.ingresar(datos.email, datos.password));
    } catch (error) {
      const campos = error instanceof ApiError ? (error.campos as Errores) : {};
      const conCampo = Object.keys(campos).filter((k): k is CampoAlta => k in ID);
      if (conCampo.length) {
        setErrores((er) => ({ ...er, ...campos }));
        enfocar(ID[ORDEN.find((k) => campos[k]) ?? conCampo[0]]);
      } else {
        setErr((error as Error).message);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="login">
      <LoginBackdrop />
      <div className="login-main">
        <header className="login-brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="brand-mark" src="/brand/zeno-mark.png" alt="" />
          <div>
            <span className="wordmark">Zeno <span>Investments</span></span>
            <p>Mercado de capitales<span className="hide-sm"> · Argentina</span></p>
          </div>
        </header>
        <div className="login-card">
          {verificando ? (
            <VerificarCorreo email={verificando}
              onListo={async (s) => { toast(`¡Listo! Tu cuenta comitente N° ${s.inversor.cuenta?.numero_comitente} está activa.`); await ingresar(s); }}
              onVolver={() => { setVerificando(null); setErr(""); }} />
          ) : (<>
          {tab === "admin" ? (
            <div className="admin-badge">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true"><path d="M12 3l7.5 3v5.5c0 4.6-3.2 8.3-7.5 9.5-4.3-1.2-7.5-4.9-7.5-9.5V6z" /></svg>
              Acceso restringido
            </div>
          ) : (
            <div className="tabs">
              <button type="button" className={`tab${tab === "in" ? " active" : ""}`} onClick={() => irA("in")}>Ingresar</button>
              <button type="button" className={`tab${tab === "alta" ? " active" : ""}`} onClick={() => irA("alta")}>Crear cuenta</button>
            </div>
          )}

        {tab !== "alta" ? (
          <form onSubmit={onLogin} noValidate>
            <h1>{tab === "admin" ? "Administración" : "Ingresá a tu cuenta"}</h1>
            {tab === "admin" && <p className="login-sub">Ingresá con una cuenta de administrador.</p>}
            <TextField id="loginEmail" label="Email" type="email" autoComplete="username" placeholder={tab === "admin" ? "admin@empresa.com" : "tu@email.com"}
              value={email} error={loginErr.email} onChange={(v) => { setEmail(v); if (loginErr.email) setLoginErr((l) => ({ ...l, email: errorEmail(v) ?? undefined })); }} />
            <PasswordField id="loginPass" label="Contraseña" autoComplete="current-password" value={pass} error={loginErr.pass}
              onChange={(v) => { setPass(v); if (v) setLoginErr((l) => ({ ...l, pass: undefined })); }} />
            <button className="btn btn-primary full" type="submit" disabled={busy}>{tab === "admin" ? "Ingresar como administrador" : "Ingresar"}</button>
          </form>
        ) : (
          <form onSubmit={onAlta} noValidate>
            <h1>Crear cuenta</h1>
            <TextField id="altaNombre" label="Nombre y apellido" autoComplete="name" value={alta.nombre} error={errores.nombre}
              onChange={setA("nombre")} onBlur={() => alSalir("nombre")} />
            <div className={revisandoEmail ? "checking-wrap" : undefined}>
              <TextField id="altaEmail" label="Email" type="email" autoComplete="email" placeholder="nombre@gmail.com" value={alta.email}
                error={errores.email} onChange={setA("email")} onBlur={() => alSalir("email")} />
            </div>
            <TextField id="altaCuit" label="CUIT" inputMode="numeric" placeholder="20-12345678-9" value={alta.cuit} error={errores.cuit}
              hint="Lo encontrás en tu constancia de AFIP o en tu DNI (CUIL)." onChange={setA("cuit")} onBlur={() => alSalir("cuit")} />
            <PasswordField id="altaPass" label="Contraseña" autoComplete="new-password" value={alta.password} error={errores.password}
              hint="Mínimo 8 caracteres." onChange={setA("password")} onBlur={() => alSalir("password")} />
            <div className="field">
              <label htmlFor="altaPerfil">Perfil de riesgo</label>
              <select id="altaPerfil" value={alta.perfil_riesgo} onChange={(e) => setAlta((a) => ({ ...a, perfil_riesgo: e.target.value as Perfil }))}>
                <option value="conservador">Conservador (riesgo hasta 2)</option>
                <option value="moderado">Moderado (riesgo hasta 4)</option>
                <option value="agresivo">Agresivo (cualquier riesgo)</option>
              </select>
            </div>
            <button className="btn btn-primary full" type="submit" disabled={busy}>Crear cuenta</button>
          </form>
        )}
        <div className="err" role="alert">{err}</div>
          </>)}
        </div>
      </div>
      <button type="button" className="login-admin" onClick={() => irA(tab === "admin" ? "in" : "admin")}>
        {tab === "admin" ? "← Volver al ingreso de inversores" : "Ingresar como administrador"}
      </button>
    </section>
  );
}

/* ===================== CONFIRMAR EL CORREO ===================== */
function VerificarCorreo({ email, onListo, onVolver }: { email: string; onListo: (s: Sesion) => Promise<void>; onVolver: () => void }) {
  const [codigo, setCodigo] = useState("");
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [busy, setBusy] = useState(false);
  const [espera, setEspera] = useState(60);

  // Cuenta regresiva para poder pedir otro código
  useEffect(() => {
    if (espera <= 0) return;
    const t = setTimeout(() => setEspera((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [espera]);

  const confirmar = async (valor = codigo) => {
    if (valor.length !== 6) return setError("Ingresá los 6 dígitos del código");
    setBusy(true);
    setError("");
    try {
      await onListo(await api.verificarEmail(email, valor));
    } catch (e) {
      setError(e instanceof ApiError ? (e.campos.codigo ?? e.message) : (e as Error).message);
      setCodigo("");
      requestAnimationFrame(() => document.getElementById("codigo")?.focus());
    } finally {
      setBusy(false);
    }
  };

  const reenviar = async () => {
    setError("");
    try {
      const r = await api.reenviarCodigo(email);
      setEspera(r.espera);
      setAviso("Te mandamos un código nuevo.");
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <form onSubmit={(e) => { e.preventDefault(); confirmar(); }} noValidate>
      <div className="verif-ico" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5" /><path d="m4 7 8 6 8-6" /></svg>
      </div>
      <h1>Confirmá tu correo</h1>
      <p className="login-sub">Te mandamos un código de 6 dígitos a <b className="verif-mail">{email}</b>. Si no lo ves, revisá la carpeta de spam.</p>
      <div className={`field${error ? " invalid" : ""}`}>
        <label htmlFor="codigo">Código de verificación</label>
        <input id="codigo" className="otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus
          placeholder="000000" value={codigo} aria-invalid={!!error} aria-describedby={error ? "codigo-err" : undefined}
          onChange={(e) => {
            const v = e.target.value.replace(/\D/g, "").slice(0, 6);
            setCodigo(v);
            setError("");
            if (v.length === 6) confirmar(v); // al completar los 6 dígitos se confirma solo
          }} />
        <FieldError id="codigo" error={error} />
      </div>
      <button className="btn btn-primary full" type="submit" disabled={busy}>{busy ? "Confirmando…" : "Confirmar correo"}</button>
      <div className="verif-acciones">
        {espera > 0
          ? <span className="muted">Podés pedir otro código en {espera} s</span>
          : <button type="button" className="link-btn" onClick={reenviar}>Reenviar código</button>}
        <button type="button" className="link-btn" onClick={onVolver}>Usar otro correo</button>
      </div>
      {aviso && !error && <p className="verif-aviso" role="status">{aviso}</p>}
    </form>
  );
}

/* ===================== FONDO DECORATIVO ===================== */
// Dos cotizaciones inventadas (fijas, para que el HTML del servidor y el del navegador coincidan)
const SERIE_A = [52, 55, 51, 58, 56, 61, 57, 63, 60, 66, 62, 64, 70, 67, 73, 69, 76, 72, 78, 75, 82, 79, 85, 83, 90];
const SERIE_B = [38, 35, 39, 36, 42, 40, 37, 44, 41, 46, 43, 48, 45, 42, 49, 47, 52, 50, 55, 51, 57, 54, 59, 56, 61];

function trazo(serie: number[], W: number, H: number) {
  const paso = W / (serie.length - 1);
  return serie.map((v, i) => `${i ? "L" : "M"}${(i * paso).toFixed(1)} ${(H - (v / 100) * H).toFixed(1)}`).join("");
}

function LoginBackdrop() {
  const W = 1200, H = 400;
  const a = trazo(SERIE_A, W, H), b = trazo(SERIE_B, W, H);
  return (
    <div className="login-bg" aria-hidden="true">
      <div className="login-glow g1" />
      <div className="login-glow g2" />
      <div className="login-grid" />
      <svg className="login-lines" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="lbA" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" style={{ stopColor: "var(--up)", stopOpacity: 0.18 }} />
            <stop offset="1" style={{ stopColor: "var(--up)", stopOpacity: 0 }} />
          </linearGradient>
        </defs>
        <path d={`${a}L${W} ${H}L0 ${H}Z`} fill="url(#lbA)" />
        <path d={a} fill="none" style={{ stroke: "var(--up)" }} strokeOpacity=".45" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        <path d={b} fill="none" style={{ stroke: "var(--brand2)" }} strokeOpacity=".35" strokeWidth="1.5" strokeDasharray="6 6" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      </svg>
    </div>
  );
}
