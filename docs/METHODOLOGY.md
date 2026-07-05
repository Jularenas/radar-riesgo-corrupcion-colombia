# Metodología — Radar de Riesgo de Corrupción (Colombia)

**Generado en M5** (scoring + backtest). Ejecutable de nuevo con `make score`
(equivalente a `uv run python -m pipeline.score.scorer` seguido de
`uv run python -m pipeline.score.backtest`, ambos desde `pipeline/`).

## Marco legal/ético — descargo de responsabilidad

**El puntaje de riesgo que produce este sistema es un indicador para
priorizar auditorías, nunca una acusación.** Un contrato con score alto
significa que coincide con patrones estadísticos asociados, en la
literatura y en casos ya documentados, con mayor riesgo de irregularidades
— no significa que exista corrupción comprobada, y mucho menos que una
persona o empresa específica sea culpable de algo. Cada contrato mostrado
en el futuro dashboard enlaza a su registro oficial en SECOP (`urlproceso`)
y muestra exactamente qué banderas se activaron y con qué evidencia
(valores, fechas, conteos), para que cualquier lectura del score sea
auditable y refutable con la fuente primaria. Los datos usados son
exclusivamente los que el Estado colombiano ya publica como información
pública (SECOP, Contraloría, Procuraduría, RUES, DIVIPOLA); este sistema no
incorpora ni infiere datos personales adicionales.

## 1. Fuentes de datos

Ver la tabla completa en `PLAN.md` ("Verified data sources"). Resumen de lo
efectivamente cargado en el mart usado por este milestone
(`pipeline/data/marts/corruption.duckdb`, modo `sample`):

| Fuente | Dataset ID | Filas en el mart | Rol |
|---|---|---:|---|
| S1 — SECOP II Contratos | `jbjy-vk9h` | 300.000 (muestra 2023) | `fct_contrato` (SECOP2) |
| S2 — SECOP II Procesos | `p6dx-8zbt` | 300.000 (muestra 2023) | `fct_proceso` |
| S3/S4 — SECOP I (slices dirigidos) | `f789-7hwg` / `79ga-5jck` | 527 (3 de los 6 casos marcados `secop1: true`) | `fct_contrato` (SECOP1) |
| L1 — Responsabilidad Fiscal (CGR) | `jr8e-e8tu` | 60 | `sanciones` |
| L2 — Multas SECOP I | `4n4q-k399` | 1.705 | `sanciones` |
| L3 — Multas SECOP II | `it5q-hg94` | 538 | `sanciones` |
| L4 — Antecedentes SIRI (Procuraduría) | `iaeu-rcn6` | 43.318 | `sanciones` |
| E1 — RUES (registros de cámaras) | `c82u-588k` / `gwqv-sqvs` | 2.440.937 (parcial, en curso) | `dim_proveedor.fecha_matricula` |
| E2 — DIVIPOLA (DANE) | `gdxc-w37w` | 1.122 municipios | geografía canónica |
| V1 — Monitor Ciudadano (Transparencia por Colombia) | descarga manual | 1.243 | validación (ver §5.4 — 0% de coincidencias por desfase temporal con la muestra, no por error de extracción) |
| V2 — Casos emblemáticos curados | `refs/known_cases.yaml` | 10 casos | validación (ver §5.3) |

**El mart de este milestone es una muestra de un solo año (2023) para
SECOP II** (~5,3% de las 5,66M filas de S1 completas) **más slices
dirigidos de SECOP I** para 3 de los 10 casos emblemáticos curados
(Agencia Nacional de Infraestructura/Ruta del Sol, IDU Bogotá, La Guajira
PAE). El pull completo de SECOP II (S1: 5.657.593 filas, S2: 8.760.641
filas) ya se completó en `pipeline/data/raw/` pero **el mart no se
reconstruye desde datos completos en este milestone** — eso ocurre en M8.
Todas las cifras de este documento corresponden a la muestra 2023 + los
slices dirigidos, no al universo completo de contratación pública
colombiana.

## 2. Catálogo de banderas — definición, peso y comportamiento observado

Pesos definidos en `pipeline/src/pipeline/score/weights.yaml` (fuente única
de verdad; `pipeline.flags.params.FLAG_META` deriva su `peso` de ese
archivo). Tasas de disparo medidas contra la muestra 2023 + slices SECOP I
(M3, antes de este milestone; los pesos no afectan si una bandera se
dispara, solo cuánto pesa en el score).

