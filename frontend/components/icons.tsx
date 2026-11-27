// Íconos de la app: todos de línea, 24×24, mismo grosor, y heredan el color del texto.
const P = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true } as const;

// ---------- Menú ----------
export const IcoInicio = () => <svg {...P}><path d="M3.5 10.2 12 3.5l8.5 6.7V20a.8.8 0 0 1-.8.8H15v-6H9v6H4.3a.8.8 0 0 1-.8-.8z" /></svg>;
export const IcoMercado = ({ w = 1.8 }: { w?: number }) => <svg {...P} strokeWidth={w}><path d="M3 17l5.5-5.5 4 4L21 7" /><path d="M15 7h6v6" /></svg>;
export const IcoCartera = () => <svg {...P}><path d="M12 3a9 9 0 1 0 9 9h-9z" /><path d="M15 2.6A9 9 0 0 1 21.4 9H15z" /></svg>;
export const IcoOperaciones = () => <svg {...P}><path d="M8 6h12M8 12h12M8 18h12" /><circle cx="4" cy="6" r="1" /><circle cx="4" cy="12" r="1" /><circle cx="4" cy="18" r="1" /></svg>;
export const IcoMovimientos = () => <svg {...P}><path d="M4 8h14l-3-3M20 16H6l3 3" /></svg>;
// Signo $: una S de dos curvas iguales y la barra vertical, centrados en el cuadro
export const IcoMep = () => <svg {...P}><path d="M12 2.5v19" /><path d="M16.5 6.5H10a3 3 0 0 0 0 6h4a3 3 0 0 1 0 6H7" /></svg>;
export const IcoBilletera = () => <svg {...P}><path d="M5 7.5V6.8A2.3 2.3 0 0 1 7.3 4.5H17v3" /><rect x="3.5" y="7.5" width="17" height="12" rx="2.5" /><path d="M20.5 11.5h-3.5a2 2 0 0 0 0 4h3.5" /></svg>;
export const IcoAlerta = () => <svg {...P}><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" /><path d="M10 20.5a2.2 2.2 0 0 0 4 0" /></svg>;
export const IcoAdmin = () => <svg {...P}><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></svg>;

// ---------- Acciones ----------
export const IcoIngresar = () => <svg {...P}><path d="M12 4v11M7.5 10.5 12 15l4.5-4.5" /><path d="M4 19h16" /></svg>;
export const IcoRetirar = () => <svg {...P}><path d="M12 15V4M7.5 8.5 12 4l4.5 4.5" /><path d="M4 19h16" /></svg>;
export const IcoLista = () => <svg {...P}><rect x="4" y="3.5" width="16" height="17" rx="2.5" /><path d="M8 8.5h8M8 12h8M8 15.5h5" /></svg>;
export const IcoComprar = () => <svg {...P}><path d="M7 17 17 7M9 7h8v8" /></svg>;
export const IcoVender = () => <svg {...P}><path d="M7 7l10 10M17 9v8H9" /></svg>;
export const IcoEditar = () => <svg {...P}><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z" /><path d="m13.5 6.5 4 4" /></svg>;
export const IcoPausa = () => <svg {...P}><path d="M9 5v14M15 5v14" /></svg>;
export const IcoPlay = () => <svg {...P}><path d="M7 4.5v15l12-7.5z" /></svg>;
export const IcoBorrar = () => <svg {...P}><path d="M4 7h16M10 11v6M14 11v6" /><path d="M6 7l1 12.5a1.5 1.5 0 0 0 1.5 1.5h7a1.5 1.5 0 0 0 1.5-1.5L18 7M9 7V4.5h6V7" /></svg>;
export const IcoPerfil = () => <svg {...P}><circle cx="12" cy="8.5" r="3.8" /><path d="M4.5 20a7.5 7.5 0 0 1 15 0" /></svg>;
export const IcoClave = () => <svg {...P}><circle cx="8" cy="14" r="4" /><path d="m11 11 8.5-8.5M16 6l2.5 2.5M14 8l2 2" /></svg>;
export const IcoLuna = () => <svg {...P}><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" /></svg>;
export const IcoSalir = () => <svg {...P}><path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4" /><path d="M10 16l-4-4 4-4M6 12h10" /></svg>;
export const IcoAjustes = () => <svg {...P}><circle cx="12" cy="12" r="3" /><path d="M12 2.5v3M12 18.5v3M4.2 6.5l2.6 1.5M17.2 16l2.6 1.5M4.2 17.5 6.8 16M17.2 8l2.6-1.5" /></svg>;
export const IcoChevron = () => <svg {...P}><path d="m9 6 6 6-6 6" /></svg>;

// ---------- Menú inferior (celular): ícono vacío y relleno cuando está activo ----------
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
