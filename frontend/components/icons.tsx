// Íconos del menú (SVG del diseño original).
const P = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8 } as const;

export const IcoInicio = () => <svg {...P} strokeLinejoin="round"><path d="M3.5 10.2 12 3.5l8.5 6.7V20a.8.8 0 0 1-.8.8H15v-6H9v6H4.3a.8.8 0 0 1-.8-.8z" /></svg>;
export const IcoMercado = ({ w = 1.8 }: { w?: number }) => <svg {...P} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round"><path d="M3 17l5.5-5.5 4 4L21 7" /><path d="M15 7h6v6" /></svg>;
export const IcoCartera = () => <svg {...P} strokeLinejoin="round"><path d="M12 3a9 9 0 1 0 9 9h-9z" /><path d="M15 2.6A9 9 0 0 1 21.4 9H15z" /></svg>;
export const IcoOperaciones = () => <svg {...P} strokeLinecap="round"><path d="M8 6h12M8 12h12M8 18h12" /><circle cx="4" cy="6" r="1" /><circle cx="4" cy="12" r="1" /><circle cx="4" cy="18" r="1" /></svg>;
export const IcoMovimientos = () => <svg {...P} strokeLinecap="round" strokeLinejoin="round"><path d="M4 8h14l-3-3M20 16H6l3 3" /></svg>;
export const IcoMep = () => <svg {...P} strokeLinecap="round"><path d="M12 3v18" /><path d="M16.5 7.5c0-1.7-2-3-4.5-3s-4.5 1.3-4.5 3 2 2.6 4.5 3 4.5 1.3 4.5 3-2 3-4.5 3-4.5-1.3-4.5-3" /></svg>;
export const IcoRankings = () => <svg {...P} strokeLinecap="round"><path d="M5 20V12M12 20V5M19 20v-9" /></svg>;
export const IcoAdmin = () => <svg {...P} strokeLinecap="round" strokeLinejoin="round"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></svg>;
export const IcoToggle = () => <svg {...P} strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="16" rx="3" /><path d="M9 4v16M13.5 10l2 2-2 2" /></svg>;

// Menú inferior (celular): ícono vacío y relleno cuando está activo
export const TabInicio = () => (<>
  <svg className="ico-off" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" /></svg>
  <svg className="ico-on" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.4 2.3 10.5V20a2 2 0 0 0 2 2H9v-6.5h6V22h4.7a2 2 0 0 0 2-2v-9.5z" /></svg>
</>);
export const TabMercado = () => (<>
  <svg className="ico-off" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 17l5.5-5.5 4 4L21 7" /><path d="M15 7h6v6" /></svg>
  <svg className="ico-on" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M3 17l5.5-5.5 4 4L21 7" /><path d="M15 7h6v6" /></svg>
</>);
export const TabMas = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="5.5" /><path d="M12 8v8M8 12h8" /></svg>;
export const TabCartera = () => (<>
  <svg className="ico-off" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M12 3a9 9 0 1 0 9 9h-9z" /><path d="M15 2.6A9 9 0 0 1 21.4 9H15z" /></svg>
  <svg className="ico-on" viewBox="0 0 24 24" fill="currentColor"><path d="M11 2.1A10 10 0 1 0 21.9 13H11z" /><path d="M13.5 1.6V10.5h8.9A10 10 0 0 0 13.5 1.6z" /></svg>
</>);