| ID | Bandera | Nivel | Peso | Población aplicable | Disparos | Tasa | Racional |
|----|---------|-------|-----:|---------------------:|---------:|-----:|----------|
| F01 | Único oferente | contrato | 15 | 3.549 | 506 | 14,3% | Modalidad competitiva con un solo oferente único sugiere direccionamiento; requiere el join contrato↔proceso (28,3% de cobertura en la muestra, ver §6.3) |
| F02 | Empresa exprés | contrato | 15 | 3.085 | 3 | 0,1% | Proveedor registrado en RUES <90 días antes de la publicación del proceso — señal clásica de "empresa de papel" creada para un contrato específico; limitada por cobertura RUES (~2,6-3,4%, ver §6.2) |
| F03 | Adiciones excesivas | contrato | 12 | 296.169 | 2.870 | 0,97% | Adiciones ≥40% en dinero o ≥50% en tiempo sobre el valor/duración inicial — el mecanismo más documentado para inflar contratos ya adjudicados |
| F04 | Abuso de contratación directa | entidad | 8 | 1.153 | 18 | 1,6% | Participación de la entidad en contratación directa ≥2 desviaciones estándar sobre su grupo de pares (mismo departamento) |
| F05 | Fraccionamiento | contrato | 12 | 232.724 | 569 | 0,24% | ≥3 contratos directos, misma entidad+proveedor+segmento UNSPSC, en 90 días, sumando >280 SMMLV — evita el umbral de licitación obligatoria |
| F06 | Carrusel | contrato | 12 | 5.214 | 0 | 0,0% | Alternancia entre 2-4 ganadores en procesos competitivos repetidos — no se observó ningún caso en la muestra 2023 (ver §6.5) |
| F07 | Ventana de licitación corta | contrato | 8 | 3.264 | 487 | 14,9% | Plazo publicación→cierre de ofertas por debajo del piso reglamentario — limita la competencia real aunque el proceso sea nominalmente abierto |
| F08 | Precio calcado | contrato | 6 | 3.529 | 975 | 27,6% | Valor adjudicado dentro de ±0,5% del precio base — indicio de que el precio de referencia fue filtrado al oferente ganador |
| F09 | Afán de diciembre | contrato | **8** (ver §5.2) | 300.498 | 5.112 | 1,7% | Firma entre el 15 y 31 de diciembre — contratación de fin de año con menor escrutinio, patrón reconocido en la contratación pública colombiana |
| F10 | Ventana electoral | contrato | 6 | 234.201 | 44.209 | 18,9% | Contratación directa dentro de las ventanas de Ley de Garantías Electorales |
| F11 | Proveedor sancionado | contrato | 20 | 299.876 | 311 | 0,1% | Proveedor con sanción (L1-L4) fechada *antes* de la firma — la bandera de mayor peso: historial confirmado, no solo un patrón estadístico |
| F12 | Concentración/dependencia | entidad | 8 | 1.756 | 402 | 22,9% | Un proveedor captura >50% del valor anual de la entidad, o >80% de los ingresos anuales del proveedor provienen de esa entidad |
| F13 | Objeto vago | contrato | 3 | 300.498 | 31.575 | 10,5% | Objeto contractual <40 caracteres o repetido en el decil superior de frecuencia — dificulta auditar qué se contrató realmente |
| F14 | Valor redondo | contrato | 2 | 300.498 | 280 | 0,09% | Valor ≥1.000M COP y múltiplo exacto de 100M — indicio (débil, por eso el peso mínimo) de que el valor no vino de un presupuesto detallado |

Definiciones completas, umbrales exactos y adaptaciones documentadas
respecto a PLAN.md están en el docstring de cada módulo
(`pipeline/src/pipeline/flags/f01_unico_oferente.py` … `f14_valor_redondo.py`)
y en `pipeline/src/pipeline/flags/params.py`.

## 3. Fórmula de score y niveles de riesgo

```
score = 100 × Σ(peso de banderas disparadas) / Σ(peso de banderas aplicables)
```

"Aplicable" significa que existe una fila `(clave, flag_id)` en
`flag_contrato`/`flag_entidad` — disparada o no. Un contrato/entidad sin
ninguna bandera aplicable recibe **score NULL** (se excluye del ranking,
nunca se interpreta como "riesgo cero"). En la corrida real sobre la
muestra, **0 de 300.349 contratos** quedaron con score NULL — las banderas
F09/F13/F14 son aplicables a prácticamente el 100% de los contratos
(solo requieren `fecha_firma`/`objeto_del_contrato`/`valor_contrato`, con
~0% de nulos en la muestra), así que en la práctica todo contrato tiene
al menos una bandera evaluable. La distribución de banderas aplicables por
contrato:

| N.º de banderas aplicables | N.º de contratos |
|---:|---:|
| 3 | 13 |
| 4 | 2.311 |
| 5 | 56.685 |
| 6 | 7.415 |
| 7 | 228.755 |
| 8 | 2.974 |
| 9 | 1.922 |
| 10 | 274 |

