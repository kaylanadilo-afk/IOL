import AppShell from "@/components/AppShell";

// Todas las pantallas de la app (con sesión) comparten el menú lateral, el menú inferior y las hojas.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
