"use client";

import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { money, num } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { useMe } from "@/context/SessionContext";
import { ErrorCard, GananciasCard, Head, Loading } from "@/components/ui";

export default function RankingsPage() {
  const { cuentaId, reloadKey } = useMe();
  const router = useRouter();
  const { data, error, reload } = useAsync(
    () => Promise.all([api.masOperados(), api.masFavoritos(), api.ganancias(cuentaId)]),
    [cuentaId, reloadKey],
  );
  const head = <Head title="Rankings del mercado" sub="Lo que se está operando en IOL Aula" />;
  if (error) return <>{head}<ErrorCard message={error} onRetry={reload} /></>;
  if (!data) return <>{head}<Loading /></>;

  const [ops, fav, gan] = data;
  const maxV = ops.length ? ops[0].volumen_ars : 1, maxF = fav.length ? fav[0].favoritos : 1;
  const row = (id: number) => ({
    tabIndex: 0, onClick: () => router.push(`/mercado/${id}`),
    onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter") router.push(`/mercado/${id}`); },
  });

  return (
    <>
      {head}
      <div className="grid g2e">
        <div className="card">
          <div className="ctitle"><h2>Más operados · últimos 7 días</h2></div>
          {ops.length ? ops.map((t, i) => (
            <div key={t.activo_id} className="list-row row-click" {...row(t.activo_id)}>
              <div style={{ flex: 1 }}>
                <b>{i + 1}.</b> <span className="sym">{t.ticker}</span> <span className="sname">{t.operaciones} op. · {num(t.cantidad_operada)} u.</span>
                <div className="bar" style={{ width: `${Math.max(4, (t.volumen_ars / maxV) * 100)}%`, marginTop: 6 }} />
              </div>
              <b style={{ minWidth: 130, textAlign: "right" }}>{money(t.volumen, t.moneda)}</b>
            </div>
          )) : <div className="empty">Sin operaciones en los últimos 7 días.</div>}
          <p className="muted" style={{ fontSize: 12 }}>Volumen = cantidad × precio. Para comparar, los USD se pasan a pesos a dólar MEP.</p>
        </div>
        <div className="card">
          <div className="ctitle"><h2>Más elegidos como favoritos</h2></div>
          {fav.length ? fav.map((t, i) => (
            <div key={t.activo_id} className="list-row row-click" {...row(t.activo_id)}>
              <div style={{ flex: 1 }}>
                <b>{i + 1}.</b> <span className="sym">{t.ticker}</span> <span className="sname">{t.nombre}</span>
                <div className="bar" style={{ background: "#f5b301", width: `${(t.favoritos / maxF) * 100}%`, marginTop: 6 }} />
              </div>
              <b>★ {t.favoritos}</b>
            </div>
          )) : <div className="empty">Nadie marcó favoritos todavía.</div>}
        </div>
      </div>
      <GananciasCard gan={gan} />
    </>
  );
}
