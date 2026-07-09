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
cp .env.example .env   # modo sample: opcional. modo full: requerido, ver abajo
```

Dos modos, desde la raíz del repo:

```bash
make all                # modo "sample": solo 2023, minutos -- para desarrollo/pruebas
make all MODE=full       # modo "full": historia completa SECOP II -- para producción real
```

`make all` encadena: `pull` (catálogos pequeños + DIVIPOLA + slices SECOP I de casos
emblemáticos + Monitor Ciudadano) → `pull-sample`/`pull-full` (S1/S2) → `marts` (limpieza +
DuckDB) → `rues-coverage` (empresas exprés) → `flags` (F01–F14) → `score` (scoring + backtest)
→ `export` (JSON para el dashboard) → `web` (build de producción).

**`MODE=full` requiere `SOCRATA_APP_TOKEN`** en `pipeline/.env` (`cp pipeline/.env.example
pipeline/.env`, luego pega el token). Sin token, los pulls concurrentes (abajo) competirían por
el mismo límite de frecuencia (bajo, por IP) de Socrata en modo anónimo en vez de ir más rápido,
así que `pipeline.extract.pull` se niega a correr `--full --dataset X` sin token (ver Makefile,
target `pull-full`). Consigue uno gratis en [datos.gov.co](https://www.datos.gov.co) (cuenta →
developer settings; ver también
[dev.socrata.com/docs/app-tokens.html](https://dev.socrata.com/docs/app-tokens.html)).

Con el token, `make all MODE=full` corre **las 6 descargas independientes a la vez** vía
`pull-full-parallel`: los 3 catálogos pequeños (`pull`) concurrentes entre sí, S1+S2+RUES
(`pull-full`) concurrentes entre sí, y ambos grupos concurrentes entre sí -- pensado para una
máquina de desarrollo real (10 núcleos/32GB en la que se probó), no para un runner de CI
compartido. Este proyecto corrió originalmente en GitHub Actions; se migró a ejecución local
(ver sección de automatización abajo) después de que esa concurrencia coincidiera con que el
runner estándar (4 núcleos/16GB) reportara "lost communication with the server" -- sin logs
capturados, nunca se pudo confirmar con certeza si la causa era esa o una falla de
infraestructura de GitHub no relacionada, pero no valía la pena seguir arriesgando corridas de
~90 min para averiguarlo en una máquina con mucho menos margen que la tuya.

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

**Producción real: GitHub Pages, servido desde la rama `gh-pages`, publicada desde esta
máquina** (no hay CI de por medio):

```bash
make web-gh-pages   # build con el base path correcto (.../radar-riesgo-corrupcion-colombia/)
make publish        # construye un git worktree, empuja web/dist/ a la rama gh-pages
```

`make publish` (`scripts/publish_gh_pages.sh`) usa un git worktree desechable para no tocar tu
checkout principal: crea la rama `gh-pages` como huérfana la primera vez, la actualiza en
corridas siguientes, y no hace commit si el build no cambió. Pages está configurado en
Settings → Pages → Source: **Deploy from a branch** (`gh-pages`) -- no hay ningún workflow de
GitHub Actions en este repo.

Esto es exactamente lo que corre `make weekly` (ver la sección de automatización semanal abajo)
al final de su cadena, así que normalmente no necesitas correr `web-gh-pages`/`publish` a mano
salvo para un despliegue puntual.

**Alternativas** (no son la ruta de producción actual, pero `vercel.json`/`netlify.toml` en la
raíz siguen siendo válidos si quieres hostear en otro lado):
```bash
# Vercel
npm i -g vercel && cd web && npm run build && vercel deploy --prebuilt --cwd ..
# Netlify
npm i -g netlify-cli && cd web && npm run build && netlify deploy --prod --dir=dist
```
En ambos casos, `web/public/data/` está en `.gitignore` (pesa varios MB, se regenera con el
pipeline), así que despliega el **build ya generado**, no dejes que la plataforma lo reconstruya
desde el repo (que no tiene los datos reales) -- salvo que quieras que un *preview deploy* por PR
muestre los datos de ejemplo (fixtures) a propósito, para revisar cambios de interfaz sin
depender del pipeline.

## Automatización semanal (launchd, sin CI)

El refresco semanal corre **en esta máquina**, disparado por un LaunchAgent de macOS -- no por
un cron de GitHub Actions. `make weekly` encadena: `pull` + `pull-refresh` (concurrentes entre
sí, ver Makefile) → `marts MODE=full` → `rues-coverage` → `flags` → `score` → `export` →
`web-gh-pages` → `publish`.

El plist en `scripts/` es una plantilla (usa `/Users/YOUR_USERNAME/...` -- sustituido por la ruta
real antes de instalarlo, para no exponer un username local en un repo público). Ya está
instalado en esta máquina: copiado a `~/Library/LaunchAgents/` con la ruta real y cargado con
`launchctl load`. Corre los domingos a las 9:00am hora local. Comandos útiles:

```bash
launchctl list | grep radar-riesgo                                      # confirma que está cargado
launchctl start local.radar-riesgo-corrupcion.weekly                    # dispara una corrida ya, sin esperar al domingo
tail -f ~/Library/Logs/radar-riesgo-corrupcion-colombia/weekly.log       # sigue el log de la última corrida
launchctl unload ~/Library/LaunchAgents/local.radar-riesgo-corrupcion.weekly.plist  # desactiva
```

**Limitación real de launchd, no de este proyecto:** `StartCalendarInterval` no recupera una
corrida perdida si la Mac estaba dormida/apagada a esa hora -- simplemente se salta hasta la
próxima vez que coincida el horario con la máquina despierta. Para mayor confiabilidad, agenda
un despertar automático un poco antes con
`sudo pmset repeat wakeorpoweron MTWRFSU 08:55:00` (opcional).

**Segundo problema relacionado, ya resuelto:** que la Mac esté despierta *al empezar* no basta
-- también tiene que seguir despierta durante toda la corrida (~90 min). Confirmado en vivo
(2026-07-07): el sueño por inactividad a mitad de una corrida deja la conexión HTTPS en curso
colgada varios minutos; el timeout de 30s de httpx no ayuda porque todo el proceso (incluida la
pila de red) está suspendido, no solo lento. Varios de estos cuelgues seguidos agotaron el
presupuesto de reintentos (5 intentos) y la corrida falló ~85 minutos adentro, antes de llegar a
`marts`/`export`/`publish`. Por eso el plist ya envuelve el job en `caffeinate -i -s` (ver
`scripts/local.radar-riesgo-corrupcion.weekly.plist`): mantiene la máquina despierta solo
mientras `make weekly` está corriendo, y suelta la asignación apenas termina (éxito o error) --
no mantiene la Mac despierta en general.

## Estructura del repositorio

```
corruption/
├── PLAN.md                  # arquitectura, fuentes de datos, catálogo de banderas, hitos
├── Makefile                 # pull | marts | rues-coverage | flags | score | export | web | all | check
├── pipeline/                 # Python 3.12+, uv — extracción, limpieza, banderas, scoring, export
├── web/                       # React + TypeScript + Vite + Tailwind — dashboard estático
├── docs/                      # DQ_REPORT.md, PROFILING.md, RUES_COVERAGE.md, METHODOLOGY.md
├── scripts/                   # publish_gh_pages.sh + el plist de launchd (ver runbook)
├── vercel.json / netlify.toml # alternativas de hosting no usadas en producción (ver Desplegar)
```

## Comandos de referencia

```bash
make check      # ruff + pytest (pipeline)
make pull       # catálogos pequeños + DIVIPOLA + slices + Monitor Ciudadano (concurrente)
make pull-sample / make pull-full   # S1+S2, 2023 vs. historia completa (resumible, S1+S2+RUES
                                     #   concurrentes -- pull-full requiere SOCRATA_APP_TOKEN)
make pull-full-parallel             # pull + pull-full, las 6 descargas a la vez (usa `all MODE=full`)
make marts [MODE=full]              # limpieza + DuckDB (default: sample)
make rues-coverage                  # empresa exprés: fecha_matricula + reporte de cobertura
make flags                          # F01–F14
make score                          # scoring + backtest contra casos conocidos
make export                         # JSON del dashboard (web/public/data/)
make web                            # build de desarrollo del dashboard (base path raíz, para `make serve`)
make web-gh-pages                   # build de producción (base path /radar-riesgo-corrupcion-colombia/)
make publish                        # publica web/dist/ a la rama gh-pages
make serve                          # sirve web/dist/ ya construido en http://localhost:4173
make all [MODE=full]                # pipeline completo + build
make all-serve [MODE=full]          # pipeline completo + build + servir localmente
make weekly                         # pull-refresh + rebuild + publish -- lo que corre el LaunchAgent semanal
```

## Aviso legal

Los puntajes de riesgo son **indicadores para priorizar auditoría**, no acusaciones de
responsabilidad. Cada caso mostrado enlaza a su registro público oficial en SECOP. Ver
[docs/METHODOLOGY.md](docs/METHODOLOGY.md) para limitaciones y sesgos conocidos.
