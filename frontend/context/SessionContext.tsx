"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, guardarToken, leerToken } from "@/lib/api";
import { useUI } from "@/context/UIContext";
import { limpiarCache } from "@/lib/useAsync";
import type { Activo, EstadoMercado, Inversor, Sesion } from "@/lib/types";

type Estado = "cargando" | "anonimo" | "listo";

interface SessionValue {
  estado: Estado;
  me: Inversor | null;
  activos: Activo[];
  favs: number[];
  mercado: EstadoMercado | null;
  /** Cambia cada vez que llegan precios nuevos (cada 30 s con precios reales). */
  liveTick: number;
  /** Cambia cuando el usuario pide recargar todo (deslizar hacia abajo, Reintentar…). */
  reloadKey: number;
  preciosReales: boolean;
  /** Avisos de alertas de precio sin leer (se revisan cada 30 s). */
  avisos: number;
  refreshAvisos: () => Promise<void>;
  cuentaId: number;
  ingresar: (s: Sesion) => Promise<void>;
  salir: () => void;
  refreshBase: () => Promise<void>;
  reloadAll: () => Promise<void>;
  setMe: (inv: Inversor) => void;
  setFavs: (ids: number[]) => void;
  setMercado: (m: EstadoMercado) => void;
  activoById: (id: number) => Activo | undefined;
  activoByTicker: (t: string) => Activo | undefined;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [estado, setEstado] = useState<Estado>("cargando");
  const [me, setMe] = useState<Inversor | null>(null);
  const [activos, setActivos] = useState<Activo[]>([]);
  const [favs, setFavs] = useState<number[]>([]);
  const [mercado, setMercado] = useState<EstadoMercado | null>(null);
  const [liveTick, setLiveTick] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [avisos, setAvisos] = useState(0);
  const avisosRef = useRef<number | null>(null);
  const { toast } = useUI();

  // Si llegó un aviso nuevo mientras la app está abierta, se muestra también como mensaje
  const refreshAvisos = useCallback(async () => {
    try {
      const r = await api.avisos();
      if (avisosRef.current != null && r.no_leidas > avisosRef.current && r.items[0]) toast(r.items[0].titulo);
      avisosRef.current = r.no_leidas;
      setAvisos(r.no_leidas);
    } catch {
      /* sin avisos por ahora: se reintenta en el próximo ciclo */
    }
  }, [toast]);
  const meRef = useRef<Inversor | null>(null);
  useEffect(() => {
    meRef.current = me;
  }, [me]);

  const refreshBase = useCallback(async () => {
    const inv = meRef.current;
    if (!inv) return;
    const [yo, lista, favoritos, m] = await Promise.all([
      api.inversor(inv.id), api.activos(), api.favoritos(inv.id), api.mercado(),
    ]);
    setMe(yo);
    setActivos(lista);
    setFavs(favoritos.map((a) => a.id));
    setMercado(m);
  }, []);

  const ingresar = useCallback(async (s: Sesion) => {
    guardarToken(s.token);
    meRef.current = s.inversor;
    setMe(s.inversor);
    await refreshBase();
    setEstado("listo");
    refreshAvisos();
  }, [refreshBase, refreshAvisos]);

  const salir = useCallback(() => {
    guardarToken(null);
    limpiarCache();
    avisosRef.current = null;
    setAvisos(0);
    meRef.current = null;
    setMe(null);
    setEstado("anonimo");
  }, []);

  const reloadAll = useCallback(async () => {
    await refreshBase();
    setReloadKey((k) => k + 1);
  }, [refreshBase]);

  // Si hay una sesión guardada (token válido) se entra directo; si venció, se pide la contraseña
  useEffect(() => {
    const t = leerToken();
    if (!t) {
      queueMicrotask(() => setEstado("anonimo"));
      return;
    }
    api.yo()
      .then((inv) => ingresar({ token: t, inversor: inv }))
      .catch(() => salir());
  }, [ingresar, salir]);

  // Cada 30 s: estado del mercado y, con precios reales, las cotizaciones del catálogo
  useEffect(() => {
    if (estado !== "listo") return;
    const id = setInterval(async () => {
      if (document.hidden) return;
      try {
        refreshAvisos();
        const m = await api.mercado();
        setMercado(m);
        if (m.precios?.modo !== "reales") return;
        setActivos(await api.activos());
        setLiveTick((n) => n + 1);
      } catch {
        /* se reintenta en el próximo ciclo */
      }
    }, 30000);
    return () => clearInterval(id);
  }, [estado, refreshAvisos]);

  const value = useMemo<SessionValue>(() => ({
    estado, me, activos, favs, mercado, liveTick, reloadKey,
    preciosReales: mercado?.precios?.modo === "reales",
    avisos, refreshAvisos,
    cuentaId: me?.cuenta?.id ?? 0,
    ingresar, salir, refreshBase, reloadAll, setMe, setFavs, setMercado,
    activoById: (id) => activos.find((a) => a.id === id),
    activoByTicker: (t) => activos.find((a) => a.ticker === t),
  }), [estado, me, activos, favs, mercado, liveTick, reloadKey, avisos, refreshAvisos, ingresar, salir, refreshBase, reloadAll]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession tiene que usarse dentro de <SessionProvider>");
  return ctx;
}

/** Igual que useSession, pero con el inversor garantizado (para las pantallas de la app). */
export function useMe() {
  const s = useSession();
  return { ...s, me: s.me as Inversor };
}