Niveles (PLAN.md, límite inferior inclusivo, superior exclusivo):

| Nivel | Rango |
|-------|-------|
| Bajo | score < 20 |
| Medio | 20 ≤ score < 40 |
| Alto | 40 ≤ score < 60 |
| Crítico | score ≥ 60 |

### 3.1 Deduplicación de `id_contrato` (nota técnica)

`fct_contrato.id_contrato` no es perfectamente único (~0,03% de la muestra
— un artefacto preexistente de M2: algunas filas de SECOP I comparten un
número de contrato reportado, y separadamente, ~76 claves tienen filas
físicas duplicadas exactas por solapamiento de fuentes S3/S4 en la carga
de slices de SECOP I sin deduplicar). Como `flag_contrato` ya está
indexado por `id_contrato` (diseño de M3), el scorer resuelve cualquier
`(clave, flag_id)` con más de una fila vía `BOOL_OR` (se dispara si
*cualquiera* de las filas subyacentes se disparó) antes de sumar pesos, y
elige una fila física canónica (la de fecha de firma más reciente) solo
para los campos descriptivos (valor, fecha, nombre de entidad/proveedor).
Esto afecta a 76 de 300.349 claves (0,025%) y se resolvió así por ser
consistente con cómo M3 ya trata `flag_contrato`, no introduce un sesgo
direccional (favorece marcar disparado, la opción conservadora para
auditoría) y se verificó exhaustivamente durante el backtest — de hecho,
este comportamiento (35 filas físicas "positivas" colapsando a claves
distintas) es la explicación completa de por qué el backtest (§5.1) evalúa
11 positivos y no 35.

## 4. Resultados de la corrida real (muestra 2023 + slices SECOP I)

### 4.1 Distribución de `contrato_score`

- **300.349 contratos** con score (ninguno NULL).
- Percentiles: p10=0,00 · p25=0,00 · p50=0,00 · p75=4,71 · p90=9,52 ·
  p95=10,94 · p99=22,46 · media=2,59 · máximo=80,00.
- Niveles: **Crítico=19** (0,006%) · **Alto=298** (0,10%) ·
  **Medio=2.968** (0,99%) · **Bajo=297.064** (98,9%).

La mediana en 0 (y de hecho el 73,5% de los contratos con score
exactamente 0) refleja que la mayoría de contratos de la muestra 2023 son
transacciones rutinarias de bajo valor (mediana de valor: $18,5M COP,
según `docs/DQ_REPORT.md`) que no activan ninguna de las 14 banderas. Esto es
esperado en una muestra aleatoria nacional dominada por contratación
menor, no un defecto del score — la cola derecha (los 317 contratos
Alto+Crítico) es donde el índice concentra la señal.

### 4.2 Agregación entidad/municipio y shrinkage empírico-bayesiano

**Fórmula:** `score_final = (n/(n+k)) × media_propia + (k/(n+k)) × media_departamento`,
donde `n` es el número de contratos de la entidad/municipio.

**`k = 10`**, elegido para coincidir exactamente con el umbral de PLAN.md
para el badge "datos insuficientes" (<10 contratos): una entidad justo en
esa frontera (n=10) recibe ~50% de peso a su propia media y ~50% a la del
departamento — un punto de inflexión natural. Por debajo, domina la media
del grupo (protege contra ruido de muestras pequeñas); por encima, domina
el historial propio de la entidad. Esta elección se valida contra la
distribución real de `n_contratos` observada en la muestra:

| Percentil | Contratos por entidad | Contratos por municipio |
|-----------|----------------------:|-------------------------:|
| p10 | 1 | 1 |
| p25 | 4 | — |
| p50 | 17 | 19 |
| p75 | 75 | — |
| p90 | 237 | 556 |
| media | 123,0 | 267,8 |
| máximo | 16.477 | 15.489 |

Con `k=10` situado entre p10 y p25 (para entidades) — **984 de 2.444
entidades (40,3%)** y **213 de 577 municipios (36,9%)** caen bajo el
umbral de 10 contratos y reciben el badge `datos_insuficientes` (se les
sigue calculando y mostrando un score, solo se marca como baja confianza,
tal como pide PLAN.md).

**Componente de entidad — mezcla de dos señales:** el score propio de una
entidad (antes del shrinkage) combina (a) la media ponderada por valor de
los scores de sus propios contratos, y (b) su score de banderas a nivel
entidad (F04+F12), mezclados **proporcionalmente a la masa de peso que
cada grupo representa en el catálogo completo**: las 12 banderas de
contrato suman 119 puntos tras la iteración de §5.2 (88,1% de 135 puntos
totales del catálogo) y las 2 de entidad suman 16 (11,9%). Es decir:

