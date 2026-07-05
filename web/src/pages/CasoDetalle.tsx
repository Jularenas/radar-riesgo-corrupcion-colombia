import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ExternalLink, FileWarning } from "lucide-react";
import { findCasoPorId } from "@/lib/data";
import { formatCOPFull, formatDate, formatInt } from "@/lib/format";
import { describeEvidence } from "@/lib/evidence";
import { TierBadge } from "@/components/TierBadge";
import { LoadingState, ErrorState } from "@/components/StateViews";
import type { CasoPrioritario } from "@/types/artifacts";

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-gray-900 dark:text-gray-100">{value ?? "—"}</dd>
    </div>
  );
}

export function CasoDetallePage() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [caso, setCaso] = useState<CasoPrioritario | null | undefined>(undefined); // undefined = loading, null = not found
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCaso(undefined);
    setError(null);
    findCasoPorId(id)
      .then((found) => {
        if (!cancelled) setCaso(found);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <ErrorState message={error} />;
  if (caso === undefined) return <LoadingState label="Buscando contrato…" />;
  if (caso === null) {
    return (
      <ErrorState message={`No se encontró el contrato "${id}" entre los casos prioritarios cargados. Puede no estar en el top de mayor riesgo.`} />
    );
  }

  return (
    <div className="space-y-6">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
      >
        <ArrowLeft size={15} aria-hidden /> Volver
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight sm:text-2xl">{caso.nombre_entidad ?? "Entidad desconocida"}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Contrato {caso.id_contrato} · {caso.dpto ?? "—"}
            {caso.municipio ? `, ${caso.municipio}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-2xl font-bold tabular-nums">{caso.score.toFixed(1)}</p>
            <p className="text-xs text-gray-400">score de riesgo</p>
          </div>
          <TierBadge tier={caso.tier} size="md" />
        </div>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Datos del contrato
        </h2>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          <Field label="Proveedor" value={caso.nombre_proveedor} />
          <Field label="Modalidad" value={caso.modalidad} />
          <Field label="Año" value={caso.anio} />
          <Field label="Fecha de firma" value={formatDate(caso.fecha_firma)} />
          <Field label="Valor" value={formatCOPFull(caso.valor_contrato)} />
          <Field label="Fuente" value={caso.source} />
          <Field label="Banderas aplicables" value={formatInt(caso.n_flags_aplicables)} />
          <Field label="Banderas disparadas" value={formatInt(caso.n_flags_disparados)} />
        </dl>
        {caso.urlproceso && (
          <a
            href={caso.urlproceso}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-5 inline-flex items-center gap-1.5 rounded-md bg-gray-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white"
          >
            Ver proceso en SECOP <ExternalLink size={14} aria-hidden />
          </a>
        )}
      </section>

      <section className="rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <h2 className="border-b border-gray-200 p-5 pb-4 text-sm font-semibold uppercase tracking-wide text-gray-500 dark:border-gray-800 dark:text-gray-400">
          Desglose del score — banderas disparadas
        </h2>
        {caso.banderas.length === 0 ? (
          <p className="flex items-center gap-2 p-5 text-sm text-gray-500 dark:text-gray-400">
            <FileWarning size={16} aria-hidden /> Ninguna bandera se activó para este contrato.
          </p>
        ) : (
          <ul className="divide-y divide-gray-100 dark:divide-gray-800/60">
            {caso.banderas.map((b) => (
              <li key={b.flag_id} className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold text-gray-900 dark:text-gray-100">
                    {b.flag_id} · {b.nombre}
                  </p>
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                    peso {b.peso}
                  </span>
                </div>
                {Object.keys(b.evidence ?? {}).length > 0 && (
                  <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
                    {describeEvidence(b.evidence).map((f) => (
                      <div key={f.key}>
                        <dt className="text-xs text-gray-400 dark:text-gray-500">{f.label}</dt>
                        <dd className="text-sm text-gray-800 dark:text-gray-200">{f.value}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-xs text-gray-400 dark:text-gray-600">
        Este puntaje es un indicador de riesgo para priorizar auditoría, no una acusación de responsabilidad. Ver{" "}
        <Link to="/metodologia" className="underline underline-offset-2 hover:text-gray-600 dark:hover:text-gray-400">
          metodología
        </Link>
        .
      </p>
    </div>
  );
}
