"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

// Últimas respuestas en memoria: al volver a una pantalla se muestra enseguida lo último que se vio
// y se actualiza por detrás, en vez de mostrar "Cargando…" cada vez que se cambia de sección.
const cache = new Map<string, unknown>();
const MAX_CACHE = 60;

function guardar(key: string, valor: unknown) {
  cache.delete(key);
  cache.set(key, valor);
  if (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value as string);
}

/** Ejecuta `fn` cuando cambian `deps` y descarta respuestas viejas (si el usuario cambió de filtro, etc.). */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[], enabled = true): AsyncState<T> {
  // La misma llamada con los mismos parámetros comparte entrada (por ejemplo, la cartera de una cuenta)
  const key = fn.toString() + JSON.stringify(deps);
  const [data, setData] = useState<T | null>(() => (cache.get(key) as T | undefined) ?? null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(() => !cache.has(key));
  const [nonce, setNonce] = useState(0);
  const seq = useRef(0);
  const fnRef = useRef(fn);
  const keyRef = useRef(key);
  // Se actualiza antes del efecto de carga (los efectos corren en orden)
  useEffect(() => {
    fnRef.current = fn;
    keyRef.current = key;
  });

  useEffect(() => {
    if (!enabled) return;
    const mine = ++seq.current;
    const k = keyRef.current;
    Promise.resolve()
      .then(() => {
        if (mine === seq.current) setLoading(true);
        return fnRef.current();
      })
      .then((d) => {
        guardar(k, d);
        if (mine !== seq.current) return;
        setData(d);
        setError(null);
      })
      .catch((e: Error) => {
        if (mine !== seq.current) return;
        setError(e.message);
      })
      .finally(() => {
        if (mine === seq.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, enabled]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, reload };
}

/** Borra las respuestas guardadas (al cerrar sesión, para que otro usuario no vea datos ajenos). */
export function limpiarCache() {
  cache.clear();
}
