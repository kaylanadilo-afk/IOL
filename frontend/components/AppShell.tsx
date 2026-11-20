"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { iniciales } from "@/lib/format";
import { useSession } from "@/context/SessionContext";
import { useUI } from "@/context/UIContext";
import { textoMercado } from "./ui";
import {
  IcoAdmin, IcoCartera, IcoInicio, IcoMep, IcoMercado, IcoMovimientos, IcoOperaciones, IcoRankings, IcoToggle,
  TabCartera, TabInicio, TabMas, TabMercado,
} from "./icons";

const NAV = [
  { href: "/", label: "Inicio", Ico: IcoInicio },
  { href: "/mercado", label: "Mercado", Ico: IcoMercado },
  { href: "/cartera", label: "Mi cartera", Ico: IcoCartera },
  { href: "/operaciones", label: "Operaciones", Ico: IcoOperaciones },
  { href: "/movimientos", label: "Movimientos", Ico: IcoMovimientos },
  { href: "/mep", label: "Dólar MEP", Ico: IcoMep },
  { href: "/rankings", label: "Rankings", Ico: IcoRankings },
];

/** Sección del menú a la que pertenece una ruta (el detalle de un activo marca "Mercado"). */
function seccion(path: string): string {
  if (path === "/") return "/";
  return "/" + path.split("/")[1];
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { estado, me, mercado, salir, reloadAll } = useSession();
  const { theme, setTheme, toggleMenu, menuOpen, sheetOpen, setSheetOpen, vibrar } = useUI();
  const router = useRouter();
  const path = usePathname();
  const actual = seccion(path);

  // Sin sesión se va al login
  useEffect(() => {
    if (estado === "anonimo") router.replace("/login");
  }, [estado, router]);

  // Administración solo para perfiles autorizados (control de la interfaz)
  useEffect(() => {
    document.body.classList.toggle("is-admin", !!me?.es_admin);
  }, [me?.es_admin]);

  // Al cambiar de pantalla: cerrar hojas y volver arriba
  useEffect(() => {
    setSheetOpen(false);
    window.scrollTo(0, 0);
  }, [path, setSheetOpen]);

  usePullToRefresh(estado === "listo", reloadAll, vibrar);

  if (estado !== "listo" || !me) {
    return <main className="main"><div className="view"><div className="empty">Cargando…</div></div></main>;
  }

  const ini = iniciales(me.nombre);
  // Menú inferior: las secciones que no tienen ícono propio marcan el perfil
  const tab = ["/", "/mercado", "/cartera"].includes(actual) ? actual : actual === "/mep" ? "" : "/perfil";
  const logout = () => { salir(); router.replace("/login"); };
  const tabClick = (href: string) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    vibrar(8);
    e.currentTarget.classList.remove("tapped");
    void e.currentTarget.offsetWidth;
    e.currentTarget.classList.add("tapped");
    if (path === href) { // como en Instagram: tocar la pestaña activa sube arriba
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <>
      {/* Compu: riel de íconos que se abre con el botón de arriba. El perfil va abajo. */}
      <aside className="sidebar" aria-label="Menú">
        <button type="button" className="side-toggle" onClick={toggleMenu} data-tip={menuOpen ? "Cerrar menú" : "Abrir menú"}
          aria-label="Abrir o cerrar el menú" aria-expanded={menuOpen}>
          <IcoToggle /><span className="lbl">Cerrar menú</span>
        </button>
        <nav className="nav">
          {NAV.map(({ href, label, Ico }) => (
            <Link key={href} href={href} className={`nav-item${actual === href ? " active" : ""}`} data-tip={label} aria-label={label}>
              <Ico /><span className="lbl">{label}</span>
            </Link>
          ))}
          <div className="sep admin-only" />
          <Link href="/admin" className={`nav-item admin-only${actual === "/admin" ? " active" : ""}`} data-tip="Administración" aria-label="Administración">
            <IcoAdmin /><span className="lbl">Administración</span>
          </Link>
        </nav>
        <div className="side-bottom">
          <div className="nav-item side-mkt" data-tip="Horario: lunes a viernes de 11 a 17">
            <span className="mkt-dot"><span className={`dot${mercado?.abierto ? " on" : ""}`} /></span>
            <span className="lbl">{textoMercado(mercado)}</span>
          </div>
          <div className="pp-wrap">
            <Link href="/perfil" className={`nav-item side-profile${actual === "/perfil" ? " active" : ""}`} aria-haspopup="true" aria-label="Mi perfil">
              <span className="avatar">{ini}</span>
              <span className="who lbl"><span>{me.nombre}</span><small>{me.es_admin ? "Administrador" : `Perfil ${me.perfil_riesgo}`}</small></span>
            </Link>
            {/* Submenú del perfil: aparece encima al pasar el mouse */}
            <div className="profile-pop" role="menu" aria-label="Opciones de la cuenta">
              <div className="pp-head"><span className="avatar">{ini}</span><div style={{ minWidth: 0 }}><b>{me.nombre}</b><small>{me.email}</small></div></div>
              <Link href="/perfil" className="pp-item" role="menuitem"><span className="mi">◉</span>Ver mi perfil</Link>
              <Link href="/perfil/configuracion#password" className="pp-item" role="menuitem"><span className="mi">⚿</span>Cambiar contraseña</Link>
              <button type="button" className="pp-item" role="menuitem" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
                <span className="mi">◐</span>Modo oscuro<span className="switch" aria-hidden="true" />
              </button>
              <Link href="/admin" className="pp-item admin-only" role="menuitem"><span className="mi">⚙</span>Administración</Link>
              <button type="button" className="pp-item danger" role="menuitem" onClick={logout}><span className="mi">⏻</span>Cerrar sesión</button>
            </div>
          </div>
        </div>
      </aside>

      <main className="main"><div className="view">{children}</div></main>

      {/* Celular: menú inferior estilo Instagram (solo íconos; el activo se rellena) */}
      <nav className="tabbar" aria-label="Menú principal">
        <Link href="/" className={tab === "/" ? "active" : ""} aria-label="Inicio" onClick={tabClick("/")}><TabInicio /></Link>
        <Link href="/mercado" className={tab === "/mercado" ? "active" : ""} aria-label="Mercado" onClick={tabClick("/mercado")}><TabMercado /></Link>
        <button type="button" aria-label="Acciones rápidas" onClick={() => { vibrar(8); setSheetOpen(true); }}><TabMas /></button>
        <Link href="/cartera" className={tab === "/cartera" ? "active" : ""} aria-label="Mi cartera" onClick={tabClick("/cartera")}><TabCartera /></Link>
        <Link href="/perfil" className={tab === "/perfil" ? "active" : ""} aria-label="Mi perfil y más opciones" onClick={tabClick("/perfil")}>
          <span className="avatar">{ini}</span>
        </Link>
      </nav>

      {/* Acciones rápidas (botón +) */}
      <div className={`sheet-bg${sheetOpen ? " open" : ""}`} onClick={() => setSheetOpen(false)} />
      <div className={`sheet${sheetOpen ? " open" : ""}`} role="dialog" aria-modal="true" aria-label="Acciones rápidas">
        <div className="grabber" />
        <h3>¿Qué querés hacer?</h3>
        <div className="actions-grid">
          {[
            ["/mercado", "#0a9f66", "↗", "Comprar"], ["/cartera", "#d64545", "↘", "Vender"], ["/mep", "#1663a8", "$", "Dólar MEP"],
            ["/movimientos", "#8b5cf6", "＋", "Depositar"], ["/movimientos", "#f08c2e", "−", "Extraer"], ["/operaciones", "#0f3b6e", "☰", "Historial"],
          ].map(([href, color, ico, label]) => (
            <Link key={label} href={href} className="action" onClick={() => setSheetOpen(false)}>
              <span className="ai" style={{ background: color }}>{ico}</span>{label}
            </Link>
          ))}
        </div>
      </div>
      <div className="ptr" id="ptr" aria-hidden="true"><span>↻</span></div>
    </>
  );
}

