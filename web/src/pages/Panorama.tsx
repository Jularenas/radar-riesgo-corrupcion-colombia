import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, Building2, FileText, Landmark, MapPin, Wallet } from "lucide-react";
import { getMeta, getResumenNacional } from "@/lib/data";
import { useAsyncData } from "@/lib/hooks";
import { formatCOP, formatInt, formatPercent } from "@/lib/format";
import { TIER_HEX, TIER_LABELS } from "@/lib/tier";
import { KpiCard } from "@/components/KpiCard";
import { LoadingState, ErrorState } from "@/components/StateViews";
import { ColombiaMap } from "@/components/ColombiaMap";

const MODALIDAD_LABELS: Record<string, string> = {
  LICITACION_PUBLICA: "Licitación pública",
  SELECCION_ABREVIADA: "Selección abreviada",
  CONCURSO_MERITOS: "Concurso de méritos",
  CONTRATACION_DIRECTA: "Contratación directa",
  MINIMA_CUANTIA: "Mínima cuantía",
  REGIMEN_ESPECIAL: "Régimen especial",
  OTRO: "Otro",
};

const MODALIDAD_COLORS: Record<string, string> = {
  LICITACION_PUBLICA: "#0ea5e9",
  SELECCION_ABREVIADA: "#6366f1",
  CONCURSO_MERITOS: "#8b5cf6",
  CONTRATACION_DIRECTA: TIER_HEX.alto,
  MINIMA_CUANTIA: "#14b8a6",
  REGIMEN_ESPECIAL: "#64748b",
  OTRO: "#9ca3af",
};

export function PanoramaPage() {
  const navigate = useNavigate();
  const resumen = useAsyncData(getResumenNacional, []);
  const meta = useAsyncData(getMeta, []);

  const serieByYear = useMemo(() => {
    if (!resumen.data) return [];
    const years = new Map<number, Record<string, number | string>>();
    for (const row of resumen.data.serie_anio_modalidad) {
      const entry = years.get(row.anio) ?? { anio: row.anio };
      entry[row.modalidad] = row.n_contratos;
      years.set(row.anio, entry);
    }
    return [...years.values()].sort((a, b) => (a.anio as number) - (b.anio as number));
  }, [resumen.data]);

  const modalidadesPresentes = useMemo(() => {
    if (!resumen.data) return [];
    return [...new Set(resumen.data.serie_anio_modalidad.map((r) => r.modalidad))];
  }, [resumen.data]);

  const casosCriticosByYear = useMemo(() => {
    if (!resumen.data) return [];
    return resumen.data.serie_anio_tier
      .filter((r) => r.tier === "critico")
      .map((r) => ({ anio: r.anio, critico: r.n_contratos }))
      .sort((a, b) => a.anio - b.anio);
  }, [resumen.data]);

  if (resumen.loading || meta.loading) return <LoadingState label="Cargando panorama nacional…" />;
  if (resumen.error) return <ErrorState message={resumen.error} />;
  if (!resumen.data) return <ErrorState message="No hay datos disponibles." />;

  const { kpis, departamentos } = resumen.data;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Panorama nacional</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Contratación pública colombiana analizada por el radar de riesgo de corrupción.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Contratos analizados"
          value={formatInt(kpis.contratos_analizados)}
          icon={FileText}
          hint={`${formatPercent(kpis.pct_geolocalizado)} geolocalizados`}
        />
        <KpiCard label="Valor total" value={formatCOP(kpis.valor_total_cop)} icon={Wallet} accent="neutral" />
        <KpiCard
          label="Casos críticos"
          value={formatInt(kpis.casos_criticos)}
          icon={AlertTriangle}
          accent="red"
          hint="Score de riesgo ≥ 60"
        />
        <KpiCard
          label="% contratación directa"
          value={formatPercent(kpis.pct_contratacion_directa)}
          icon={Landmark}
          accent={kpis.pct_contratacion_directa > 60 ? "orange" : "neutral"}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <KpiCard label="Entidades contratantes" value={formatInt(kpis.n_entidades)} icon={Building2} />
        <KpiCard label="Proveedores distintos" value={formatInt(kpis.n_proveedores)} icon={MapPin} />
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900 sm:p-6">
        <h2 className="mb-4 text-lg font-semibold">Mapa de riesgo por departamento</h2>
        {meta.data && (
          <ColombiaMap
            departamentos={departamentos}
            niveles={meta.data.niveles_riesgo}
            onSelect={(cod) => navigate(`/departamentos/${cod}`)}
          />
        )}
      </section>

      {serieByYear.length > 0 && (
        <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900 sm:p-6">
          <h2 className="mb-4 text-lg font-semibold">Contratos por año y modalidad</h2>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={serieByYear}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-800" />
                <XAxis dataKey="anio" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => formatInt(v)} />
                <Tooltip
                  formatter={(value, name) => [formatInt(Number(value)), MODALIDAD_LABELS[String(name)] ?? String(name)]}
                  labelFormatter={(label) => `Año ${label}`}
                />
                <Legend formatter={(name) => MODALIDAD_LABELS[String(name)] ?? String(name)} />
                {modalidadesPresentes.map((mod) => (
                  <Bar key={mod} dataKey={mod} stackId="modalidad" fill={MODALIDAD_COLORS[mod] ?? "#9ca3af"} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {casosCriticosByYear.length > 0 && (
        <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900 sm:p-6">
          <h2 className="text-lg font-semibold">Casos críticos por año</h2>
          <p className="mb-4 mt-1 text-sm text-gray-500 dark:text-gray-400">
            Contratos con score de riesgo ≥ 60 firmados cada año. Se grafican solo estos -- apilarlos junto a
            bajo/medio/alto los deja invisibles: son{" "}
            {formatPercent((100 * (resumen.data?.kpis.casos_criticos ?? 0)) / (resumen.data?.kpis.contratos_analizados || 1), 3)} del
            total de contratos.
          </p>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={casosCriticosByYear}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-800" />
                <XAxis dataKey="anio" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => formatInt(v)} allowDecimals={false} />
                <Tooltip formatter={(value) => [formatInt(Number(value)), TIER_LABELS.critico]} labelFormatter={(label) => `Año ${label}`} />
                <Bar dataKey="critico" fill={TIER_HEX.critico} name={TIER_LABELS.critico} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
    </div>
  );
}
