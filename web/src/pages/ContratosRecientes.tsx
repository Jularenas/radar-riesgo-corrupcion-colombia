import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, Download, Loader2, Search } from "lucide-react";
import { useContratosRecientes } from "@/lib/hooks";
import { formatCOP, formatDate, formatInt } from "@/lib/format";
import { TIER_LABELS, TIER_ORDER } from "@/lib/tier";
import { TierBadge } from "@/components/TierBadge";
import { LoadingState, ErrorState } from "@/components/StateViews";
import type { ContratoReciente, Tier } from "@/types/artifacts";

const MODALIDAD_LABELS: Record<string, string> = {
  LICITACION_PUBLICA: "Licitación pública",
  SELECCION_ABREVIADA: "Selección abreviada",
  CONCURSO_MERITOS: "Concurso de méritos",
  CONTRATACION_DIRECTA: "Contratación directa",
  MINIMA_CUANTIA: "Mínima cuantía",
  REGIMEN_ESPECIAL: "Régimen especial",
  OTRO: "Otro",
};

function toCsvRow(fields: (string | number | null | undefined)[]): string {
  return fields
    .map((f) => {
      const s = f === null || f === undefined ? "" : String(f);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    })
    .join(",");
}

function downloadContratosCsv(rows: ContratoReciente[]): void {
  const header = toCsvRow([
    "id_contrato", "departamento", "municipio", "entidad", "proveedor",
    "modalidad", "fecha_firma", "valor_contrato", "score", "nivel_riesgo", "urlproceso",
  ]);
  const body = rows.map((r) =>
    toCsvRow([
      r.id_contrato, r.dpto, r.municipio, r.nombre_entidad, r.nombre_proveedor,
      r.modalidad, r.fecha_firma, r.valor_contrato, r.score, TIER_LABELS[r.tier], r.urlproceso,
    ]),
  );
  const csv = [header, ...body].join("\n");
  const blob = new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "contratos_recientes.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function ContratosRecientesPage() {
  const { items, loading, loadedChunks, totalChunks, nItemsTotal, error } = useContratosRecientes();
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [tierFilter, setTierFilter] = useState<Tier | "">("");
  const [dptoFilter, setDptoFilter] = useState<string>("");
  const [modalidadFilter, setModalidadFilter] = useState<string>("");
  const [sorting, setSorting] = useState<SortingState>([{ id: "fecha_firma", desc: true }]);

  const dptosDisponibles = useMemo(
    () => [...new Set(items.map((i) => i.dpto).filter((v): v is string => !!v))].sort(),
    [items],
  );
  const modalidadesDisponibles = useMemo(
    () => [...new Set(items.map((i) => i.modalidad).filter((v): v is string => !!v))].sort(),
    [items],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((row) => {
      if (tierFilter && row.tier !== tierFilter) return false;
      if (dptoFilter && row.dpto !== dptoFilter) return false;
      if (modalidadFilter && row.modalidad !== modalidadFilter) return false;
      if (q && !`${row.nombre_entidad ?? ""} ${row.nombre_proveedor ?? ""}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [items, search, tierFilter, dptoFilter, modalidadFilter]);

  const columns = useMemo<ColumnDef<ContratoReciente>[]>(
    () => [
      {
        accessorKey: "fecha_firma",
        header: "Fecha de firma",
        cell: (c) => formatDate(c.getValue<string | null>()),
      },
      { accessorKey: "dpto", header: "Departamento", cell: (c) => c.getValue<string | null>() ?? "—" },
      {
        accessorKey: "nombre_entidad",
        header: "Entidad",
        cell: (c) => <span className="line-clamp-1 max-w-[16rem]">{c.getValue<string | null>() ?? "—"}</span>,
      },
      {
        accessorKey: "modalidad",
        header: "Modalidad",
        cell: (c) => {
          const v = c.getValue<string | null>();
          return v ? (MODALIDAD_LABELS[v] ?? v) : "—";
        },
      },
      {
        accessorKey: "valor_contrato",
        header: "Valor",
        cell: (c) => formatCOP(c.getValue<number | null>()),
      },
      {
        accessorKey: "score",
        header: "Score",
        cell: (c) => (
          <div className="flex items-center gap-2">
            <span className="tabular-nums font-medium">{c.getValue<number>().toFixed(1)}</span>
            <TierBadge tier={c.row.original.tier} size="sm" />
          </div>
        ),
      },
    ],
    [],
  );

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  if (loading && items.length === 0) return <LoadingState label="Cargando contratos recientes…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Contratos recientes</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {nItemsTotal !== null ? `Los ${formatInt(nItemsTotal)} contratos firmados más recientemente` : "Cargando…"}
            {loading && totalChunks && (
              <span className="ml-2 inline-flex items-center gap-1 text-xs text-gray-400">
                <Loader2 className="animate-spin" size={12} aria-hidden /> cargando bloque {loadedChunks + 1}/
                {totalChunks}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => downloadContratosCsv(filtered)}
          disabled={filtered.length === 0}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          <Download size={14} aria-hidden /> Exportar CSV ({formatInt(filtered.length)})
        </button>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
        Esta vista ordena por fecha de firma, no por score. Un contrato reciente suele tener un score más bajo aunque
        tenga un patrón real de riesgo: la bandera de mayor peso (proveedor sancionado) depende de sanciones ya
        publicadas, y esas sanciones tardan años en resolverse. Úsela para vigilar actividad en curso, no como un
        segundo ranking de riesgo.{" "}
        <Link to="/metodologia" className="underline underline-offset-2 hover:text-amber-700 dark:hover:text-amber-100">
          Ver metodología (sección 6.11)
        </Link>
        .
      </div>

      <div className="flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-[14rem]">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" size={15} aria-hidden />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar entidad o proveedor…"
            className="w-full rounded-md border border-gray-300 bg-white py-1.5 pl-8 pr-3 text-sm dark:border-gray-700 dark:bg-gray-900"
          />
        </div>
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value as Tier | "")}
          className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
        >
          <option value="">Todos los niveles</option>
          {TIER_ORDER.map((t) => (
            <option key={t} value={t}>
              {TIER_LABELS[t]}
            </option>
          ))}
        </select>
        <select
          value={dptoFilter}
          onChange={(e) => setDptoFilter(e.target.value)}
          className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
        >
          <option value="">Todos los departamentos</option>
          {dptosDisponibles.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <select
          value={modalidadFilter}
          onChange={(e) => setModalidadFilter(e.target.value)}
          className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900"
        >
          <option value="">Todas las modalidades</option>
          {modalidadesDisponibles.map((m) => (
            <option key={m} value={m}>
              {MODALIDAD_LABELS[m] ?? m}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-800">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-900">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => {
                  const sort = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400"
                    >
                      <span className="inline-flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {sort === "asc" && <ArrowUp size={12} aria-hidden />}
                        {sort === "desc" && <ArrowDown size={12} aria-hidden />}
                        {!sort && <ArrowUpDown size={12} className="text-gray-300 dark:text-gray-700" aria-hidden />}
                      </span>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white dark:divide-gray-800/60 dark:bg-gray-950">
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                onClick={() => navigate(`/casos/${row.original.id_contrato}`)}
                className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900"
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-2.5">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
            {table.getRowModel().rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-gray-400">
                  Sin resultados para estos filtros.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 dark:text-gray-600">
        Mostrando {formatInt(filtered.length)} de {formatInt(items.length)} contratos cargados
        {nItemsTotal !== null && nItemsTotal > items.length ? ` (de ${formatInt(nItemsTotal)} en total)` : ""}. Clic en
        una fila para ver el detalle.
      </p>
    </div>
  );
}
