"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Perfil } from "@/lib/types";
import { useSession } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { PasswordField } from "@/components/ui";

export default function LoginPage() {
  const { estado, ingresar } = useSession();
  const { toast } = useUI();
  const router = useRouter();
  const [tab, setTab] = useState<"in" | "alta">("in");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const [email, setEmail] = useState("alumno@aula.test");
  const [pass, setPass] = useState("");
  const [alta, setAlta] = useState({ nombre: "", email: "", cuit: "", password: "", perfil_riesgo: "moderado" as Perfil });

  // Con sesión abierta se va directo a la app
  useEffect(() => {
    if (estado === "listo") router.replace("/");
  }, [estado, router]);

  const onLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pass) return setErr("Escribí tu contraseña.");
    setBusy(true);
    try {
      await ingresar(await api.ingresar(email, pass));
      setPass("");
    } catch (error) {
      setErr((error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onAlta = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^\d{11}$/.test(alta.cuit.replace(/[-\s]/g, ""))) return setErr("El CUIT tiene que tener 11 dígitos.");
    if (alta.password.length < 8) return setErr("La contraseña tiene que tener al menos 8 caracteres.");
    setBusy(true);
    try {
      // Se crea la cuenta y enseguida se ingresa con la misma contraseña
      const inv = await api.crearInversor(alta);
      toast(`Cuenta comitente N° ${inv.cuenta?.numero_comitente} creada.`);
      await ingresar(await api.ingresar(alta.email, alta.password));
    } catch (error) {
      setErr((error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const setA = (k: keyof typeof alta) => (v: string) => setAlta({ ...alta, [k]: v });

  return (
    <section className="login">
      <LoginBackdrop />
      <div className="login-card">
        <div className="brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="brand-mark" src="/icons/icon-192.png" alt="" />
          <span className="wordmark">IOL <span>Aula</span></span>
        </div>
        <div className="tabs">
          <button type="button" className={`tab${tab === "in" ? " active" : ""}`} onClick={() => { setTab("in"); setErr(""); }}>Ingresar</button>
          <button type="button" className={`tab${tab === "alta" ? " active" : ""}`} onClick={() => { setTab("alta"); setErr(""); }}>Crear cuenta</button>
        </div>

        {tab === "in" ? (
          <form onSubmit={onLogin} noValidate>
            <h1>Ingresá a tu cuenta</h1>
            <div className="field">
              <label htmlFor="loginEmail">Email</label>
              <input id="loginEmail" type="email" autoComplete="username" placeholder="tu@email.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <PasswordField id="loginPass" label="Contraseña" autoComplete="current-password" value={pass} onChange={setPass} />
            <button className="btn btn-primary full" type="submit" disabled={busy}>Ingresar</button>
          </form>
        ) : (
          <form onSubmit={onAlta} noValidate>
            <h1>Crear cuenta</h1>
            <div className="field"><label htmlFor="altaNombre">Nombre y apellido</label><input id="altaNombre" autoComplete="name" value={alta.nombre} onChange={(e) => setA("nombre")(e.target.value)} /></div>
            <div className="field"><label htmlFor="altaEmail">Email</label><input id="altaEmail" type="email" autoComplete="email" value={alta.email} onChange={(e) => setA("email")(e.target.value)} /></div>
            <div className="field"><label htmlFor="altaCuit">CUIT (11 dígitos)</label><input id="altaCuit" inputMode="numeric" placeholder="20-12345678-9" value={alta.cuit} onChange={(e) => setA("cuit")(e.target.value)} /></div>
            <PasswordField id="altaPass" label="Contraseña (mínimo 8 caracteres)" autoComplete="new-password" value={alta.password} onChange={setA("password")} />
            <div className="field">
              <label htmlFor="altaPerfil">Perfil de riesgo</label>
              <select id="altaPerfil" value={alta.perfil_riesgo} onChange={(e) => setA("perfil_riesgo")(e.target.value)}>
                <option value="conservador">Conservador (riesgo hasta 2)</option>
                <option value="moderado">Moderado (riesgo hasta 4)</option>
                <option value="agresivo">Agresivo (cualquier riesgo)</option>
              </select>
            </div>
            <button className="btn btn-primary full" type="submit" disabled={busy}>Crear cuenta</button>
          </form>
        )}
        <div className="err" aria-live="polite">{err}</div>
      </div>
    </section>
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
