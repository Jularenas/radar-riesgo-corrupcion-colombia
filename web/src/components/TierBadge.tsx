import { AlertOctagon, AlertTriangle, Flame, HelpCircle, ShieldCheck } from "lucide-react";
import type { Tier } from "@/types/artifacts";
import { TIER_BADGE_CLASSES, TIER_LABELS } from "@/lib/tier";
import { cn } from "@/lib/cn";

const TIER_ICONS: Record<Tier, typeof ShieldCheck> = {
  bajo: ShieldCheck,
  medio: AlertTriangle,
  alto: AlertOctagon,
  critico: Flame,
};

export interface TierBadgeProps {
  tier: Tier | null | undefined;
  /** Entities/municipalities with <10 contracts (PLAN.md): still scored, but flagged low-confidence. */
  datosInsuficientes?: boolean;
  size?: "sm" | "md";
  className?: string;
}

const SIZE_CLASSES: Record<"sm" | "md", string> = {
  sm: "text-xs px-1.5 py-0.5 gap-1",
  md: "text-sm px-2.5 py-1 gap-1.5",
};

const ICON_SIZE: Record<"sm" | "md", number> = { sm: 12, md: 14 };

/**
 * The one shared tier-badge component (PLAN.md: "Build one shared
 * TierBadge/tierColor() utility used everywhere a tier appears"). Color is
 * always paired with an icon and a text label -- never color alone -- for
 * colorblind accessibility.
 */
export function TierBadge({ tier, datosInsuficientes = false, size = "md", className }: TierBadgeProps) {
  const sizeCls = SIZE_CLASSES[size];

  if (!tier) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full border font-medium",
          "bg-gray-100 text-gray-600 border-gray-300 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700",
          sizeCls,
          className,
        )}
      >
        <HelpCircle size={ICON_SIZE[size]} aria-hidden />
        {datosInsuficientes ? "Datos insuficientes" : "Sin datos"}
      </span>
    );
  }

  const Icon = TIER_ICONS[tier];

  return (
    <span className={cn("inline-flex flex-wrap items-center gap-1", className)}>
      <span className={cn("inline-flex items-center rounded-full border font-medium", TIER_BADGE_CLASSES[tier], sizeCls)}>
        <Icon size={ICON_SIZE[size]} aria-hidden />
        {TIER_LABELS[tier]}
      </span>
      {datosInsuficientes && (
        <span
          className="inline-flex items-center gap-1 rounded-full border border-gray-300 bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
          title="Menos de 10 contratos: se muestra el score calculado, pero con baja confianza estadística."
        >
          <HelpCircle size={11} aria-hidden />
          datos insuficientes
        </span>
      )}
    </span>
  );
}
