# Radar de Riesgo de Corrupción — Colombia
Sistema de detección de riesgo de corrupción en contratación pública colombiana, con dashboard web estático.

## Context

Colombia publishes all public procurement on SECOP (via datos.gov.co, Socrata API) and all sanction registries are open data. Nobody has to guess: red flags like single-bidder tenders, contract carousels, express companies, abusive additions, and contract splitting are *computable* from official, auditable sources. The goal is a reproducible pipeline that ingests those sources, standardizes them, computes a transparent risk score per contract/entity/municipality, validates it against **already-identified corruption cases**, and publishes a beautiful, filterable Spanish-language dashboard as a static website.

**Decisions made with user:** SECOP II full + targeted SECOP I for known-case backtesting · Static precomputed architecture (no backend) · Transparent weighted red-flag index (ML deferred to v2) · Spanish UI.
**Execution model:** Implementation milestones are delegated to Sonnet subagents, orchestrated and reviewed between milestones by the main session.

**Framing constraint (legal/ethical):** scores are *risk indicators for audit prioritization*, never accusations. Every displayed case must link back to its official SECOP record (`urlproceso`) and show exactly which flags fired with what evidence. A disclaimer + methodology page is a deliverable, not an afterthought.

## Verified data sources (checked live 2026-07-03 via Socrata API)

| # | Dataset | ID (datos.gov.co) | Rows | Use |
|---|---------|-------------------|------|-----|
| S1 | SECOP II — Contratos Electrónicos | `jbjy-vk9h` | 5,657,593 | Core contract facts. Verified fields: `valor_del_contrato`, `modalidad_de_contratacion`, `dias_adicionados`, `urlproceso`, `nit_entidad`, `documento_proveedor`, `proveedor_adjudicado`, `fecha_de_firma`, `departamento`, `codigo_de_categoria_principal`, `estado_contrato`, `valor_pagado`, start/end dates |
| S2 | SECOP II — Procesos de Contratación | `p6dx-8zbt` | 8,760,641 | Bidding-stage facts. Verified bidder-count fields: `proveedores_unicos_con_respuestas`, `respuestas_al_procedimiento`, `proveedores_invitados`, `visualizaciones_del`; plus `precio_base`, `fecha_de_publicacion_del`, `fecha_de_recepcion_de`, `adjudicado`, `valor_total_adjudicacion`, `duracion` |
| S3 | SECOP I — Procesos de Compra Pública | `f789-7hwg` | (2018+) | Targeted pulls only, for known-case entities/periods |
| S4 | SECOP I — Contratos +16K SMMLV / Integrado | `79ga-5jck` / `rpmr-utcd` (22.1M) | — | Fallback for pre-2018 known-case slices (Odebrecht, Carrusel IDU) |
| S5 | SECOP I — Proponentes | `tauh-5jvn` | — | Bidder lists per legacy process (carrusel co-bidding, targeted only) |
| L1 | Responsabilidad Fiscal — Contraloría | `jr8e-e8tu` | — | Ground-truth labels: fiscally liable persons/companies (NIT/cédula) |
| L2 | Multas y Sanciones SECOP I | `4n4q-k399` | — | Contractual fines labels |
| L3 | SECOP II — Multas y Sanciones | `it5q-hg94` | — | Contractual fines labels (updated daily) |
| L4 | Antecedentes SIRI — Procuraduría | `iaeu-rcn6` | — | Disciplinary sanctions labels |
| E1 | RUES-synced chamber registries (e.g. `c82u-588k`, `gwqv-sqvs`) | — | — | Company `fecha_matricula` for express-company flag; **coverage must be measured in M4**, fallback = throttled per-NIT RUES lookups with local cache, else flag = NULL |
| E2 | DIVIPOLA (DANE) dept/municipality codes | discover in M1 | — | Canonical geography |
| V1 | Monitor Ciudadano — Radiografía hechos de corrupción 2016–2022 | monitorciudadano.co/bases-radiografia-2016-2022 | ~thousands | Independent known-case validation set (Transparencia por Colombia) |
| V2 | Curated landmark cases (hand-built YAML, cited) | in-repo | ~10 | Centros Poblados/MinTIC 2021 · UNGRD carrotanques 2023-24 · PAE La Guajira/Santander 2016-18 · Ruta del Sol II/Odebrecht (ANI) · Carrusel de la Contratación IDU Bogotá 2010-12 · Cartel de la Hemofilia Córdoba 2013-15 · sobrecostos COVID 2020 · Cartel del SIDA Córdoba |

