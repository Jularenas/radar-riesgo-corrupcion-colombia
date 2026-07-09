import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { getMeta } from "@/lib/data";
import { useAsyncData } from "@/lib/hooks";
import { formatInt, formatPercent, formatScore } from "@/lib/format";
import { TIER_HEX, TIER_LABELS, TIER_ORDER } from "@/lib/tier";
import { LoadingState, ErrorState } from "@/components/StateViews";

const FUENTES = [
  { grupo: "Contratación (SECOP)", items: [
    { nombre: "SECOP II — Contratos Electrónicos", detalle: "Contratos firmados 2015→hoy, cifras, fechas, adiciones. Fuente principal de este mart." },
    { nombre: "SECOP II — Procesos de Contratación", detalle: "Etapa de licitación: oferentes invitados/únicos, precio base, fechas de publicación y cierre." },
    { nombre: "SECOP I — Procesos y Contratos", detalle: "Contratación histórica (pre-2015), usada para validar casos emblemáticos ya conocidos." },
  ]},
  { grupo: "Sanciones (etiquetas de validación, L1–L4)", items: [
    { nombre: "Responsabilidad Fiscal — Contraloría General", detalle: "Personas naturales/jurídicas declaradas fiscalmente responsables." },
    { nombre: "Multas y Sanciones SECOP I/II", detalle: "Multas contractuales impuestas a proveedores en la plataforma." },
    { nombre: "Antecedentes SIRI — Procuraduría", detalle: "Sanciones disciplinarias contra servidores y particulares con funciones públicas." },
  ]},
  { grupo: "Registro empresarial y validación externa", items: [
    { nombre: "RUES / Cámaras de Comercio", detalle: "Fecha de matrícula mercantil de proveedores — insumo de la bandera 'Empresa exprés'." },
    { nombre: "DIVIPOLA (DANE)", detalle: "Códigos oficiales de departamento y municipio." },
    { nombre: "Monitor Ciudadano de la Corrupción (Transparencia por Colombia)", detalle: "Hechos de corrupción reportados en prensa 1995–2022, usado como validación independiente." },
  ]},
];

