/**
 * TypeScript mirrors of the JSON Schemas at
 * `pipeline/src/pipeline/export/schemas/*.schema.json`. Those schemas are the
 * authoritative shape reference (see PLAN.md, "Web artifact contract") --
 * keep this file in sync with them, not the other way around.
 */

export type Tier = "bajo" | "medio" | "alto" | "critico";

export type NivelBandera = "contract" | "entity";

// ---------------------------------------------------------------------------
// meta.json
// ---------------------------------------------------------------------------

export interface FlagCatalogItem {
  id: string;
  nombre: string;
  nivel: NivelBandera;
  peso: number;
  descripcion: string;
}

export interface NivelRiesgo {
  id: Tier;
  nombre: string;
  min_score: number;
  max_score: number | null;
}

export interface CasoEmblematico {
  slug: string;
  nombre: string;
  periodo: [number, number];
  n_matched: number;
  mejor_score: number | null;
  mejor_tier: Tier | null;
  percentil_anio: number | null;
  cuartil_superior: boolean | null;
  confirmado_manualmente: boolean;
}

export interface MonitorCiudadanoResumen {
  n_total: number;
  n_matched: number;
  match_rate_pct: number | null;
  nota: string;
}

export interface Backtest {
  auc_roc: number | null;
  objetivo_auc_roc: number;
  lift_top_decil: number | null;
  objetivo_lift_top_decil: number;
  cumple_objetivos: boolean;
  n_contratos_evaluados: number;
  n_positivos_l1_l4: number;
  precision_top_1pct: number | null;
  precision_top_5pct: number | null;
  precision_top_10pct: number | null;
  casos_emblematicos: CasoEmblematico[];
  n_casos_emblematicos_total: number;
  n_casos_emblematicos_con_coincidencias_genuinas: number;
  n_casos_emblematicos_en_percentil_superior: number;
  monitor_ciudadano: MonitorCiudadanoResumen;
  resumen: string;
}

export interface Meta {
  generado_en: string;
  version: { git_commit: string | null };
  banderas: FlagCatalogItem[];
  niveles_riesgo: NivelRiesgo[];
  formula_score: string;
  shrinkage: { k: number; min_contratos_rank: number };
  backtest: Backtest;
  artefactos: {
    casos_prioritarios: { top_n: number; chunk_size: number; n_chunks: number; patron_archivo: string };
    entidades_top: { top_n: number; criterio: string };
    proveedores_top: { top_n: number; criterio: string };
    departamentos: { patron_archivo: string; top_n_entidades_por_departamento: number };
  };
}

// ---------------------------------------------------------------------------
// resumen_nacional.json
// ---------------------------------------------------------------------------

export interface KpisNacionales {
  contratos_analizados: number;
  valor_total_cop: number;
  casos_criticos: number;
  pct_contratacion_directa: number;
  n_entidades: number;
  n_proveedores: number;
  n_contratos_sin_departamento: number;
  pct_geolocalizado: number;
}

export interface SerieAnioModalidad {
  anio: number;
  modalidad: string;
  n_contratos: number;
  valor_total: number;
}

export interface SerieAnioTier {
  anio: number;
  tier: Tier;
  n_contratos: number;
}

export interface DepartamentoResumenRow {
  cod_dpto: string;
  dpto: string | null;
  n_contratos: number;
  valor_total: number;
  score_promedio: number | null;
  n_bajo: number;
  n_medio: number;
  n_alto: number;
  n_criticos: number;
}

export interface ResumenNacional {
  generado_en: string;
  kpis: KpisNacionales;
  serie_anio_modalidad: SerieAnioModalidad[];
  serie_anio_tier: SerieAnioTier[];
  departamentos: DepartamentoResumenRow[];
}

// ---------------------------------------------------------------------------
// Shared: fired-flag evidence, entity rows
// ---------------------------------------------------------------------------

export interface BanderaEvidencia {
  flag_id: string;
  nombre: string;
  peso: number;
  evidence: Record<string, unknown>;
}

export interface EntidadRow {
  nit_entidad: string;
  nombre_entidad: string | null;
  cod_dpto: string | null;
  dpto: string | null;
  n_contratos: number;
  valor_total: number | null;
  score: number | null;
  tier: Tier | null;
  datos_insuficientes: boolean;
  n_flags_aplicables: number;
  n_flags_disparados: number;
  banderas: BanderaEvidencia[];
}

// ---------------------------------------------------------------------------
// departamentos/{cod_dpto}.json
// ---------------------------------------------------------------------------

export interface MunicipioRow {
  cod_mpio: string;
  municipio: string | null;
  n_contratos: number;
  valor_total: number;
  score: number | null;
  tier: Tier | null;
  datos_insuficientes: boolean;
}

export interface SerieAnioDepartamento {
  anio: number;
  n_contratos: number;
  valor_total: number;
  score_promedio: number | null;
}

export interface DepartamentoDetalle {
  cod_dpto: string;
  dpto: string | null;
  n_contratos: number;
  valor_total: number;
  score_promedio: number | null;
  n_bajo: number;
  n_medio: number;
  n_alto: number;
  n_criticos: number;
  municipios: MunicipioRow[];
  top_entidades: EntidadRow[];
  serie_anio: SerieAnioDepartamento[];
}

// ---------------------------------------------------------------------------
// casos_prioritarios/{idx}.json
// ---------------------------------------------------------------------------

export interface CasoPrioritario {
  id_contrato: string;
  nit_entidad: string | null;
  nombre_entidad: string | null;
  doc_proveedor: string | null;
  nombre_proveedor: string | null;
  cod_dpto: string | null;
  dpto: string | null;
  cod_mpio: string | null;
  municipio: string | null;
  modalidad: string | null;
  anio: number | null;
  valor_contrato: number | null;
  fecha_firma: string | null;
  source: string | null;
  score: number;
  tier: Tier;
  urlproceso: string | null;
  n_flags_aplicables: number;
  n_flags_disparados: number;
  banderas: BanderaEvidencia[];
}

export interface CasosPrioritariosChunk {
  chunk_index: number;
  n_chunks: number;
  n_items_total: number;
  items: CasoPrioritario[];
}

// ---------------------------------------------------------------------------
// contratos_recientes/{idx}.json
// ---------------------------------------------------------------------------

/** Same row shape as CasoPrioritario -- ordered by fecha_firma desc instead of score desc (see METHODOLOGY.md 6.11). */
export type ContratoReciente = CasoPrioritario;

export interface ContratosRecientesChunk {
  chunk_index: number;
  n_chunks: number;
  n_items_total: number;
  items: ContratoReciente[];
}

// ---------------------------------------------------------------------------
// entidades_top.json / proveedores_top.json
// ---------------------------------------------------------------------------

export interface EntidadesTop {
  n_items: number;
  items: EntidadRow[];
}

export interface ProveedorRow {
  doc_proveedor: string;
  nombre_proveedor: string | null;
  es_persona_natural: boolean | null;
  n_contratos: number;
  valor_total: number | null;
  score: number | null;
  tier: Tier | null;
  datos_insuficientes: boolean;
}

export interface ProveedoresTop {
  n_items: number;
  items: ProveedorRow[];
}