Access: Socrata SODA v2. Keyset pagination (`$order=:id`, `$where=:id > <last>`, `$limit=50000`), `$select` column projection on S2 to cut volume, per-year Parquet partitions, `manifest.json` with row counts + `:updated_at` watermark for incremental refresh. Optional free `SOCRATA_APP_TOKEN` in `.env` (works tokenless, throttled). Full pull ≈ 1.5–2 GB Parquet, run as resumable background task.

## Repository layout

```
corruption/
├── PLAN.md                       # this plan
├── Makefile                      # pull | clean | flags | score | export | web | all | check
├── pipeline/                     # Python 3.12+, uv-managed
│   ├── pyproject.toml  .env.example
│   ├── src/pipeline/
│   │   ├── config.py             # dataset registry (IDs above), paths, params
│   │   ├── extract/  socrata.py  rues.py  monitor_ciudadano.py
│   │   ├── refs/     smmlv.csv  ventanas_electorales.csv  known_cases.yaml  modalidades.csv
│   │   ├── clean/                # DuckDB SQL → canonical marts
│   │   ├── flags/                # f01_unico_oferente.py … f14 (one module per flag + SQL)
│   │   ├── score/                # weights.yaml  scorer.py  backtest.py
│   │   └── export/               # web artifact builder + JSON-schema validation
│   ├── data/{raw,staging,marts,export}/   # gitignored
│   └── tests/                    # pytest, synthetic fixtures per flag
├── web/                          # Vite + React + TS + Tailwind + shadcn/ui + Recharts + react-simple-maps
│   ├── public/data/              # artifacts from pipeline (≤60 MB total)
│   └── src/{pages,components,lib}
└── docs/METHODOLOGY.md           # fuentes, definiciones, pesos, backtest, limitaciones, descargo
```

Storage/compute: **DuckDB + Parquet** (no DB server; handles 10M+ rows locally). Canonical marts: `fct_contrato`, `fct_proceso`, `dim_entidad`, `dim_proveedor`, `sanciones` — normalized NITs (strip verification digit, zero-pad), normalized modality enum, DIVIPOLA geo codes, ISO dates, COP numerics, UNSPSC segment (first 2 digits of `codigo_de_categoria_principal`).

## Red-flag catalog (v1)

Score = `100 × Σ(weights of fired flags) / Σ(weights of applicable flags)` — flags with unknown inputs (e.g. no RUES match) drop out of the denominator instead of penalizing. Tiers: **Bajo <20 · Medio 20–40 · Alto 40–60 · Crítico ≥60** (report percentile alongside).