export function MetodologiaPage() {
  const { data: meta, loading, error } = useAsyncData(getMeta, []);

  if (loading) return <LoadingState label="Cargando metodología…" />;
  if (error) return <ErrorState message={error} />;
  if (!meta) return <ErrorState message="No hay datos de metodología disponibles." />;

  const bt = meta.backtest;

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Metodología</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Cómo se calcula el score de riesgo, de dónde vienen los datos, y qué tan bien predice casos ya conocidos.
        </p>
      </div>

      <section className="rounded-lg border border-amber-300 bg-amber-50 p-5 dark:border-amber-800 dark:bg-amber-950/40">
        <div className="flex gap-3">
          <AlertTriangle className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" size={22} aria-hidden />
          <div className="text-sm text-amber-900 dark:text-amber-200">
            <p className="font-semibold">Este score es un indicador de riesgo, no una acusación.</p>
            <p className="mt-1">
              Un puntaje alto o crítico señala patrones estadísticos que ameritan revisión y auditoría — no constituye
              prueba de irregularidad ni de responsabilidad de ninguna persona o entidad. Cada contrato mostrado
              enlaza a su registro público oficial en SECOP para que cualquiera pueda verificar los datos de origen.
            </p>
          </div>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Fórmula del score</h2>
        <div className="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
          <p className="font-mono text-sm text-gray-800 dark:text-gray-200">{meta.formula_score}</p>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Las banderas sin datos disponibles para un contrato se excluyen del denominador (no cuentan como
            "no disparada"). Los puntajes de entidad y municipio usan además contracción empírico-bayesiana hacia el
            promedio departamental (k={meta.shrinkage.k}); con menos de {meta.shrinkage.min_contratos_rank} contratos
            se muestra la etiqueta "datos insuficientes" en vez de un ranking.
          </p>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Niveles de riesgo</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {meta.niveles_riesgo.map((n) => (
            <div key={n.id} className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: TIER_HEX[n.id] }} />
                <span className="font-semibold">{n.nombre}</span>
              </div>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                {n.max_score === null ? `≥ ${n.min_score}` : `${n.min_score} – ${n.max_score}`}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Catálogo de banderas de riesgo</h2>
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr className="text-left text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                <th className="px-4 py-2.5">ID</th>
                <th className="px-4 py-2.5">Bandera</th>
                <th className="px-4 py-2.5">Nivel</th>
                <th className="px-4 py-2.5">Peso</th>
                <th className="px-4 py-2.5">Descripción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white dark:divide-gray-800/60 dark:bg-gray-950">
              {meta.banderas.map((b) => (
                <tr key={b.id}>
                  <td className="px-4 py-3 font-mono text-xs">{b.id}</td>
                  <td className="px-4 py-3 font-medium">{b.nombre}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                    {b.nivel === "contract" ? "Contrato" : "Entidad"}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{b.peso}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{b.descripcion}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Validación contra casos ya conocidos</h2>
        <div className="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center gap-2">
            {bt.cumple_objetivos ? (
              <CheckCircle2 className="text-green-600 dark:text-green-400" size={20} aria-hidden />
            ) : (
              <XCircle className="text-red-600 dark:text-red-400" size={20} aria-hidden />
            )}
            <p className="font-semibold">{bt.cumple_objetivos ? "Cumple los objetivos de validación" : "No cumple todos los objetivos de validación"}</p>
          </div>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{bt.resumen}</p>

          <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <dt className="text-xs text-gray-400">AUC-ROC</dt>
              <dd className="text-lg font-bold tabular-nums">
                {bt.auc_roc !== null ? bt.auc_roc.toFixed(3) : "—"}{" "}
                <span className="text-xs font-normal text-gray-400">/ meta {bt.objetivo_auc_roc}</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-400">Lift top-decil</dt>
              <dd className="text-lg font-bold tabular-nums">
                {bt.lift_top_decil !== null ? bt.lift_top_decil.toFixed(2) : "—"}{" "}
                <span className="text-xs font-normal text-gray-400">/ meta {bt.objetivo_lift_top_decil}</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-400">Contratos evaluados</dt>
              <dd className="text-lg font-bold tabular-nums">{formatInt(bt.n_contratos_evaluados)}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-400">Positivos (L1–L4)</dt>
              <dd className="text-lg font-bold tabular-nums">{formatInt(bt.n_positivos_l1_l4)}</dd>
            </div>
          </dl>
        </div>

        {bt.casos_emblematicos.length > 0 && (
          <div className="mt-4 overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-800">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr className="text-left text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  <th className="px-4 py-2.5">Caso emblemático</th>
                  <th className="px-4 py-2.5">Período</th>
                  <th className="px-4 py-2.5 text-right">Contratos coincidentes</th>
                  <th className="px-4 py-2.5">Mejor score</th>
                  <th className="px-4 py-2.5">Percentil (su año)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white dark:divide-gray-800/60 dark:bg-gray-950">
                {bt.casos_emblematicos.map((c) => (
                  <tr key={c.slug}>
                    <td className="px-4 py-2.5 font-medium">
                      {c.nombre}
                      {!c.confirmado_manualmente && c.n_matched > 0 && (
                        <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                          coincidencia sin confirmar
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400">
                      {c.periodo[0]}–{c.periodo[1]}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{formatInt(c.n_matched)}</td>
                    <td className="px-4 py-2.5 tabular-nums">{c.mejor_score !== null ? formatScore(c.mejor_score) : "—"}</td>
                    <td className="px-4 py-2.5 tabular-nums">
                      {c.percentil_anio !== null ? formatPercent(c.percentil_anio * 100, 0) : "—"}
                      {c.cuartil_superior && <span className="ml-1 text-green-600 dark:text-green-400">✓ cuartil superior</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
          Monitor Ciudadano: {formatInt(bt.monitor_ciudadano.n_matched)} de {formatInt(bt.monitor_ciudadano.n_total)}{" "}
          hechos coincidentes ({bt.monitor_ciudadano.match_rate_pct !== null ? formatPercent(bt.monitor_ciudadano.match_rate_pct) : "—"}).{" "}
          {bt.monitor_ciudadano.nota}
        </p>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Fuentes de datos</h2>
        <div className="space-y-6">
          {FUENTES.map((grupo) => (
            <div key={grupo.grupo}>
              <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">{grupo.grupo}</h3>
              <ul className="space-y-2">
                {grupo.items.map((it) => (
                  <li key={it.nombre} className="rounded-lg border border-gray-200 bg-white p-3 text-sm dark:border-gray-800 dark:bg-gray-900">
                    <p className="font-medium">{it.nombre}</p>
                    <p className="text-gray-500 dark:text-gray-400">{it.detalle}</p>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-gray-50 p-5 text-xs text-gray-500 dark:border-gray-800 dark:bg-gray-900/60 dark:text-gray-500">
        <p>
          Todas las fuentes citadas son datos públicos, abiertos y auditables (datos.gov.co, Contraloría, Procuraduría,
          Confecámaras/RUES, Transparencia por Colombia). Los indicadores de riesgo aquí presentados nunca sustituyen
          un proceso de auditoría o investigación formal.
        </p>
        <p className="mt-2">Leyenda de colores: {TIER_ORDER.map((t) => TIER_LABELS[t]).join(" · ")}.</p>
      </section>
    </div>
  );
}
