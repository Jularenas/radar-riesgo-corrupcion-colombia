import { formatDate, formatInt, formatNumber, formatRatioAsPercent, humanizeKey } from "@/lib/format";
import { formatCOP } from "@/lib/format";

/**
 * Evidence dicts are genuinely free-form: `pipeline/src/pipeline/flags/common.py`
 * builds them from "every other SQL column" each flag module selects, so the
 * key set is whatever that module's query happens to project (see
 * `pipeline/src/pipeline/flags/f01_unico_oferente.py` .. `f14_valor_redondo.py`).
 * This is a best-effort label/format dictionary covering every key observed
 * across the real exported artifacts (`web/public/data/casos_prioritarios/`,
 * `entidades_top.json`, department `top_entidades`) plus the fixture's
 * synthetic placeholder key ("nota"). Unknown keys still render legibly via
 * `humanizeKey` + a type-based guess in `formatEvidenceValue`, so a future
 * flag/column change can't produce raw unreadable JSON.
 */

type EvidenceKind = "money" | "date" | "ratio" | "bool" | "int" | "number" | "list" | "text";

interface EvidenceFieldMeta {
  label: string;
  kind: EvidenceKind;
}

const EVIDENCE_FIELD_META: Record<string, EvidenceFieldMeta> = {
  // F01 -- Único oferente
  num_oferentes_unicos: { label: "Oferentes únicos", kind: "int" },
  modalidad_norm: { label: "Modalidad", kind: "text" },
  num_invitados: { label: "Proveedores invitados", kind: "int" },
  num_respuestas: { label: "Respuestas recibidas", kind: "int" },
  id_del_proceso: { label: "ID del proceso (SECOP)", kind: "text" },

  // F02 -- Empresa exprés
  fecha_matricula: { label: "Fecha de matrícula (RUES)", kind: "date" },
  fecha_publicacion: { label: "Fecha de publicación del proceso", kind: "date" },
  dias_desde_matricula: { label: "Días entre matrícula y publicación", kind: "int" },
  dias_antes_publicacion: { label: "Días entre matrícula y publicación", kind: "int" },

  // F03 -- Adiciones excesivas
  source: { label: "Fuente del contrato", kind: "text" },
  dias_adicionados: { label: "Días adicionados", kind: "int" },
  duracion_dias_inicial: { label: "Duración inicial (días)", kind: "int" },
  f03_tiempo: { label: "¿Se activó por plazo adicionado?", kind: "bool" },
  ratio_adicion_dinero: { label: "Adición en valor sobre el inicial", kind: "ratio" },
  f03_dinero: { label: "¿Se activó por adición en valor?", kind: "bool" },
  fuente_dinero: { label: "Fuente de la adición en valor", kind: "text" },

  // F04 -- Abuso de contratación directa (entidad)
  nombre_entidad: { label: "Entidad", kind: "text" },
  cod_dpto: { label: "Departamento (código DIVIPOLA)", kind: "text" },
  share_directa: { label: "Participación de la entidad en contratación directa", kind: "ratio" },
  mean_share_peers: { label: "Promedio del grupo de pares", kind: "ratio" },
  sd_share_peers: { label: "Desviación estándar del grupo de pares", kind: "ratio" },
  n_peers: { label: "Entidades pares comparadas", kind: "int" },
  z_score: { label: "Desviaciones estándar sobre el grupo de pares", kind: "number" },

  // F05 -- Fraccionamiento
  nit_entidad_norm: { label: "NIT de la entidad", kind: "text" },
  doc_proveedor_norm: { label: "Documento del proveedor", kind: "text" },
  unspsc_segmento: { label: "Segmento UNSPSC", kind: "text" },
  n_contratos_ventana: { label: "Contratos en la ventana de 90 días", kind: "int" },
  suma_valor_ventana: { label: "Valor sumado en la ventana", kind: "money" },
  umbral_smmlv_cop: { label: "Umbral (280 SMMLV en COP)", kind: "money" },

  // F06 -- Carrusel
  bucket_24m: { label: "Ventana de 24 meses", kind: "text" },
  n_procesos_grupo: { label: "Procesos competitivos en el grupo", kind: "int" },
  n_ganadores_distintos: { label: "Ganadores distintos", kind: "int" },
  participacion_minima_ganador: { label: "Participación mínima de un ganador", kind: "ratio" },
  indice_alternancia: { label: "Índice de alternancia", kind: "ratio" },

  // F07 -- Ventana de licitación corta
  fecha_recepcion_respuestas: { label: "Cierre de recepción de ofertas", kind: "date" },
  dias_ventana: { label: "Días entre publicación y cierre", kind: "int" },
  piso_dias: { label: "Mínimo reglamentario (días)", kind: "int" },

  // F08 -- Precio calcado
  valor_contrato: { label: "Valor del contrato", kind: "money" },
  precio_base: { label: "Precio base publicado", kind: "money" },
  desviacion_pct: { label: "Desviación frente al precio base", kind: "ratio" },

  // F09 -- Afán de diciembre
  fecha_firma: { label: "Fecha de firma", kind: "date" },

  // F10 -- Ventana electoral
  window_id: { label: "Ventana electoral", kind: "text" },
  tipo_ventana: { label: "Tipo de ventana", kind: "text" },
  descripcion_ventana: { label: "Descripción de la ventana", kind: "text" },

  // F11 -- Proveedor sancionado
  n_sanciones_antes_firma: { label: "Sanciones antes de la firma", kind: "int" },
  n_sanciones_total_contexto: { label: "Sanciones totales (cualquier fecha, contexto)", kind: "int" },
  fuentes_antes_firma: { label: "Fuente(s) de la sanción", kind: "list" },
  fuentes_total_contexto: { label: "Fuente(s), contexto completo", kind: "list" },
  sancion_mas_reciente_antes_firma: { label: "Sanción más reciente antes de la firma", kind: "date" },

  // F12 -- Concentración/dependencia (entidad)
  anio: { label: "Año", kind: "int" },
  doc_proveedor_dominante: { label: "Proveedor dominante (documento)", kind: "text" },
  n_contratos_entidad_anual: { label: "Contratos de la entidad ese año", kind: "int" },
  participacion_proveedor_en_entidad: { label: "Participación del proveedor en la entidad", kind: "ratio" },
  condicion_a_captura_entidad: { label: "¿Un proveedor captura más del 50% del valor?", kind: "bool" },
  n_contratos_proveedor_anual: { label: "Contratos del proveedor ese año", kind: "int" },
  dependencia_proveedor_en_entidad: { label: "Dependencia del proveedor en esta entidad", kind: "ratio" },
  condicion_b_dependencia_proveedor: { label: "¿El proveedor depende en más del 80% de esta entidad?", kind: "bool" },

  // F13 -- Objeto vago
  longitud_objeto: { label: "Longitud del objeto contractual (caracteres)", kind: "int" },
  objeto_len: { label: "Longitud del objeto contractual (caracteres)", kind: "int" },
  frecuencia_objeto: { label: "Veces que se repite este objeto", kind: "int" },
  umbral_decil_superior: { label: "Umbral del decil superior de frecuencia", kind: "number" },
  objeto_muy_corto: { label: "¿Objeto muy corto (menos de 40 caracteres)?", kind: "bool" },
  objeto_repetitivo: { label: "¿Objeto repetitivo?", kind: "bool" },

  // Fixture placeholder
  nota: { label: "Nota", kind: "text" },
};