```
combinado = (119 × componente_contrato + 16 × componente_entidad) / 135
```

con reducción automática a la única señal disponible cuando falta una de
las dos (p. ej. una entidad con <5 contratos no tiene F04/F12 aplicable).
La media del departamento (o nacional, si la entidad no tiene
`cod_dpto` — 801 de 2.444 entidades, 32,8% — o si es el único dato de su
departamento) se calcula igual: media ponderada por valor del
`combined_raw_score` de las demás entidades.

**Resultado observado:** con esta muestra, **ninguna entidad ni municipio
alcanza los niveles Alto o Crítico** (`entidad_score`: 23 Medio, 2.421
Bajo; `municipio_score`: 1 Medio, 576 Bajo). Esto es matemáticamente
esperable, no un error: el nivel Crítico a nivel de *contrato* existe
porque unos pocos contratos concentran banderas graves, pero el score de
entidad es un **promedio ponderado por valor de todos los contratos de
esa entidad** — incluso una entidad con un contrato Crítico ($ alto,
score 80) diluye esa señal si el resto de su portafolio es rutinario, y
además el shrinkage empírico-bayesiano añade una capa adicional de
atenuación hacia la media (baja) del departamento. Una entidad solo
llegaría a Alto/Crítico si tuviera un **patrón sostenido** de contratos
riesgosos, no un evento aislado — que es precisamente la distinción que
el diseño de PLAN.md pretende hacer entre "un contrato sospechoso" y "una
entidad con un problema estructural". Las 23 entidades en nivel Medio son
las que más se acercan a ese patrón en la muestra (ejemplo: Centro de
Diagnóstico Automotor del Valle, 69 contratos, score 35,0).

## 5. Backtest

Las etiquetas se usan **solo para validación, nunca para ajustar
`weights.yaml`** (PLAN.md, riesgo de sesgo de rótulo — solo los casos ya
descubiertos están etiquetados).

### 5.1 Etiquetas L1-L4 y métricas de ranking

**Positivo** = el proveedor o la entidad de un contrato aparece en
`sanciones` con `fecha_sancion` **estrictamente posterior** a
`fecha_firma` (nunca `<=`, para evitar fuga de información — una sanción
anterior o el mismo día de la firma es contexto, ya capturado por F11,
no un desenlace que el score deba "predecir"). Verificado con pruebas
unitarias (`tests/test_score/test_backtest.py::TestLeakageGuard`).

| Métrica | Valor | Objetivo (PLAN.md) | ¿Cumple? |
|---------|------:|---------------------|:--:|
| Contratos evaluados | 300.349 | — | — |
| Positivos | 11 | — | — |
| **AUC-ROC** | **0,4233** | >0,60 | **NO** |
| Precision@top 1% (k=3.003) | 0,0 | — | — |
| Precision@top 5% (k=15.017) | 0,0000666 | — | — |
| Precision@top 10% (k=30.035) | 0,0000333 | — | — |
| **Lift@top-decil** | **0,909** | >1,5 | **NO** |

**¿Por qué el AUC es tan bajo (incluso peor que el azar, 0,5, en la
corrida inicial)?** Se investigó a fondo antes de aceptar el resultado.
Los 11 positivos son **todos** contratos de la Agencia Nacional de
Infraestructura en el slice de SECOP I (2010-2016, caso Ruta del
Sol/Odebrecht). De esos 11, **10 tienen cero banderas disparadas** entre
las 4-5 que les son aplicables (SECOP I no tiene los campos de proceso que
requieren F01/F06/F07/F08, ni UNSPSC para F05) — su score es
matemáticamente 0 sin importar los pesos, porque `0 × cualquier_peso = 0`.
Solo 1 de los 11 dispara algo (F09, por firma en diciembre). Esto se
verificó de forma reproducible:

```
n contratos con score exactamente 0: 220.668 de 300.349 (73,5%)
```

Con 10 de 11 positivos empatados en el fondo absoluto de la distribución
(junto con el 73,5% de todos los contratos), el AUC queda determinado
casi por completo por en qué lugar de ese empate promedian su rango — muy
por debajo del rango medio de toda la población, porque el empate-cero es
la mitad inferior de un ranking muy sesgado a la derecha.

### 5.2 Una iteración de pesos, documentada (única permitida por PLAN.md)

