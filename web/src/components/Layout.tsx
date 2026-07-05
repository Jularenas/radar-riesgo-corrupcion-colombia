import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { cn } from "@/lib/cn";

const NAV_ITEMS = [
  { to: "/", label: "Panorama", end: true },
  { to: "/casos", label: "Casos prioritarios", end: false },
  { to: "/metodologia", label: "Metodología", end: false },
];

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100">
      <header className="sticky top-0 z-20 border-b border-gray-200 bg-white/90 backdrop-blur dark:border-gray-800 dark:bg-gray-950/90">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <ShieldAlert className="text-red-600 dark:text-red-500" size={22} aria-hidden />
            <span className="text-base sm:text-lg">
              Radar de Riesgo de Corrupción <span className="text-gray-400 dark:text-gray-500">· Colombia</span>
            </span>
          </NavLink>
          <nav className="flex flex-wrap gap-1 text-sm">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-3 py-1.5 font-medium transition-colors",
                    isActive
                      ? "bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900"
                      : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>

      <footer className="mx-auto max-w-7xl px-4 py-8 text-xs text-gray-400 sm:px-6 dark:text-gray-600">
        <p>
          Los puntajes de riesgo son indicadores para priorizar auditoría, no acusaciones de responsabilidad. Cada
          caso enlaza a su registro público oficial en SECOP.{" "}
          <NavLink to="/metodologia" className="underline underline-offset-2 hover:text-gray-600 dark:hover:text-gray-400">
            Ver metodología completa
          </NavLink>
          .
        </p>
      </footer>
    </div>
  );
}
