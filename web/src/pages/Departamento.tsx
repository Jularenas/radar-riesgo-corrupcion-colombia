import { useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { getDepartamento } from "@/lib/data";
import { useAsyncData } from "@/lib/hooks";
import { formatCOP, formatInt, formatScore } from "@/lib/format";
import { TierBadge } from "@/components/TierBadge";
import { LoadingState, ErrorState } from "@/components/StateViews";
import { KpiCard } from "@/components/KpiCard";

export function DepartamentoPage() {
  const { cod = "" } = useParams<{ cod: string }>();
  const navigate = useNavigate();
  const { data, loading, error } = useAsyncData(() => getDepartamento(cod), [cod]);

  const serie = useMemo(
    () => (data?.serie_anio ?? []).slice().sort((a, b) => a.anio - b.anio),
    [data],
  );

  if (loading) return <LoadingState label="Cargando departamento…" />;
  if (error) return <ErrorState message={error} />;
  if (!data) return <ErrorState message="Departamento no encontrado." />;

  return (
    <div className="space-y-8">
      <div>
        <button
          onClick={() => navigate(-1)}
          className="mb-3 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
        >
          <ArrowLeft size={15} aria-hidden /> Volver
        </button>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{data.dpto ?? cod}</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Departamento · código DIVIPOLA {data.cod_dpto}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard label="Contratos" value={formatInt(data.n_contratos)} />
        <KpiCard label="Valor total" value={formatCOP(data.valor_total)} />
        <KpiCard label="Score promedio" value={formatScore(data.score_promedio)} />
        <KpiCard label="Casos críticos" value={formatInt(data.n_criticos)} accent="red" />
      </div>

      {serie.length > 1 && (
        <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900 sm:p-6">
          <h2 className="mb-4 text-lg font-semibold">Score promedio por año</h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={serie}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-800" />
                <XAxis dataKey="anio" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} />
                <Tooltip formatter={(v) => formatScore(Number(v))} labelFormatter={(l) => `Año ${l}`} />
                <Line type="monotone" dataKey="score_promedio" stroke="#dc2626" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      <section className="rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <h2 className="border-b border-gray-200 p-4 text-lg font-semibold dark:border-gray-800 sm:p-6 sm:pb-4">
          Municipios
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500 dark:border-gray-800 dark:text-gray-400">
                <th className="px-4 py-2 sm:px-6">Municipio</th>
                <th className="px-4 py-2 text-right sm:px-6">Contratos</th>
                <th className="px-4 py-2 text-right sm:px-6">Valor total</th>
                <th className="px-4 py-2 sm:px-6">Riesgo</th>
              </tr>
            </thead>
            <tbody>
              {data.municipios.map((m) => (
                <tr key={m.cod_mpio} className="border-b border-gray-100 last:border-0 dark:border-gray-800/60">
                  <td className="px-4 py-2.5 font-medium sm:px-6">{m.municipio ?? m.cod_mpio}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums sm:px-6">{formatInt(m.n_contratos)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums sm:px-6">{formatCOP(m.valor_total)}</td>
                  <td className="px-4 py-2.5 sm:px-6">
                    <TierBadge tier={m.tier} datosInsuficientes={m.datos_insuficientes} size="sm" />
                  </td>
                </tr>
              ))}
              {data.municipios.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-400 sm:px-6">
                    Sin municipios con contratos en la muestra actual.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <h2 className="border-b border-gray-200 p-4 text-lg font-semibold dark:border-gray-800 sm:p-6 sm:pb-4">
          Entidades con mayor riesgo
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500 dark:border-gray-800 dark:text-gray-400">
                <th className="px-4 py-2 sm:px-6">Entidad</th>
                <th className="px-4 py-2 text-right sm:px-6">Contratos</th>
                <th className="px-4 py-2 text-right sm:px-6">Valor total</th>
                <th className="px-4 py-2 sm:px-6">Riesgo</th>
              </tr>
            </thead>
            <tbody>
              {data.top_entidades.map((e) => (
                <tr key={e.nit_entidad} className="border-b border-gray-100 last:border-0 dark:border-gray-800/60">
                  <td className="px-4 py-2.5 font-medium sm:px-6">{e.nombre_entidad ?? e.nit_entidad}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums sm:px-6">{formatInt(e.n_contratos)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums sm:px-6">{formatCOP(e.valor_total)}</td>
                  <td className="px-4 py-2.5 sm:px-6">
                    <TierBadge tier={e.tier} datosInsuficientes={e.datos_insuficientes} size="sm" />
                  </td>
                </tr>
              ))}
              {data.top_entidades.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-400 sm:px-6">
                    Sin entidades con contratos en la muestra actual.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <p className="text-xs text-gray-400 dark:text-gray-600">
        <Link to="/casos" className="underline underline-offset-2 hover:text-gray-600 dark:hover:text-gray-400">
          Ver todos los casos prioritarios
        </Link>
      </p>
    </div>
  );
}
