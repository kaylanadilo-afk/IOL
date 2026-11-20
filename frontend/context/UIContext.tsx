"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

interface ConfirmOpts {
  title: string;
  body: React.ReactNode;
  okText: string;
  /** Sin onOk es un aviso con un solo botón. */
  onOk?: () => void;
}

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<unknown>;
}

type Theme = "light" | "dark";

interface UIValue {
  toast: (msg: string, bad?: boolean) => void;
  confirm: (opts: ConfirmOpts) => void;
  theme: Theme;
  setTheme: (t: Theme) => void;
  menuOpen: boolean;
  toggleMenu: () => void;
  sheetOpen: boolean;
  setSheetOpen: (v: boolean) => void;
  puedeInstalar: boolean;
  esIOS: boolean;
  esStandalone: boolean;
  instalar: () => void;
  vibrar: (p: number | number[]) => void;
}

const UIContext = createContext<UIValue | null>(null);

function leer(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function escribir(key: string, v: string) {
  try {
    localStorage.setItem(key, v);
  } catch {
    /* sin almacenamiento */
  }
}

export function UIProvider({ children }: { children: React.ReactNode }) {
  const [toastMsg, setToastMsg] = useState<{ msg: string; bad: boolean } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [modal, setModal] = useState<ConfirmOpts | null>(null);
  const okRef = useRef<HTMLButtonElement>(null);
  const [theme, setThemeState] = useState<Theme>("light");
  const [menuOpen, setMenuOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [env, setEnv] = useState({ esIOS: false, esStandalone: false });

  // Preferencias guardadas en este dispositivo (se leen después de hidratar para no desfasar el HTML)
  useEffect(() => {
    queueMicrotask(() => {
      setThemeState(leer("iolAula_tema") === "dark" ? "dark" : "light");
      setMenuOpen(leer("iolAula_menu") === "abierto");
      setEnv({
        esIOS: /iphone|ipad|ipod/i.test(navigator.userAgent),
        esStandalone: window.matchMedia("(display-mode: standalone)").matches
          || (navigator as Navigator & { standalone?: boolean }).standalone === true,
      });
    });
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#0A111D" : "#F4F6F3");
  }, [theme]);

  useEffect(() => {
    document.body.classList.toggle("menu-open", menuOpen);
  }, [menuOpen]);

  const toast = useCallback((msg: string, bad = false) => {
    setToastMsg({ msg, bad });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastMsg(null), 3500);
  }, []);

  const vibrar = useCallback((p: number | number[]) => {
    try {
      navigator.vibrate?.(p);
    } catch {
      /* no soportado */
    }
  }, []);

  // Instalación: Chrome/Edge/Android avisan con beforeinstallprompt; en iPhone se instala desde "Compartir"
  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      setDeferred(null);
      toast("¡Listo! Zeno Investments quedó instalada.");
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    if ("serviceWorker" in navigator && window.isSecureContext && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => { /* sin PWA, la web sigue andando */ });
    }
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, [toast]);

  const instalar = useCallback(() => {
    if (deferred) {
      deferred.prompt();
      deferred.userChoice.then(() => setDeferred(null));
    } else if (env.esIOS) {
      setModal({
        title: "Instalar en iPhone",
        body: <p>1. Tocá el botón <b>Compartir</b> (el cuadrado con la flecha) abajo en Safari.<br />2. Elegí <b>&quot;Agregar a inicio&quot;</b>.<br />3. Abrila desde el ícono: se ve a pantalla completa, como una app.</p>,
        okText: "Entendido",
      });
    } else {
      toast('Abrí el menú del navegador y elegí "Instalar app" o "Agregar a la pantalla principal".');
    }
  }, [deferred, env.esIOS, toast]);

  const value = useMemo<UIValue>(() => ({
    toast,
    confirm: setModal,
    theme,
    setTheme: (t) => {
      setThemeState(t);
      escribir("iolAula_tema", t);
    },
    menuOpen,
    toggleMenu: () => setMenuOpen((v) => {
      escribir("iolAula_menu", v ? "cerrado" : "abierto");
      return !v;
    }),
    sheetOpen,
    setSheetOpen,
    puedeInstalar: !!deferred,
    esIOS: env.esIOS,
    esStandalone: env.esStandalone,
    instalar,
    vibrar,
  }), [toast, theme, menuOpen, sheetOpen, deferred, env, instalar, vibrar]);

  useEffect(() => {
    if (!modal) return;
    okRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setModal(null);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [modal]);

  return (
    <UIContext.Provider value={value}>
      {children}
      {modal && (
        <div className="modal-bg" onClick={(e) => { if (e.target === e.currentTarget) setModal(null); }}>
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="mTitle">
            <h3 id="mTitle">{modal.title}</h3>
            {modal.body}
            <div className="modal-actions">
              {modal.onOk && <button type="button" className="btn btn-ghost" onClick={() => setModal(null)}>Cancelar</button>}
              <button
                type="button"
                className="btn btn-primary"
                ref={okRef}
                onClick={() => {
                  const cb = modal.onOk;
                  setModal(null);
                  cb?.();
                }}
              >
                {modal.okText}
              </button>
            </div>
          </div>
        </div>
      )}
      <div className={`toast${toastMsg?.bad ? " bad" : ""}${toastMsg ? "" : " hidden"}`} role="status" aria-live="polite">
        {toastMsg?.msg}
      </div>
    </UIContext.Provider>
  );
}

export function useUI(): UIValue {
  const ctx = useContext(UIContext);
  if (!ctx) throw new Error("useUI tiene que usarse dentro de <UIProvider>");
  return ctx;
}
