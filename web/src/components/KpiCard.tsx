import type { ComponentType } from "react";
import { cn } from "@/lib/cn";

export interface KpiCardProps {
  label: string;
  value: string;
  hint?: string;
  icon?: ComponentType<{ size?: number; className?: string }>;
  accent?: "neutral" | "green" | "yellow" | "orange" | "red";
}

const ACCENT_CLASSES: Record<NonNullable<KpiCardProps["accent"]>, string> = {
  neutral: "text-gray-900 dark:text-gray-100",
  green: "text-green-600 dark:text-green-400",
  yellow: "text-yellow-600 dark:text-yellow-400",
  orange: "text-orange-600 dark:text-orange-400",
  red: "text-red-600 dark:text-red-400",
};

export function KpiCard({ label, value, hint, icon: Icon, accent = "neutral" }: KpiCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{label}</p>
        {Icon && <Icon size={18} className="shrink-0 text-gray-400 dark:text-gray-500" />}
      </div>
      <p className={cn("mt-2 text-2xl font-bold tabular-nums tracking-tight sm:text-3xl", ACCENT_CLASSES[accent])}>
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-gray-500 dark:text-gray-500">{hint}</p>}
    </div>
  );
}