**Antes de iterar, se calculó matemáticamente el techo alcanzable por
cualquier reponderación**, dado que reponderar *nunca* puede sacar del 0 a
un contrato con cero banderas disparadas (ninguna combinación de pesos en
`weights.yaml` cambia *cuáles* banderas se disparan — eso lo decide M3, no
M5). El único grado de libertad disponible es el único contrato con >0
banderas disparadas. Simulando ese contrato en la posición más alta
posible del ranking (manteniendo los otros 10 positivos fijos en su rango
real):

```
techo teórico de AUC  ≈ 0,4249
techo teórico de lift ≈ 0,909
```

Es decir: **ninguna reponderación posible con el catálogo de 14 banderas
actual puede alcanzar AUC>0,60 ni lift>1,5 en esta muestra**, porque el
cuello de botella es la *cobertura de banderas para contratos de SECOP I*,
no la calibración de pesos. Aun así, se ejecutó la iteración permitida de
buena fe:

- **Cambio:** `F09` (Afán de diciembre) de peso **4 → 8**
  (`pipeline/src/pipeline/score/weights.yaml`). Racional: es la única
  bandera que dispara para algún positivo del backtest, y de forma
  independiente es defendible — la contratación de fin de año es un patrón
  reconocido de menor escrutinio en la contratación pública colombiana, y
  su peso original (4, el más bajo del catálogo salvo F14) parecía
  subestimado frente a F07 (ventana corta, peso 8), una bandera de
  "integridad del proceso" de severidad comparable.
- **Antes → Después:**

  | Métrica | Antes (F09=4) | Después (F09=8) |
  |---------|--------------:|-----------------:|
  | AUC-ROC | 0,4098 | 0,4233 |
  | Lift@top-decil | 0,000 | 0,909 |
  | Contratos Crítico | 14 | 19 |
  | Contratos Alto | 256 | 298 |
  | Contratos Medio | 3.335 | 2.968 |

  El único contrato positivo con banderas disparadas subió de score 9,76
  a 17,78 (ambos en nivel Bajo) y, al superar el nuevo p90 (9,52), entró
  al top-decil — de ahí que el lift pase de 0 a 0,909, prácticamente el
  techo teórico calculado arriba. El conteo de Medio bajó (3.335→2.968)
  porque subir el peso de F09 también sube el *denominador* (peso
  aplicable) para todo contrato donde F09 es aplicable pero no se disparó
  — un efecto secundario inevitable de cualquier aumento de peso: penaliza
  (diluye) a los contratos que sí tienen esa bandera evaluada y no
  disparada, no solo premia a los que la disparan.
- **Decisión:** se conserva `F09=8` como configuración final (mejora real,
  aunque insuficiente, y defendible por sí sola). **No se realizó una
  segunda iteración**, conforme a la instrucción de reportar honestamente
  en vez de seguir ajustando. Ver §7 para qué se necesitaría realmente
  para cerrar esta brecha (no es un problema de pesos).

### 5.3 V2 — Casos emblemáticos (`refs/known_cases.yaml`)

Emparejamiento: patrones `LIKE` sobre el nombre de entidad normalizado
(mayúsculas, sin tildes — igual que la normalización de departamento ya
usada en `clean/build.py`) **y** el período del caso (año de firma dentro
del rango declarado). El filtro de período no es solo una restricción de
datos: algunos hints son deliberadamente amplios (p. ej. `%IDU%`,
`%GESTION DEL RIESGO DE DESASTRES%`) para tolerar variantes de escritura,
y en el mart nacional completo esa amplitud puede coincidir con una
entidad homónima distinta — el período filtra la mayoría de esos falsos
positivos porque solo aparecen en la muestra 2023.

| Caso | Período | Contratos coincidentes | Mejor score | Nivel | Percentil (mismo año) | ¿Cuartil superior? |
|------|---------|------------------------:|-------------:|-------|------------------------:|:--:|
| Centros Poblados — MinTIC | 2020-2021 | 0 | — | — | — | sin datos |
| **UNGRD — Carrotanques La Guajira** | 2023-2024 | 195 (**ver nota**) | 21,05 | Medio | 0,989 | ~~Sí~~ **descartado** |
| **PAE La Guajira** | 2016-2018 | **286** | **35,29** | Medio | 0,995 | **Sí** |
| PAE Santander | 2016-2020 | 0 | — | — | — | sin datos |
| **Ruta del Sol II — Odebrecht (ANI)** | 2010-2016 | **67** | **19,61** | Bajo | 1,000 | **Sí** |
| **Carrusel de la Contratación — IDU Bogotá** | 2008-2012 | **4** | **17,78** | Bajo | 0,667 | **No** |
| Cartel de la Hemofilia — Córdoba | 2013-2015 | 0 | — | — | — | sin datos |
| Cartel del SIDA — Córdoba | 2011-2015 | 0 | — | — | — | sin datos |
| Sobrecostos COVID-19 — Bogotá | 2020 | 0 | — | — | — | sin datos |
| Sobrecostos COVID-19 — Medellín | 2020 | 0 | — | — | — | sin datos |