| ID | Flag (ES) | Level | Definition (precise, testable) | W |
|----|-----------|-------|-------------------------------|---|
| F01 | Único oferente | contract | Competitive modality (licitación, selección abreviada, concurso de méritos) AND `proveedores_unicos_con_respuestas` = 1 | 15 |
| F02 | Empresa exprés | contract | Supplier `fecha_matricula` (RUES) within 90 days before process publication | 15 |
| F03 | Adiciones excesivas | contract | Money additions ≥ 40% of initial value OR `dias_adicionados` ≥ 50% of initial `duracion` (exact money-addition columns resolved by M2 profiling; SECOP I has explicit addition fields) | 12 |
| F04 | Abuso de contratación directa | entity | Entity's share of value via contratación directa ≥ 2 z-scores above peer group (same entity level + department) | 8 |
| F05 | Fraccionamiento | contract | ≥3 direct contracts, same entity+supplier, same UNSPSC segment, within 90 days, summing > 280 SMMLV (most conservative menor-cuantía bracket; SMMLV table per year in `refs/`) | 12 |
| F06 | Carrusel | contract | Within entity (or municipality×UNSPSC) over rolling 24 months: 2–4 distinct winners, ≥8 competitive processes, each winner share ≥15%, alternation index ≥0.6 → flag member contracts | 12 |
| F07 | Ventana de licitación corta | contract | Days(publication → bid deadline) below per-modality floor (licitación <10, abreviada <5) | 8 |
| F08 | Precio calcado | contract | Awarded value within ±0.5% of `precio_base` in competitive process | 6 |
| F09 | Afán de diciembre | contract | Signed Dec 15–31 | 4 |
| F10 | Ventana electoral | contract | Direct contract signed inside Ley de Garantías restricted windows (static dates table 2018/2019/2022/2023, sourced) | 6 |
| F11 | Proveedor sancionado | contract | Supplier doc in L1/L2/L3/L4 (only sanctions dated *before* signing for scoring; any-date version shown as context) | 20 |
| F12 | Concentración/dependencia | entity | Single supplier captures >50% of entity's annual value (≥5 contracts), or supplier gets >80% of its SECOP revenue from one entity | 8 |
| F13 | Objeto vago | contract | Contract object < 40 chars or top-decile boilerplate similarity | 3 |
| F14 | Valor redondo | contract | Value ≥ 1,000M COP and multiple of 100M | 2 |

Entity/municipality score: value-weighted mean of contract scores + entity-level flags, with **empirical-Bayes shrinkage toward department mean**; entities/municipalities with <10 contracts get an "datos insuficientes" badge instead of a rank.

**Validation (uses the already-identified cases):** labels = suppliers in L1–L4 (sanction date after contract, to avoid leakage) + V1 Monitor Ciudadano cases + V2 landmark cases matched to their SECOP contracts. Report ROC-AUC, precision@k, lift@top-decile, and a per-landmark-case table showing where each fell in the ranking. Target: AUC > 0.60, lift@10% > 1.5, landmark cases in top quartile; one documented weight-iteration allowed if unmet. Results go in `docs/METHODOLOGY.md`.

## Web artifact contract (fixed now so dashboard can build against fixtures)

All under `web/public/data/`, schema-validated in M6, total ≤ 60 MB, each lazy-loaded file ≤ 5 MB:
- `meta.json` — build date, pipeline version, weights, flag definitions (ES), tier thresholds
- `resumen_nacional.json` — KPIs, year×modality series, per-department aggregates (choropleth)
- `departamentos/{DD}.json` — department detail: municipal scores, top entities, series
- `casos_prioritarios/{NNN}.json` — top 2,500 contracts by score, chunks of 500: contract facts, score, tier, fired flags **with evidence values**, `urlproceso` link
- `entidades_top.json`, `proveedores_top.json` — top 300 profiles each
- JSON Schema files + a fixture generator (synthetic mini-dataset) for web development

## Dashboard (Spanish, static, hostable on Vercel/Netlify/GH Pages)

1. **Panorama** — KPI cards (contratos analizados, valor total, casos críticos, % directa), choropleth map of Colombia by department (react-simple-maps + TopoJSON, click → department drill), time series, top entidades/proveedores riesgosos.
2. **Casos prioritarios** — TanStack Table: sort/filter by departamento, municipio, entidad, modalidad, año, nivel de riesgo, tipo de bandera; free-text search; risk-tier color chips; CSV export.
3. **Detalle de caso** — score breakdown showing each fired flag + its evidence numbers, contract facts, supplier history sparkline, **"Ver en SECOP" link** (`urlproceso`) for auditability.
4. **Metodología** — sources (linked to the datasets above), flag definitions, weights, backtest results, limitations, descargo de responsabilidad.

Design: shadcn/ui + Tailwind, Inter, dark-mode aware; risk palette verde `#22c55e` → amarillo `#eab308` → naranja `#f97316` → rojo `#dc2626` (colorblind-safe pairing with icons/patterns, not color alone).

## Milestones (each = one Sonnet subagent task; orchestrator reviews acceptance criteria between them)

