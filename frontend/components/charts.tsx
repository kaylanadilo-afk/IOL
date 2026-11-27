"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { num, pct, round2 } from "@/lib/format";

/* ===================== MINI GRÁFICO (30 días) ===================== */
export function Sparkline({ valores, actual }: { valores?: number[]; actual?: number }) {
  const v = (valores ?? []).slice();
  if (actual != null && v.length) v.push(actual);
  if (v.length < 2) return <svg className="spark" aria-hidden="true" />;
  let mn = Math.min(...v), mx = Math.max(...v);
  const W = 84, H = 28, p = 2;
  if (mx === mn) { mx += 1; mn -= 1; }
  const d = v.map((y, i) => `${i ? "L" : "M"}${(p + (i * (W - 2 * p)) / (v.length - 1)).toFixed(1)} ${(p + (H - 2 * p) * (1 - (y - mn) / (mx - mn))).toFixed(1)}`).join(" ");
  const col = v[v.length - 1] >= v[0] ? "var(--up)" : "var(--down)";
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Tendencia de 30 días: ${pct((v[v.length - 1] / v[0] - 1) * 100)}`}>
      <path d={d} fill="none" stroke={col} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/* ===================== ANILLO DE COMPOSICIÓN ===================== */
export interface DonutPart { label: string; value: number; pct?: number; color: string }

export function DonutSvg({ parts, centro }: { parts: DonutPart[]; centro?: React.ReactNode }) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  const R = 58, C = 2 * Math.PI * R;
  const gap = parts.filter((p) => p.value > 0).length > 1 ? 3 : 0;
  const visibles = parts.filter((p) => p.value > 0);
  // Cada segmento arranca donde termina el anterior
  const offsets = visibles.map((_, i) => visibles.slice(0, i).reduce((s, p) => s + (p.value / total) * C, 0));
  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 140 140" role="img" aria-label="Composición de la cartera">
        <circle r={R} cx="70" cy="70" fill="none" stroke="var(--card2)" strokeWidth="14" />
        {visibles.map((p, i) => {
          const len = (p.value / total) * C;
          return (
            <circle key={p.label} r={R} cx="70" cy="70" fill="none" stroke={p.color} strokeWidth="14" strokeLinecap="butt"
              strokeDasharray={`${Math.max(len - gap, 0.5).toFixed(2)} ${(C - len + gap).toFixed(2)}`}
              strokeDashoffset={(-offsets[i]).toFixed(2)} transform="rotate(-90 70 70)" />
          );
        })}
      </svg>
      {centro && <div className="donut-center">{centro}</div>}
    </div>
  );
}

export function Legend({ parts }: { parts: DonutPart[] }) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  return (
    <div className="legend">
      {parts.filter((p) => p.value > 0).map((p) => (
        <div key={p.label}>
          <span><span className="sw" style={{ background: p.color }} />{p.label}</span>
          <b>{(p.pct != null ? p.pct : (p.value / total) * 100).toFixed(1).replace(".", ",")}%</b>
        </div>
      ))}
    </div>
  );
}

export function Donut({ parts }: { parts: DonutPart[] }) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  if (total <= 0) return <div className="empty">Sin tenencias todavía.</div>;
  return <div className="alloc"><DonutSvg parts={parts} /><Legend parts={parts} /></div>;
}

/* ===================== GRÁFICO DE LÍNEA ===================== */
// El SVG dibuja la línea; ejes, cursor y tooltip son HTML para que el texto no se deforme.
export interface ChartPoint { x: number; y: number; label: React.ReactNode }

interface ChartOpts {
  xMin?: number;
  xMax?: number;
  xTicks?: { x: number; label: string }[];
  /** Línea de referencia punteada (cierre anterior). */
  ref?: number | null;
  aria: string;
  vacio: string;
}

export function LineChart({ pts, opt, className = "chart", id }: { pts: ChartPoint[] | null; opt: ChartOpts; className?: string; id?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  // Punto bajo el cursor y ancho del gráfico medido en ese momento
  const [hover, setHover] = useState<{ i: number; w: number } | null>(null);

  // El tooltip no puede salirse del gráfico: se acomoda después de medirlo
  useLayoutEffect(() => {
    const tip = tipRef.current, el = box.current;
    if (!tip || !el || !hover) return;
    const left = parseFloat(tip.dataset.left ?? "0");
    tip.style.left = `${Math.max(0, Math.min(left - tip.offsetWidth / 2, el.getBoundingClientRect().width - tip.offsetWidth))}px`;
  });

  if (pts == null) return <div className={className} id={id}><div className="msg">Cargando gráfico…</div></div>;
  if (!pts.length) return <div className={className} id={id}><div className="msg">{opt.vacio}</div></div>;

  const ys = pts.map((p) => p.y);
  if (opt.ref != null) ys.push(opt.ref);
  let yMin = Math.min(...ys), yMax = Math.max(...ys);
  const pad = (yMax - yMin) * 0.08 || Math.abs(yMax) * 0.01 || 1;
  yMin -= pad; yMax += pad;
  let xMin = opt.xMin ?? pts[0].x, xMax = opt.xMax ?? pts[pts.length - 1].x;
  if (xMax === xMin) { xMin -= 1; xMax += 1; }
  const fx = (x: number) => (x - xMin) / (xMax - xMin);
  const fy = (y: number) => 1 - (y - yMin) / (yMax - yMin);
  const base = opt.ref != null ? opt.ref : pts[0].y, last = pts[pts.length - 1].y;
  const sube = last >= base;
  const color = sube ? "var(--up)" : "var(--down)";
  const W = 1000, H = 1000;
  const d = pts.map((p, i) => `${i ? "L" : "M"}${(fx(p.x) * W).toFixed(1)} ${(fy(p.y) * H).toFixed(1)}`).join("");
  const area = `${d} L${(fx(pts[pts.length - 1].x) * W).toFixed(1)} ${H} L${(fx(pts[0].x) * W).toFixed(1)} ${H} Z`;
  const gid = `cg${(id ?? "c")}${pts.length}`;

  const onMove = (clientX: number) => {
    const el = box.current;
    if (!el) return;
    const rect = el.getBoundingClientRect(), w = rect.width - 64;
    const f = Math.max(0, Math.min(1, (clientX - rect.left) / w));
    let best = 0;
    pts.forEach((p, i) => { if (Math.abs(fx(p.x) - f) < Math.abs(fx(pts[best].x) - f)) best = i; });
    setHover({ i: best, w });
  };

  const hp = hover != null ? pts[hover.i] : null;
  const left = hp && hover ? fx(hp.x) * hover.w : 0;

  return (
    <div className={className} id={id} ref={box} onPointerMove={(e) => onMove(e.clientX)} onPointerLeave={() => setHover(null)}>
      <svg className="plot" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={opt.aria}>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={sube ? "#0a9f66" : "#d64545"} stopOpacity=".22" />
            <stop offset="1" stopColor={sube ? "#0a9f66" : "#d64545"} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3, 4].map((i) => (
          <line key={i} x1="0" x2={W} y1={(i / 4) * H} y2={(i / 4) * H} stroke="var(--line)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        ))}
        {opt.ref != null && (
          <line x1="0" x2={W} y1={fy(opt.ref) * H} y2={fy(opt.ref) * H} stroke="var(--muted)" strokeDasharray="4 4" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        )}
        <path d={area} fill={`url(#${gid})`} />
        <path d={d} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        {pts.length === 1 && <circle cx={fx(pts[0].x) * W} cy={fy(pts[0].y) * H} r="6" fill={color} />}
      </svg>
      {[0, 1, 2, 3, 4].map((i) => {
        const f = i / 4;
        return <div key={i} className="ylab" style={{ top: `calc(8px + (100% - 32px) * ${f})` }}>{num(round2(yMax - f * (yMax - yMin)))}</div>;
      })}
      {(opt.xTicks ?? []).map((t, i, all) => (
        <div key={t.x} className={`xlab${i === 0 ? " first" : i === all.length - 1 ? " last" : ""}`} style={{ left: `calc((100% - 64px) * ${fx(t.x)})` }}>{t.label}</div>
      ))}
      {hp && (
        <>
          <div className="cross" style={{ left }} />
          <div className="pt" style={{ left, top: `calc(8px + (100% - 32px) * ${fy(hp.y)})`, background: color }} />
          <div className="tip" ref={tipRef} data-left={left}>{hp.label}</div>
        </>
      )}
    </div>
  );
}


