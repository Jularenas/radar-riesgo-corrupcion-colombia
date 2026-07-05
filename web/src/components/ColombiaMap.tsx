import { useEffect, useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import type { DepartamentoResumenRow, NivelRiesgo } from "@/types/artifacts";
import { SIN_DATOS_HEX, TIER_LABELS, TIER_ORDER, TIER_SOLID_CLASSES, tierForScore, tierHex } from "@/lib/tier";
import { formatInt, formatScore } from "@/lib/format";
import { LoadingState, ErrorState } from "@/components/StateViews";

interface DptoProps {
  cod_dpto: string;
  dpto: string;
}

type DptoFeature = Feature<Geometry, DptoProps>;
type DptoFeatureCollection = FeatureCollection<Geometry, DptoProps>;

export interface ColombiaMapProps {
  departamentos: DepartamentoResumenRow[];
  niveles: NivelRiesgo[];
  onSelect: (codDpto: string) => void;
}

const GEO_URL = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/colombia-departamentos.geojson`;

// SVG viewBox size + geoMercator center/scale, solved analytically with d3-geo's
// geoPath().bounds() against the actual departments geometry (mainland + San
// Andrés) so the country fills the frame without manual trial and error --
// see the derivation notes in this milestone's report. Re-derive if the
// source geography file ever changes.
const WIDTH = 520;
const HEIGHT = 620;
const PROJECTION_CENTER: [number, number] = [-72.93, 4.11];
const PROJECTION_SCALE = 1700;

/**
 * Colombia department choropleth. Source: DANE's Marco Geoestadístico
 * Nacional 2018 (official government geographic boundaries), reformatted to
 * GeoJSON and simplified to 4-decimal coordinate precision -- see
 * `web/public/colombia-departamentos.geojson` and web/README.md for
 * provenance. `properties.cod_dpto` is the 2-digit DIVIPOLA code, matching
 * `resumen_nacional.json`'s `departamentos[].cod_dpto` exactly (verified: all
 * 33 codes present in both).
 */
export function ColombiaMap({ departamentos, niveles, onSelect }: ColombiaMapProps) {
  const [fc, setFc] = useState<DptoFeatureCollection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hovered, setHovered] = useState<{ cod: string; x: number; y: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(GEO_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<DptoFeatureCollection>;
      })
      .then((data) => {
        if (!cancelled) setFc(data);
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo cargar el mapa de departamentos.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const byCod = useMemo(() => {
    const m = new Map<string, DepartamentoResumenRow>();
    for (const d of departamentos) m.set(d.cod_dpto, d);
    return m;
  }, [departamentos]);

  const hoveredRow = hovered ? byCod.get(hovered.cod) : undefined;

  if (error) {
    return <ErrorState message={error} />;
  }
  if (!fc) {
    return <LoadingState label="Cargando mapa de Colombia…" />;
  }

  return (
    <div className="relative">
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{ center: PROJECTION_CENTER, scale: PROJECTION_SCALE }}
        width={WIDTH}
        height={HEIGHT}
        style={{ width: "100%", height: "auto" }}
        role="img"
        aria-label="Mapa de Colombia coloreado por score de riesgo promedio de cada departamento"
      >
        <Geographies geography={fc}>
          {({ geographies }: { geographies: DptoFeature[] }) =>
            geographies.map((g) => {
              const cod = g.properties.cod_dpto;
              const row = byCod.get(cod);
              const hasData = !!row && row.n_contratos > 0;
              const tier = hasData ? tierForScore(row.score_promedio, niveles) : null;
              const fill = hasData ? tierHex(tier) : SIN_DATOS_HEX;
              return (
                <Geography
                  key={cod}
                  geography={g}
                  onClick={() => onSelect(cod)}
                  onMouseEnter={(evt) => setHovered({ cod, x: evt.clientX, y: evt.clientY })}
                  onMouseMove={(evt) => setHovered({ cod, x: evt.clientX, y: evt.clientY })}
                  onMouseLeave={() => setHovered(null)}
                  tabIndex={0}
                  aria-label={row?.dpto ?? cod}
                  style={{
                    default: { fill, stroke: "#ffffff", strokeWidth: 0.5, outline: "none", cursor: "pointer" },
                    hover: { fill, stroke: "#111827", strokeWidth: 1.25, outline: "none", cursor: "pointer" },
                    pressed: { fill, stroke: "#111827", strokeWidth: 1.5, outline: "none" },
                  }}
                />
              );
            })
          }
        </Geographies>
      </ComposableMap>

      {hovered && (
        <div
          className="pointer-events-none fixed z-30 max-w-xs rounded-md border border-gray-200 bg-white px-3 py-2 text-xs shadow-lg dark:border-gray-700 dark:bg-gray-900"
          style={{ left: hovered.x + 14, top: hovered.y + 14 }}
        >
          <p className="font-semibold text-gray-900 dark:text-gray-100">{hoveredRow?.dpto ?? hovered.cod}</p>
          {hoveredRow && hoveredRow.n_contratos > 0 ? (
            <>
              <p className="text-gray-600 dark:text-gray-400">{formatInt(hoveredRow.n_contratos)} contratos</p>
              <p className="text-gray-600 dark:text-gray-400">Score promedio: {formatScore(hoveredRow.score_promedio)}</p>
            </>
          ) : (
            <p className="text-gray-500 dark:text-gray-500">Sin contratos en la muestra</p>
          )}
          <p className="mt-1 text-[11px] text-gray-400 dark:text-gray-500">Clic para ver el detalle</p>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-600 dark:text-gray-400">
        <span className="font-medium text-gray-500 dark:text-gray-400">Score promedio:</span>
        {TIER_ORDER.map((t) => (
          <span key={t} className="flex items-center gap-1.5">
            <span className={`h-3 w-3 rounded-sm ${TIER_SOLID_CLASSES[t]}`} />
            {TIER_LABELS[t]}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm border border-gray-400" style={{ backgroundColor: SIN_DATOS_HEX }} />
          Sin datos
        </span>
      </div>
    </div>
  );
}
