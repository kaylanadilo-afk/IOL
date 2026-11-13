import type { Metadata, Viewport } from "next";
import { Instrument_Sans } from "next/font/google";
import { SessionProvider } from "@/context/SessionContext";
import { UIProvider } from "@/context/UIContext";
import "./globals.css";

const instrument = Instrument_Sans({
  variable: "--font-instrument",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "IOL Aula | Broker educativo",
  description: "Simulador de broker: acciones, CEDEARs, bonos y dólar MEP con precios reales.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "IOL Aula", statusBarStyle: "black-translucent" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#F4F6F3",
};

// Aplica el tema guardado antes de pintar, para que no parpadee el modo claro
const temaInicial = `try{if(localStorage.getItem('iolAula_tema')==='dark')document.documentElement.setAttribute('data-theme','dark')}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es" data-theme="light" className={instrument.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: temaInicial }} />
      </head>
      <body>
        <UIProvider>
          <SessionProvider>{children}</SessionProvider>
        </UIProvider>
      </body>
    </html>
  );
}