function formatEvidenceValue(value: unknown, kind: EvidenceKind | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  switch (kind) {
    case "money":
      return typeof value === "number" ? formatCOP(value) : String(value);
    case "date":
      return typeof value === "string" ? formatDate(value) : String(value);
    case "ratio":
      return typeof value === "number" ? formatRatioAsPercent(value) : String(value);
    case "bool":
      return value === true ? "Sí" : value === false ? "No" : String(value);
    case "int":
      return typeof value === "number" ? formatInt(value) : String(value);
    case "number":
      return typeof value === "number" ? formatNumber(value, { maximumFractionDigits: 2 }) : String(value);
    case "list":
      return Array.isArray(value) ? value.join(", ") : String(value);
    case "text":
      return String(value);
    default:
      return guessFormat(value);
  }
}

/** Best-effort formatting for keys with no explicit metadata entry. */
function guessFormat(value: unknown): string {
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "number") return formatNumber(value, { maximumFractionDigits: 2 });
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export interface EvidenceDisplayField {
  key: string;
  label: string;
  value: string;
}

/** Turn a raw evidence object into an ordered list of {label, value} ready to render. */
export function describeEvidence(evidence: Record<string, unknown>): EvidenceDisplayField[] {
  return Object.entries(evidence).map(([key, value]) => {
    const meta = EVIDENCE_FIELD_META[key];
    return {
      key,
      label: meta?.label ?? humanizeKey(key),
      value: formatEvidenceValue(value, meta?.kind),
    };
  });
}
