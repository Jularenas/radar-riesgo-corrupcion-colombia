import type { NivelRiesgo, Tier } from "@/types/artifacts";

/**
 * Single source of truth for the risk-tier palette (PLAN.md, "Design"
 * section). Every place a tier is rendered -- KPI cards, table cells, map
 * legend, detail page -- should import from here, not redefine colors.
 *
 * Colorblind-safe: color is always paired with an icon and/or text label,
 * never used alone to convey meaning (see TierBadge.tsx).
 */
export const TIER_ORDER: Tier[] = ["bajo", "medio", "alto", "critico"];

export const TIER_LABELS: Record<Tier, string> = {
  bajo: "Bajo",
  medio: "Medio",
  alto: "Alto",
  critico: "Crítico",
};

/** Exact hex values from PLAN.md's risk palette, for SVG fills (map, charts) where Tailwind classes don't apply. */
export const TIER_HEX: Record<Tier, string> = {
  bajo: "#22c55e",
  medio: "#eab308",
  alto: "#f97316",
  critico: "#dc2626",
};

export const SIN_DATOS_HEX = "#d1d5db"; // gray-300, for "sin datos" map fills

/** Badge background/text/border classes (light + dark), literal so Tailwind's scanner picks them up. */
export const TIER_BADGE_CLASSES: Record<Tier, string> = {
  bajo: "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/40 dark:text-green-300 dark:border-green-700",
  medio: "bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/40 dark:text-yellow-300 dark:border-yellow-700",
  alto: "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900/40 dark:text-orange-300 dark:border-orange-700",
  critico: "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/40 dark:text-red-300 dark:border-red-700",
};

/** Solid-fill classes (map legend swatches, chart bars). */
export const TIER_SOLID_CLASSES: Record<Tier, string> = {
  bajo: "bg-green-500",
  medio: "bg-yellow-500",
  alto: "bg-orange-500",
  critico: "bg-red-600",
};

export function tierLabel(tier: Tier | null | undefined): string {
  if (!tier) return "Sin datos";
  return TIER_LABELS[tier];
}

export function tierHex(tier: Tier | null | undefined): string {
  if (!tier) return SIN_DATOS_HEX;
  return TIER_HEX[tier];
}

/**
 * Resolve a numeric score to its tier using meta.json's `niveles_riesgo`
 * thresholds (min_score inclusive, max_score exclusive; null max_score means
 * unbounded above) -- so the dashboard never hardcodes 20/40/60 separately
 * from the pipeline's own definition.
 */
export function tierForScore(score: number | null | undefined, niveles: NivelRiesgo[]): Tier | null {
  if (score === null || score === undefined || Number.isNaN(score)) return null;
  for (const n of niveles) {
    if (score >= n.min_score && (n.max_score === null || score < n.max_score)) {
      return n.id;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Relative (percentile-based) color scale -- for comparing entities against
// each other (e.g. departments on the map) rather than against the fixed
// bajo/medio/alto/critico score thresholds above. A department-level average
// score regresses toward the low end of that absolute scale (most individual
// contracts aren't critical, so the mean dilutes down), which washes out real
// variation *between* departments. This reuses the exact same 4-color palette
// as TIER_HEX, just interpolated continuously by rank instead of bucketed by
// absolute value, so "redder" always means "higher relative to its peers".
// ---------------------------------------------------------------------------

const GRADIENT_STOPS: readonly string[] = [TIER_HEX.bajo, TIER_HEX.medio, TIER_HEX.alto, TIER_HEX.critico];

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex([r, g, b]: [number, number, number]): string {
  return `#${[r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;
}

function lerpColor(c1: string, c2: string, t: number): string {
  const a = hexToRgb(c1);
  const b = hexToRgb(c2);
  return rgbToHex([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]);
}

/** Maps a percentile rank (0..1) to a color continuously interpolated across GRADIENT_STOPS. */
export function colorForPercentile(p: number): string {
  const clamped = Math.max(0, Math.min(1, p));
  const segments = GRADIENT_STOPS.length - 1;
  const scaled = clamped * segments;
  const idx = Math.min(Math.floor(scaled), segments - 1);
  return lerpColor(GRADIENT_STOPS[idx], GRADIENT_STOPS[idx + 1], scaled - idx);
}