| M | Deliverable | Acceptance criteria (checked by orchestrator) |
|---|-------------|-----------------------------------------------|
| M0 | Scaffold: git init, uv project, Vite web scaffold, Makefile, .gitignore, `.env.example`, this plan as `PLAN.md` | `make check` (ruff+pytest) and `npm run build` pass on empty skeleton |
| M1 | Extraction: Socrata client (keyset paging, resume, manifest), pulls S1–S2 full + L1–L4 + E2 + targeted S3/S4/S5 slices; `known_cases.yaml` curated with citations; Monitor Ciudadano download (best-effort manual fallback documented) | Manifest row counts within 1% of live API `count(1)`; kill+resume works; incremental re-pull via `:updated_at` demonstrated on one partition |
| M2 | Canonical marts + cleaning: DuckDB models, NIT/name normalization, dedup, type casts, SMMLV/election/modality ref tables, **column-profiling report that resolves SECOP II money-addition fields**, data-quality report (nulls, quarantine) | DQ report generated; raw→mart row reconciliation documented; edge-case fixtures pass |
| M3 | Flags F01–F14, one module each, unit-tested on synthetic fixtures (known-positive + known-negative per flag) | All tests green; fire-rates within sanity bands (e.g. F01 between 1–15% of competitive processes) |
| M4 | RUES enrichment: chamber-dataset coverage measurement, throttled+cached per-NIT fallback for suppliers of contracts ≥ 200M COP or otherwise-flagged | Coverage % reported; F02 null-handling verified |
| M5 | Scoring + backtest: `weights.yaml`, scorer, entity/muni aggregation with shrinkage, backtest vs L1–L4 + V1 + V2, `docs/METHODOLOGY.md` | AUC/lift/landmark-case table produced; targets met or one documented iteration |
| M6 | Export: artifact builder + JSON-schema validation + fixture generator | All artifacts schema-valid and within size budgets |
| M7 | Dashboard: 4 views, responsive, ES copy, loads real artifacts and fixtures | `npm run build` succeeds; renders with real data (verified via preview screenshot); Lighthouse perf ≥ 85 |
| M8 | Deploy + docs: README runbook (refresh → rebuild → deploy), Vercel/Netlify config + GH Pages workflow, full e2e run | Fresh-clone `make all` → working site, executed once end-to-end |

Parallelism: M3 ∥ M4; M7 may start once M6's fixtures exist. Data pulls (M1) run in background while M2 SQL is developed against a sampled partition. Orchestrator (main session) spawns each milestone as `Agent(model:"sonnet")` with the relevant PLAN.md section, reviews diffs, runs acceptance commands itself, and only then advances — cheap models execute, review gates stay with the orchestrator.

## Verification (end-to-end)

1. `make all` with `--sample` mode (one department, one year) completes in minutes — CI-friendly smoke path.
2. Full run: manifests reconcile with live API counts; DQ report reviewed.
3. Backtest metrics meet targets; each V2 landmark case's rank inspected and explained in METHODOLOGY.md.
4. Spot-audit: 10 random flagged contracts opened via their `urlproceso` links to confirm the underlying data matches SECOP's website (auditability proof).
5. Dashboard: build + preview screenshots of all 4 views with real data; filters/sort/color tiers exercised.

## Risks & mitigations

- **RUES coverage unknown** → tiered fallback (chamber datasets → per-NIT lookups → NULL, excluded from denominator); coverage % published in methodology.
- **SECOP II money-addition columns ambiguous** → M2 profiling resolves empirically; time-based F03 (`dias_adicionados`) works regardless.
- **Socrata throttling / 403s** (SECOP I `xvdy-vvsk` already returns 403) → pinned IDs verified above; app token; backoff; Integrado `rpmr-utcd` as legacy fallback.
- **Label bias** (only caught cases are labeled) → labels used for *validation only*, never training, in v1; stated in methodology.
- **Volume** → column projection, year partitions, resumable pulls, DuckDB.
- **Legal exposure** → risk-not-proof framing, official-source links everywhere, methodology page, no personal data beyond what the State already publishes.
