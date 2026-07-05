# Radar de Riesgo de Corrupción — Colombia

Sistema de detección de riesgo de corrupción en contratación pública colombiana,
con dashboard web estático construido sobre datos abiertos del Estado (SECOP, Contraloría,
Procuraduría, RUES, Monitor Ciudadano). Ver [PLAN.md](PLAN.md) para la arquitectura completa,
fuentes de datos, catálogo de banderas de riesgo, y [docs/METHODOLOGY.md](docs/METHODOLOGY.md)
para la metodología de scoring y los resultados de backtest.

## Inicio rápido (dashboard sin correr el pipeline)

El dashboard funciona de inmediato con datos sintéticos de ejemplo — no necesitas correr
el pipeline de Python para ver la interfaz:

```bash
cd web
npm install
npm run dev
```

`npm run dev`/`npm run build` copian automáticamente `web/src/fixtures/` a `web/public/data/`
la primera vez (ver `web/scripts/seed-fixtures.mjs`) — y **nunca sobrescriben datos reales**
si ya corriste el pipeline.

## Runbook completo: refrescar datos → reconstruir → desplegar

Este proyecto es **estático y precomputado** (PLAN.md): no hay backend ni base de datos en
producción. El sitio publicado es HTML/JS/JSON generado una vez y servido tal cual. Refrescar
significa: correr el pipeline de Python (produce los JSON en `web/public/data/`), reconstruir
el sitio (`npm run build`, que empaqueta esos JSON), y desplegar la carpeta `web/dist/` resultante.

### 1. Refrescar datos

```bash
cd pipeline
uv sync --extra dev
cp .env.example .env   # opcional: agrega SOCRATA_APP_TOKEN para límites de frecuencia más altos
```

Dos modos, desde la raíz del repo:

```bash
make all                # modo "sample": solo 2023, minutos -- para desarrollo/pruebas
make all MODE=full       # modo "full": historia completa SECOP II, HORAS -- para producción real
```

`make all` encadena: `pull` (catálogos pequeños + DIVIPOLA + slices SECOP I de casos
emblemáticos + Monitor Ciudadano) → `pull-sample`/`pull-full` (S1/S2) → `marts` (limpieza +
DuckDB) → `rues-coverage` (empresas exprés) → `flags` (F01–F14) → `score` (scoring + backtest)
→ `export` (JSON para el dashboard) → `web` (build de producción).

Cada paso es re-ejecutable independientemente (`make pull-full`, `make marts MODE=full`, etc.)
y los pulls son **resumibles**: si se interrumpen, simplemente vuelve a correr el mismo comando
y continúan desde donde quedaron (ver el manifest en `pipeline/data/raw/manifest.json`).

Verifica el resultado antes de desplegar:

```bash
make check                              # tests + linting del pipeline
cat pipeline/docs/DQ_REPORT.md          # reconciliación de filas, calidad de datos
cat docs/METHODOLOGY.md                 # resultados de backtest contra casos conocidos
```

### 2. Reconstruir el sitio

```bash
cd web
npm run build      # usa web/public/data/ (ya poblado por `make export` arriba)
npm run preview    # sirve dist/ localmente para verificar antes de desplegar
```

### 3. Desplegar

El sitio es 100% estático (`web/dist/`) — cualquier hosting de archivos estáticos sirve.
`web/public/data/` está en `.gitignore` (puede pesar varios MB y se regenera con el pipeline),
así que el flujo recomendado es desplegar el **build ya generado**, no dejar que la plataforma
lo reconstruya desde el repo (que no tiene los datos reales).

**Vercel** (`vercel.json` en la raíz):
```bash
npm i -g vercel
cd web && npm run build
vercel deploy --prebuilt --cwd .. 
```
También puedes conectar el repo por git para *preview deploys* automáticos por PR — como
`web/public/data/` no está en git, esos previews mostrarán los datos de ejemplo (fixtures),
lo cual es intencional y útil para revisar cambios de interfaz sin depender del pipeline.

**Netlify** (`netlify.toml` en la raíz):
```bash
npm i -g netlify-cli
cd web && npm run build
netlify deploy --prod --dir=dist
```

**GitHub Pages**: workflow en `.github/workflows/deploy-gh-pages.yml`, disparo manual
(`workflow_dispatch`) desde la pestaña Actions, con un input `mode` (`sample` o `full`). Corre
el pipeline completo dentro del job — con `mode=full` puede tomar horas; hay un cron
comentado en el workflow para refrescos desatendidos mensuales.

## Estructura del repositorio

```
corruption/
├── PLAN.md                  # arquitectura, fuentes de datos, catálogo de banderas, hitos
├── Makefile                 # pull | marts | rues-coverage | flags | score | export | web | all | check
├── pipeline/                 # Python 3.12+, uv — extracción, limpieza, banderas, scoring, export
├── web/                       # React + TypeScript + Vite + Tailwind — dashboard estático
├── docs/                      # DQ_REPORT.md, PROFILING.md, RUES_COVERAGE.md, METHODOLOGY.md
├── vercel.json / netlify.toml / .github/workflows/deploy-gh-pages.yml
```

## Comandos de referencia

```bash
make check      # ruff + pytest (pipeline)
make pull       # catálogos pequeños + DIVIPOLA + slices + Monitor Ciudadano
make pull-sample / make pull-full   # S1+S2, 2023 vs. historia completa (resumible)
make marts [MODE=full]              # limpieza + DuckDB (default: sample)
make rues-coverage                  # empresa exprés: fecha_matricula + reporte de cobertura
make flags                          # F01–F14
make score                          # scoring + backtest contra casos conocidos
make export                         # JSON del dashboard (web/public/data/)
make web                            # build de producción del dashboard
make all [MODE=full]                # pipeline completo + build
```

## Aviso legal

Los puntajes de riesgo son **indicadores para priorizar auditoría**, no acusaciones de
responsabilidad. Cada caso mostrado enlaza a su registro público oficial en SECOP. Ver
[docs/METHODOLOGY.md](docs/METHODOLOGY.md) para limitaciones y sesgos conocidos.
