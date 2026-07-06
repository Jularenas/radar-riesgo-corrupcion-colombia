import { useEffect, useState, type DependencyList } from "react";
import { getCasosChunk, getContratosRecientesChunk } from "@/lib/data";
import type { CasoPrioritario, ContratoReciente } from "@/types/artifacts";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** Generic one-shot fetch-on-mount hook for the single-file artifacts. */
export function useAsyncData<T>(loader: () => Promise<T>, deps: DependencyList): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });
    loader()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((e: unknown) => {
        if (!cancelled) setState({ data: null, loading: false, error: errorMessage(e) });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

export interface ChunkedListState<T> {
  items: T[];
  loadedChunks: number;
  totalChunks: number | null;
  nItemsTotal: number | null;
  loading: boolean;
  error: string | null;
}

interface Chunk<T> {
  n_chunks: number;
  n_items_total: number;
  items: T[];
}

/**
 * Loads chunk 0 of a paginated artifact first (fast first paint), then keeps
 * fetching subsequent chunks in the background and appends them, per
 * PLAN.md's "don't block first paint on all chunks" guidance. Shared by
 * useCasosPrioritarios (score-sorted) and useContratosRecientes
 * (fecha_firma-sorted) -- same pagination algorithm, different endpoint.
 */
function useChunkedList<T>(getChunk: (idx: number) => Promise<Chunk<T>>): ChunkedListState<T> {
  const [items, setItems] = useState<T[]>([]);
  const [loadedChunks, setLoadedChunks] = useState(0);
  const [totalChunks, setTotalChunks] = useState<number | null>(null);
  const [nItemsTotal, setNItemsTotal] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setItems([]);
    setLoadedChunks(0);
    setTotalChunks(null);
    setNItemsTotal(null);
    setError(null);

    async function run(): Promise<void> {
      const first = await getChunk(0);
      if (cancelled) return;
      setTotalChunks(first.n_chunks);
      setNItemsTotal(first.n_items_total);
      setItems(first.items);
      setLoadedChunks(1);

      for (let i = 1; i < first.n_chunks; i++) {
        const chunk = await getChunk(i);
        if (cancelled) return;
        setItems((prev) => [...prev, ...chunk.items]);
        setLoadedChunks((n) => n + 1);
      }
    }

    run().catch((e: unknown) => {
      if (!cancelled) setError(errorMessage(e));
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loading = totalChunks === null || loadedChunks < totalChunks;
  return { items, loadedChunks, totalChunks, nItemsTotal, loading, error };
}

export type CasosPrioritariosState = ChunkedListState<CasoPrioritario>;

export function useCasosPrioritarios(): CasosPrioritariosState {
  return useChunkedList(getCasosChunk);
}

export type ContratosRecientesState = ChunkedListState<ContratoReciente>;

export function useContratosRecientes(): ContratosRecientesState {
  return useChunkedList(getContratosRecientesChunk);
}
