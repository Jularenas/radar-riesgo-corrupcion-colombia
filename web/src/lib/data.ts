import type {
  CasoPrioritario,
  CasosPrioritariosChunk,
  DepartamentoDetalle,
  EntidadesTop,
  Meta,
  ProveedoresTop,
  ResumenNacional,
} from "@/types/artifacts";

/**
 * Fetch layer for the static JSON artifacts under `/data/` (see PLAN.md,
 * "Web artifact contract"). In dev, `web/public/data/` is seeded from
 * `web/src/fixtures/` by `scripts/seed-fixtures.mjs` (see package.json's
 * `predev`/`prebuild`); in production it's the pipeline's real M6 export.
 * Either way this module just fetches whatever is actually at `/data/...`.
 */

function dataUrl(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${base}/data/${path}`;
}

const jsonCache = new Map<string, Promise<unknown>>();

function fetchJson<T>(path: string): Promise<T> {
  const url = dataUrl(path);
  const cached = jsonCache.get(url);
  if (cached) return cached as Promise<T>;

  const promise = fetch(url).then((res) => {
    if (!res.ok) {
      throw new Error(`No se pudo cargar ${path} (HTTP ${res.status})`);
    }
    return res.json() as Promise<T>;
  });
  // Drop failed fetches from the cache so a later retry (e.g. remount) can
  // actually try again instead of replaying the same rejection forever.
  promise.catch(() => jsonCache.delete(url));
  jsonCache.set(url, promise);
  return promise;
}

export function getMeta(): Promise<Meta> {
  return fetchJson<Meta>("meta.json");
}

export function getResumenNacional(): Promise<ResumenNacional> {
  return fetchJson<ResumenNacional>("resumen_nacional.json");
}

export function getDepartamento(codDpto: string): Promise<DepartamentoDetalle> {
  return fetchJson<DepartamentoDetalle>(`departamentos/${codDpto}.json`);
}

export function getCasosChunk(idx: number): Promise<CasosPrioritariosChunk> {
  const idxStr = String(idx).padStart(3, "0");
  return fetchJson<CasosPrioritariosChunk>(`casos_prioritarios/${idxStr}.json`);
}

export function getEntidadesTop(): Promise<EntidadesTop> {
  return fetchJson<EntidadesTop>("entidades_top.json");
}

export function getProveedoresTop(): Promise<ProveedoresTop> {
  return fetchJson<ProveedoresTop>("proveedores_top.json");
}

/**
 * Sequentially loads casos_prioritarios chunks looking for one contract.
 * Chunk 0 is fetched (and cached) first regardless of whether the Casos
 * table already loaded it, so this works standalone too (e.g. a direct link
 * to /casos/:id).
 */
export async function findCasoPorId(idContrato: string): Promise<CasoPrioritario | null> {
  const first = await getCasosChunk(0);
  const inFirst = first.items.find((c) => c.id_contrato === idContrato);
  if (inFirst) return inFirst;

  for (let i = 1; i < first.n_chunks; i++) {
    const chunk = await getCasosChunk(i);
    const found = chunk.items.find((c) => c.id_contrato === idContrato);
    if (found) return found;
  }
  return null;
}
