# Radar de Riesgo de Corrupción — Colombia

Sistema de detección de riesgo de corrupción en contratación pública colombiana,
con dashboard web estático construido sobre datos abiertos del Estado (SECOP, Contraloría,
Procuraduría).

## Inicio rápido

### Pipeline (Python)

```bash
cd pipeline
uv sync --extra dev   # instala dependencias + dev tools
uv run pytest -q      # corre smoke tests
uv run ruff check .   # linting
```

O desde la raíz:

```bash
make check
```

### Web (React + Vite + Tailwind)

```bash
cd web
npm install
npm run build
```

O desde la raíz:

```bash
make web
```

## Configuración

Copia `pipeline/.env.example` a `pipeline/.env` y añade tu token de Socrata (opcional;
aumenta los límites de frecuencia de la API):

```bash
cp pipeline/.env.example pipeline/.env
```

## Documentación

Ver [PLAN.md](PLAN.md) para la arquitectura completa, fuentes de datos, catálogo de
banderas de riesgo e hitos de implementación.