/** Deslizar hacia abajo para actualizar (en la app instalada no existe el del navegador). */
function usePullToRefresh(activo: boolean, reload: () => Promise<void>, vibrar: (p: number) => void) {
  const reloadRef = useRef(reload);
  useEffect(() => {
    reloadRef.current = reload;
  }, [reload]);
  useEffect(() => {
    if (!activo) return;
    let y0: number | null = null, dy = 0;
    const ptr = () => document.getElementById("ptr");
    const start = (e: TouchEvent) => {
      y0 = window.scrollY <= 0 && !document.querySelector(".sheet.open,.trade-card.open,.modal-bg") ? e.touches[0].clientY : null;
      dy = 0;
    };
    const move = (e: TouchEvent) => {
      const el = ptr();
      if (y0 == null || !el) return;
      dy = Math.max(0, e.touches[0].clientY - y0);
      el.style.transform = `translateY(${Math.min(dy, 150) - 130}px) rotate(${dy * 2.5}deg)`;
    };
    const end = () => {
      const el = ptr();
      if (y0 == null || !el) return;
      y0 = null;
      if (dy > 80) {
        vibrar(10);
        el.classList.add("spin");
        el.style.transform = "translateY(0)";
        reloadRef.current().catch(() => {}).then(() => { el.classList.remove("spin"); el.style.transform = ""; });
      } else {
        el.style.transform = "";
      }
    };
    document.addEventListener("touchstart", start, { passive: true });
    document.addEventListener("touchmove", move, { passive: true });
    document.addEventListener("touchend", end);
    return () => {
      document.removeEventListener("touchstart", start);
      document.removeEventListener("touchmove", move);
      document.removeEventListener("touchend", end);
    };
  }, [activo, vibrar]);
}
