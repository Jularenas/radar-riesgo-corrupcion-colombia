# Dashboard — Radar de Riesgo de Corrupción

React 19 + TypeScript + Vite + Tailwind v4. Cuatro vistas (Panorama, Casos prioritarios,
Detalle de caso, Metodología) consumiendo los artefactos JSON descritos en PLAN.md ("Web
artifact contract"). Ver el [README de la raíz](../README.md) para el runbook completo
(refrescar datos → reconstruir → desplegar).

## Datos: fixtures vs. datos reales

`web/public/data/` (ignorado por git, lo genera el pipeline vía `make export`) es lo que la
app sirve en tiempo de ejecución. `web/public/data/` **no existe** en un clon nuevo hasta que
corres el pipeline — así que `scripts/seed-fixtures.mjs` copia automáticamente
`web/src/fixtures/` (comprometido a git: 50 contratos sintéticos, los 33 departamentos reales
de Colombia, casos que cubren los 4 niveles de riesgo) a `public/data/` antes de `npm run dev`
o `npm run build`, **solo si `public/data/meta.json` no existe todavía** — nunca sobrescribe
datos reales ya generados.

Para regenerar los fixtures (si cambia el esquema de algún artefacto):
```bash
cd ../pipeline && uv run python -m pipeline.export.build_fixtures
```

## Desarrollo

```bash
npm install
npm run dev       # http://localhost:5173
```

`react-simple-maps@3.0.0` aún no publica un rango de peer-dependency compatible con React 19
(funciona bien en la práctica) — por eso `.npmrc` fija `legacy-peer-deps=true`; sin eso,
`npm install` falla con ERESOLVE en un clon nuevo.

## Build de producción

```bash
npm run build     # tsc -b && vite build -> dist/
npm run preview   # sirve dist/ localmente
```

Para GitHub Pages (sitio de proyecto, no en la raíz del dominio) hay que pasar `--base`:
```bash
npm run build -- --base=/nombre-del-repo/
```
(el workflow en `.github/workflows/deploy-gh-pages.yml` ya lo hace automáticamente).

## Estructura

```
web/src/
├── types/artifacts.ts      # tipos TS espejo de pipeline/src/pipeline/export/schemas/*.schema.json
├── lib/
│   ├── data.ts              # fetch + cache de los JSON en /data/
│   ├── hooks.ts              # useAsyncData, useCasosPrioritarios (carga progresiva de chunks)
│   ├── tier.ts               # paleta de riesgo (única fuente de verdad: verde/amarillo/naranja/rojo)
│   ├── format.ts             # formato es-CO (moneda, fechas, porcentajes)
│   ├── evidence.ts           # traduce la evidencia de cada bandera (F01-F14) a texto legible
│   └── cn.ts                 # clsx + tailwind-merge
├── components/                # TierBadge, KpiCard, ColombiaMap, Layout, StateViews
└── pages/                     # Panorama, Departamento, CasosPrioritarios, CasoDetalle, Metodologia
```

## Mapa de Colombia

`public/colombia-departamentos.geojson`: límites departamentales oficiales (DANE, Marco
Geoestadístico Nacional), simplificados a 4 decimales. `properties.cod_dpto` es el código
DIVIPOLA de 2 dígitos, la misma clave usada en `resumen_nacional.json`.

## Linting

```bash
npm run lint      # oxlint
```