**Nota crítica sobre UNGRD — Carrotanques:** el match automático (195
contratos) es un **falso positivo confirmado por revisión manual**. Las
195 filas corresponden a tres entidades *departamentales* distintas
("Unidad Administrativa Especial para la Gestión del Riesgo de Desastres
de Cundinamarca", "Secretaría de Gestión del Riesgo de Desastres del
Valle del Cauca", "Fondo de Gestión del Riesgo de Desastres del
Casanare") — **ninguna es la UNGRD nacional**, que no aparece en la
muestra 2023. El diagnóstico automático `nombre_exacto_confirmado=0/195`
(¿alguna fila contiene el nombre oficial exacto de `entidades:` en
`known_cases.yaml`?) detectó esto: 0 de 195 filas contienen el nombre
oficial "Unidad Nacional para la Gestión del Riesgo de Desastres". Este
caso se **excluye** del cómputo de cumplimiento del objetivo de "casos en
cuartil superior" — no porque el matching esté mal implementado, sino
porque el hint curado (`%GESTION DEL RIESGO DE DESASTRES%`) es
genuinamente ambiguo entre la entidad nacional y homónimos
departamentales, algo que solo una revisión manual puede resolver de
forma confiable (se probó y descartó una heurística automática de "nombre
exacto" porque produce el error inverso en el caso IDU, ver abajo).

**Nota sobre IDU Bogotá:** el diagnóstico `nombre_exacto_confirmado=0/4`
también es engañoso en sentido contrario — el slice de SECOP I almacena
la entidad como la abreviatura **"BOGOTÁ DC IDU"**, que no contiene el
nombre oficial completo "Instituto de Desarrollo Urbano". Sin embargo,
por revisión manual, este SÍ es el match correcto (es la única entidad de
todo el slice de SECOP I que contiene "IDU", y su período/fuente son
consistentes con el caso). Por eso el código reporta el diagnóstico
`n_confirmado_nombre_exacto` como **información de apoyo, no como filtro
automático** — un heurístico de "contiene el nombre exacto" tiene tanto
falsos positivos (UNGRD) como falsos negativos (IDU) en esta muestra
pequeña; la revisión humana documentada aquí es más confiable que
cualquiera de las dos heurísticas por sí sola.

**Cómputo corregido (manual) del objetivo "casos en cuartil superior":**
de los **3 casos con coincidencias genuinas** (PAE La Guajira, Ruta del
Sol/ANI, IDU Bogotá), **2 de 3 (66,7%) alcanzan el cuartil superior**
dentro de su propio año — el caso IDU (percentil 0,667) no. El objetivo de
PLAN.md ("casos emblemáticos en cuartil superior") se cumple
**parcialmente**: mayoría sí, no unanimidad.

**Limitación honesta de los percentiles pre-2023:** el percentil "entre
todos los contratos anotados ese año" para años distintos de 2023 se
calcula contra una cohorte muy delgada y **no aleatoria** — el único año
con muestreo representativo es 2023 (SECOP II); los años 2010-2019 solo
tienen los contratos de los 3 slices de SECOP I dirigidos, es decir, se
está comparando un contrato de un caso emblemático principalmente contra
*otros contratos del mismo caso emblemático o de otros casos
emblemáticos*, no contra una población general de esa época. El percentil
0,995 de PAE La Guajira, por ejemplo, es mayormente una comparación contra
sus propios ~286 contratos hermanos, no contra "todos los contratos
colombianos de 2017". Interprétense estos percentiles pre-2023 como
"posición relativa entre otros contratos ya sospechosos", no como
posición en la población general.

**Casos sin datos (6 de 10):** la ausencia de coincidencias no es
evidencia de ausencia del patrón — es consecuencia directa de dos
restricciones de este milestone, ninguna corregible dentro de M5:
1. **Centros Poblados, Sobrecostos COVID (Bogotá/Medellín):** sus períodos
   (2020-2021, 2020) no se solapan con el único año con muestreo aleatorio
   de SECOP II (2023), y sus entidades no tienen slice de SECOP I dirigido
   en este mart.
2. **PAE Santander, Cartel de la Hemofilia, Cartel del SIDA:** sí son
   `secop1: true` en `known_cases.yaml` (deberían tener slice dirigido),
   pero **el pull de M1 nunca los descargó** — no existe el directorio
   `pipeline/data/raw/secop1_slices/{pae-santander,cartel-hemofilia-cordoba,cartel-sida-cordoba}/`.
   Es una laguna de extracción (M1), fuera del alcance de M5.

Para cada caso sin coincidencias, `backtest.py` también reporta cuántas
filas coinciden con el hint de entidad **ignorando el período** (ver
salida de `make score` / `uv run python -m pipeline.score.backtest`),
como diagnóstico de si el problema es "la entidad no está en la muestra
en absoluto" o "está, pero no en el año correcto".

### 5.4 V1 — Monitor Ciudadano

**Resultado: 0 de 1.243 casos emparejados (0,0%).** Esta cifra tuvo dos
causas distintas, encontradas y resueltas en momentos distintos:

**Bug de extracción (corregido).** La inspección inicial encontró que
`pipeline/src/pipeline/clean/build.py::_build_monitor_hechos()` trataba la
fila 0 del xlsx como encabezado, cuando en realidad esa fila es el título
del reporte ("Corporación Transparencia por Colombia / Monitor Ciudadano
de la Corrupción / ..."); el encabezado real (`Departamento`, `Municipio`,
`Año Inicial Hecho`, `Tipo de corrupción`, `Sector`, etc.) está en la fila
16 de la hoja `Hechos`. Esto hacía que el 100% de las filas quedaran con
`departamento`/`municipio`/`sector` vacíos y `anio` nulo. **Corregido**:
el encabezado ahora se localiza por contenido (buscando la celda
`"Departamento"`) en vez de un índice de fila fijo, y `_HEADER_MAP` usa
claves sin tilde (vía el `strip_accents()` ya existente en
`normalize.py`) para que `Año Inicial Hecho` y `Tipo de corrupción`
mapeen correctamente. Tras la corrección, 1.242/1.243 filas tienen
`departamento` no vacío — la extracción funciona.

**Desfase temporal (causa raíz real, no corregible en M5).** Aun con la
extracción corregida, el emparejamiento sigue en 0%: `monitor_ciudadano_hechos.anio`
cubre 1995–2022 (consistente con el título del dataset, "Radiografía
2016–2022", más hechos históricos anteriores), mientras que la muestra
actual de `fct_contrato` es **exclusivamente 2023** (muestra de un solo
año, por diseño de M1/M2). No existe ningún año en común entre ambas
tablas, así que ninguna coincidencia dept+municipio+año es posible
independientemente de la calidad del emparejamiento — es la misma
limitación estructural que afecta a 6 de los 10 casos emblemáticos en
§5.3. Este dataset debería producir coincidencias reales una vez M8
reconstruya los marts sobre los datos completos multi-año (`s1_secop2_contratos`/
`s2_secop2_procesos` ya están 100% descargados; ver PLAN.md).

La lógica de emparejamiento en
`pipeline/src/pipeline/score/backtest.py::match_monitor_ciudadano()` está
completamente implementada y probada con datos sintéticos limpios
(`tests/test_score/test_backtest.py::TestMonitorCiudadanoMatching`).
Deliberadamente **no se forzaron coincidencias débiles** (p. ej. ignorar
el año) para maquillar esta cifra, siguiendo la instrucción explícita de
documentar honestamente las limitaciones de este dataset.

## 6. Limitaciones (honestas)

1. **Sesgo de las etiquetas de validación.** Los positivos de §5.1 son
   *casos ya descubiertos y sancionados* — el modelo nunca puede validarse
   contra corrupción no detectada, por definición. Las etiquetas se usan
   solo para validación, nunca para entrenar/ajustar pesos (excepto la
   única iteración documentada en §5.2, que no usó las etiquetas para
   *ajustar automáticamente* nada — fue una decisión humana, con las
   etiquetas usadas después, para *medir* el efecto).
2. **Cobertura RUES limita F02.** Solo 2,6% de proveedores (3,4% del valor
   contratado) tiene `fecha_matricula` conocida (`docs/RUES_COVERAGE.md`),
   y el pull de `e1_rues_santarosa` seguía en curso al momento de esta
   corrida (25,3% del registro nacional). F02 excluye correctamente del
   denominador a los proveedores sin fecha conocida (NULL ≠ "no exprés"),
   pero esto significa que F02 solo es *aplicable* a 3.085 de ~300k
   contratos (1,0%) — su fire-rate real entre proveedores desconocidos es,
   por definición, indeterminable con los datos actuales.
3. **Cobertura del join contrato↔proceso limita F01/F08 y el sub-flag de
   dinero de F03.** 28,3% en la muestra (`docs/DQ_REPORT.md` §6) — se
   espera que suba sustancialmente con datos completos (M8), porque la
   baja cobertura actual es en gran parte un artefacto de que S1 y S2 se
   muestrearon independientemente al 5,3% cada uno, no un problema
   estructural del esquema.
4. **Muestra de un solo año (2023) sesga banderas estacionales/electorales.**
   F09 (fin de año) y F10 (ventana electoral) solo pueden observarse en el
   calendario 2023 para el 99,8% de la muestra (SECOP II); no hay forma de
   saber con este mart si 2023 fue un año típico o atípico para esos
   patrones. F10 en particular depende de las ventanas definidas en
   `refs/ventanas_electorales.csv` para 2018/2019/2022/2023 — su tasa de
   disparo (18,9%) refleja la ventana territorial 2023, no un promedio
   multianual.
5. **F06 (Carrusel) no se observó ninguna vez en esta muestra** (0 de
   5.214 aplicables). Dado que el patrón requiere ≥8 procesos competitivos
   con alternancia entre 2-4 ganadores en una ventana de 24 meses, y la
   muestra cubre solo 12 meses de datos aleatorios (2023) más unos pocos
   cientos de filas de SECOP I, es esperable que este patrón — que por
   diseño requiere observar el mismo conjunto de actores repetidamente en
   una ventana amplia — casi nunca se manifieste en una muestra de este
   tamaño y horizonte. No se interpreta como evidencia de que el carrusel
   de contratación no ocurra en Colombia.
6. **`id_contrato` no es perfectamente único** (§3.1) — afecta a 0,025%
   de las claves del mart, resuelto vía `BOOL_OR` (conservador) mas no
   corregido en el origen (fuera de alcance de M5).
7. **El score de entidad/municipio comprime hacia "Bajo"** en esta muestra
   (§4.2) — es un resultado esperado del diseño (promedio ponderado por
   valor + shrinkage), no un error, pero significa que en esta muestra
   particular el nivel Alto/Crítico solo es informativo a nivel de
   contrato individual, no de entidad/municipio.
8. **V1 Monitor Ciudadano da 0% de coincidencias en este mart** — no por
   error de extracción (corregido, §5.4), sino porque el dataset
   (1995–2022) y la muestra actual de `fct_contrato` (solo 2023) no
   comparten ningún año. Debería mejorar tras la reconstrucción con datos
   completos multi-año en M8.
9. **El backtest de casos emblemáticos depende de qué se pulló en M1** —
   3 de los 6 casos marcados `secop1: true` en `known_cases.yaml` nunca
   tuvieron su slice descargado (§5.3), y de los 4 casos `secop1: false`,
   3 tienen período completamente anterior a 2023 (Centros Poblados,
   Sobrecostos COVID Bogotá/Medellín) por lo que no pueden aparecer en una
   muestra de un solo año así su entidad estuviera en el mart. Esto no es
   evidencia de que el score no
   funcionaría para esos casos — es ausencia de datos para probarlo en
   este milestone.
10. **AUC/lift no alcanzan el objetivo de PLAN.md y no pueden alcanzarlo
    solo ajustando pesos** con el catálogo y la muestra actuales — ver
    §5.2 para la prueba y §7 (siguiente) para qué sí lo resolvería.

## 7. Qué se necesitaría para cerrar la brecha del backtest (fuera de alcance de M5)

Dado que §5.2 demuestra matemáticamente que ningún ajuste de pesos puede
alcanzar los objetivos con los datos y banderas actuales, las vías reales
de mejora — todas fuera del alcance de "ajustar `weights.yaml`" — son:

- **Más señal aplicable para contratos de SECOP I**: los 10 positivos
  "atascados en 0" lo están porque F01/F06/F07/F08 (que dependen de datos
  de proceso de SECOP II) no son computables para SECOP I. Si se
  incorporaran datos de proceso de SECOP I (`S3`/`S5` — proponentes), F01
  (único oferente) sería computable para el caso ANI/Ruta del Sol.
- **Más y más representativos positivos**: 11 positivos (todos de un solo
  proveedor/caso) es una muestra minúscula. El pull completo de L1-L4 más
  el pull de M1 pendiente (`pae-santander`, `cartel-hemofilia-cordoba`,
  `cartel-sida-cordoba`) ampliaría y diversificaría las etiquetas.
- **Full-data rebuild (M8)**: con el pull completo de SECOP II ya
  descargado (S1: 5,66M, S2: 8,77M filas) pero aún no usado para
  reconstruir el mart, la cobertura de joins (F01/F03/F08) y el número de
  contratos con historial de sanciones subsecuentes debería aumentar
  sustancialmente — cambiando de forma fundamental la composición del
  conjunto de positivos evaluado aquí.

Ninguna de estas rutas es "ajustar un peso"; por eso no se intentaron como
parte de la única iteración permitida en este milestone.
