"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { InformeAgente } from "@/lib/types";
import { useMe } from "@/context/SessionContext";
import { Analizando, Briefing, ChatAgente, Recomendaciones, RiesgosYPasos, ZenoLinea } from "@/components/agente";

type Estado = { tipo: "cargando" } | { tipo: "sin-config" } | { tipo: "error"; msg: string } | { tipo: "listo"; inf: InformeAgente };

export default function AgentePage() {
  const { me } = useMe();
  useEffect(() => { document.title = "Zeno AI · Zeno Investments"; }, []);
  const [estado, setEstado] = useState<Estado>({ tipo: "cargando" });
  const [configurado, setConfigurado] = useState(true);

  const cargar = useCallback(async (actualizar = false) => {
    setEstado({ tipo: "cargando" });
    try {
      const est = await api.agenteEstado();
      setConfigurado(est.configurado);
      if (!est.configurado) return setEstado({ tipo: "sin-config" });
      setEstado({ tipo: "listo", inf: await api.agenteInforme(actualizar) });
    } catch (e) {
      setEstado({ tipo: "error", msg: (e as Error).message });
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => { void cargar(); });
  }, [cargar]);

  return (
    <div className="ag">
      <header className="ag-head">
        <div className="ag-id">
          <ZenoLinea size={46} pensando={estado.tipo === "cargando"} />
          <div>
            <h1>Zeno AI</h1>
            <p>Tu analista de inversiones · perfil {me.perfil_riesgo}</p>
          </div>
        </div>
        {estado.tipo === "listo" && (
          <button type="button" className="btn btn-ghost btn-sm ag-actualizar" onClick={() => cargar(true)}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6" /></svg>
            Volver a analizar
          </button>
        )}
      </header>

      <div className="ag-layout">
        <div className="ag-main">
          {estado.tipo === "cargando" && <Analizando />}
          {estado.tipo === "sin-config" && <SinConfigurar />}
          {estado.tipo === "error" && (
            <div className="card ag-err">
              <h2>No se pudo armar el análisis</h2>
              <p className="muted">{estado.msg}</p>
              <button type="button" className="btn btn-primary" onClick={() => cargar(true)}>Intentar de nuevo</button>
            </div>
          )}
          {estado.tipo === "listo" && (
            <div className="ag-informe">
              <Briefing inf={estado.inf} />
              <Recomendaciones recs={estado.inf.recomendaciones} descartadas={estado.inf.descartadas} situacion={estado.inf.situacion} />
              <RiesgosYPasos riesgos={estado.inf.riesgos} pasos={estado.inf.proximos_pasos} />
              {!!estado.inf.fuentes?.length && (
                <ul className="ag-fuentes" aria-label="Datos usados en el análisis">
                  {estado.inf.fuentes.map((f) => <li key={f}>{f}</li>)}
                </ul>
              )}
              <p className="ag-aviso">
                Zeno AI analiza tus datos y los precios del día con inteligencia artificial ({estado.inf.modelo}). Sus sugerencias
                son orientativas: no son asesoramiento financiero, no garantizan resultados y no se ejecutan solas. Cada operación
                la decidís y la confirmás vos.
              </p>
            </div>
          )}
        </div>
        <ChatAgente habilitado={configurado && estado.tipo !== "sin-config"} />
      </div>
    </div>
  );
}

function SinConfigurar() {
  return (
    <div className="card ag-config">
      <h2>Conectá Zeno AI</h2>
      <p className="muted">El agente usa la API de Groq. Para activarlo:</p>
      <ol>
        <li>Creá una clave gratis en <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer">console.groq.com/keys</a>.</li>
        <li>Pegala en <code>backend/.env</code> del laboratorio, en la línea <code>GROQ_API_KEY=</code>.</li>
        <li>Reiniciá la API con <b>Detener Zeno Lab</b> y <b>Iniciar Zeno Lab</b>.</li>
      </ol>
    </div>
  );
}
