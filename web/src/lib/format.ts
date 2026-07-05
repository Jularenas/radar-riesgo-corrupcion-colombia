/**
 * Number/currency/date formatting helpers, Colombian Spanish (es-CO) locale.
 *
 * COP amounts use the Colombian long-scale reading (mil millones = 1e9,
 * millones = 1e6, billones = 1e12 -- NOT the English short scale, where
 * "billion" = 1e9) so KPI cards read naturally, e.g. "$103,1 billones" for
 * ~103.13 trillion COP.
 */

function nf(opts?: Intl.NumberFormatOptions): Intl.NumberFormat {
  return new Intl.NumberFormat("es-CO", opts);
}

export function formatNumber(value: number, opts?: Intl.NumberFormatOptions): string {
  return nf(opts).format(value);
}

export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return nf({ maximumFractionDigits: 0 }).format(value);
}

/** Compact, human-scale COP amount for KPI cards and prose, e.g. "$103,1 billones". */
export function formatCOP(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const oneDecimal = { maximumFractionDigits: 1, minimumFractionDigits: 1 };
  if (abs >= 1e12) return `${sign}$${formatNumber(abs / 1e12, oneDecimal)} billones`;
  if (abs >= 1e9) return `${sign}$${formatNumber(abs / 1e9, oneDecimal)} mil millones`;
  if (abs >= 1e6) return `${sign}$${formatNumber(abs / 1e6, oneDecimal)} millones`;
  return `${sign}$${formatNumber(abs, { maximumFractionDigits: 0 })}`;
}

/** Full-precision COP amount, e.g. for the contract detail page. */
export function formatCOPFull(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `$${formatNumber(value, { maximumFractionDigits: 0 })} COP`;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${formatNumber(value, { maximumFractionDigits: digits, minimumFractionDigits: digits })}%`;
}

/** Ratio in [0,1] rendered as a percentage, e.g. evidence fields like `share_directa`. */
export function formatRatioAsPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return formatPercent(value * 100, digits);
}

export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return "—";
  return formatNumber(score, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("es-CO", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("es-CO", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(d);
}

/** Humanize a snake_case identifier as a fallback label, e.g. "num_oferentes" -> "Num oferentes". */
export function humanizeKey(key: string): string {
  const spaced = key.replace(/_/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