/* ===================== TORTA (distribución por categoría) ===================== */
export interface PieSlice { key: string; label: string; value: number; color: string }

/** Torta con porciones seleccionables (mouse, toque o teclado). */
export function PieChart({ parts, selected, onSelect, aria }: {
  parts: PieSlice[]; selected: string | null; onSelect: (key: string | null) => void; aria: string;
}) {
  const visibles = parts.filter((p) => p.value > 0);
  const total = visibles.reduce((s, p) => s + p.value, 0);
  if (total <= 0) return null;
  const R = 70, C = 80;
  const punto = (f: number) => [C + R * Math.sin(2 * Math.PI * f), C - R * Math.cos(2 * Math.PI * f)];
  const inicios = visibles.map((_, i) => visibles.slice(0, i).reduce((s, p) => s + p.value / total, 0));
  return (
    <svg className="pie" viewBox="0 0 160 160" role="group" aria-label={aria}>
      {visibles.map((p, i) => {
        const f0 = inicios[i], f1 = f0 + p.value / total;
        const on = selected === p.key;
        const medio = (f0 + f1) / 2;
        // La porción elegida se separa un poco del centro
        const [dx, dy] = on ? [Math.sin(2 * Math.PI * medio) * 5, -Math.cos(2 * Math.PI * medio) * 5] : [0, 0];
        const comun = {
          fill: p.color, stroke: "var(--card)", strokeWidth: 1.5, tabIndex: 0, role: "button",
          "aria-label": `${p.label}: ${((p.value / total) * 100).toFixed(1).replace(".", ",")}%`, "aria-pressed": on,
          className: `pie-slice${selected && !on ? " dim" : ""}`, transform: `translate(${dx.toFixed(2)} ${dy.toFixed(2)})`,
          onClick: () => onSelect(on ? null : p.key),
          onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(on ? null : p.key); } },
        };
        if (f1 - f0 >= 0.9999) return <circle key={p.key} {...comun} cx={C} cy={C} r={R} />;
        const [x0, y0] = punto(f0), [x1, y1] = punto(f1);
        const d = `M${C} ${C} L${x0.toFixed(2)} ${y0.toFixed(2)} A${R} ${R} 0 ${f1 - f0 > 0.5 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)} Z`;
        return <path key={p.key} {...comun} d={d} />;
      })}
    </svg>
  );
}
