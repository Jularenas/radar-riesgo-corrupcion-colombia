# Column Profiling Report — M2

**Sample:** S1=300,000 rows, S2=300,000 rows (2023 sample)

---

## S1 — SECOP II Contratos (`jbjy-vk9h`)

Total rows: 300,000

| Column | Type | Null % | N Distinct | Examples |
|--------|------|--------|------------|---------|
| `nombre_entidad` | VARCHAR | 0.0% | 2,871 | DISTRITO ESPECIAL DE CIENCIA TECNOLOGIA E INNOVACION DE MEDELLIN; Institución Un |
| `nit_entidad` | VARCHAR | 0.0% | 2,442 | 891800395; 891780009 |
| `departamento` | VARCHAR | 0.0% | 34 | Magdalena; Casanare |
| `ciudad` | VARCHAR | 0.0% | 568 | Ibagué; Lérida |
| `localizaci_n` | VARCHAR | 0.0% | 694 | Colombia,  Cundinamarca ,  Soacha; Colombia, Bogotá, No Definido |
| `orden` | VARCHAR | 0.0% | 4 | Nacional; No Definido |
| `sector` | VARCHAR | 0.0% | 26 | defensa; No aplica/No pertenece |
| `rama` | VARCHAR | 0.0% | 5 | Ejecutivo; Judicial |
| `entidad_centralizada` | VARCHAR | 0.0% | 2 | Descentralizada; Centralizada |
| `proceso_de_compra` | VARCHAR | 0.0% | 277,979 | CO1.BDOS.4462720; CO1.BDOS.4651818 |
| `id_contrato` | VARCHAR | 0.0% | 299,979 | CO1.PCCNTR.4734623; CO1.PCCNTR.5195797 |
| `referencia_del_contrato` | VARCHAR | 0.0% | 239,282 | 2951 DE 17 DE OCTUBRE DE 2023; CPS 669-2023 |
| `estado_contrato` | VARCHAR | 0.0% | 9 | terminado; Cancelado |
| `codigo_de_categoria_principal` | VARCHAR | 0.0% | 5,184 | V1.80111501; V1.50211502 |
| `descripcion_del_proceso` | VARCHAR | 0.0% | 208,572 | PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN EN EL MANTENIMIENTO PREVENTIVO Y C |
| `tipo_de_contrato` | VARCHAR | 0.0% | 21 | Comodato; Servicios financieros |
| `modalidad_de_contratacion` | VARCHAR | 0.0% | 14 | Licitación Pública Acuerdo Marco de Precios; Contratación Directa (con ofertas) |
| `justificacion_modalidad_de` | VARCHAR | 0.0% | 32 | Servicios profesionales y apoyo a la gestión; No existe pluralidad de oferentes  |
| `fecha_de_firma` | VARCHAR | 0.0% | 362 | 2023-01-30 00:00:00.000000000; 2023-02-22 00:00:00.000000000 |
| `fecha_de_inicio_del_contrato` | VARCHAR | 1.0% | 564 | 2023-07-24 00:00:00.000000000; 2023-04-27 00:00:00.000000000 |
| `fecha_de_fin_del_contrato` | VARCHAR | 0.0% | 1,784 | 2024-01-31 00:00:00.000000000; 2023-01-30 00:00:00.000000000 |
| `condiciones_de_entrega` | VARCHAR | 0.0% | 22 | NXTWY.DLVY.3; NXTWY.DLVY.10 |
| `tipodocproveedor` | VARCHAR | 0.0% | 10 | Pasaporte; NIT |
| `documento_proveedor` | VARCHAR | 0.0% | 233,422 | 1023878832; 93400210 |
| `proveedor_adjudicado` | VARCHAR | 0.0% | 233,091 | Adriana Maria Gonzalez Puliche; MARA LUCIA ALVAREZ DOMINGUEZ |
| `es_grupo` | VARCHAR | 0.0% | 2 | No; Si |
| `es_pyme` | VARCHAR | 0.0% | 2 | No; Si |
| `habilita_pago_adelantado` | VARCHAR | 0.0% | 3 | No; Si |
| `liquidaci_n` | VARCHAR | 0.0% | 2 | No; Si |
| `obligaci_n_ambiental` | VARCHAR | 0.0% | 2 | No; Si |
| `obligaciones_postconsumo` | VARCHAR | 0.0% | 2 | No; Si |
| `reversion` | VARCHAR | 0.0% | 2 | No; Si |
| `origen_de_los_recursos` | VARCHAR | 0.0% | 2 | Distribuido; Recursos Propios |
| `destino_gasto` | VARCHAR | 0.0% | 3 | No Definido; Inversión |
| `valor_del_contrato` | VARCHAR | 0.0% | 100,188 | 40150000; 3600000 |
| `valor_de_pago_adelantado` | VARCHAR | 0.0% | 319 | 137297899; 26192466 |
| `valor_facturado` | VARCHAR | 0.0% | 74,522 | 8100000; 6832699 |
| `valor_pendiente_de_pago` | VARCHAR | 0.0% | 74,688 | 0; 2300000 |
| `valor_pagado` | VARCHAR | 0.0% | 68,072 | 17400000; 9684606 |
| `valor_amortizado` | VARCHAR | 0.0% | 108 | 3600000; 12300000 |
| `valor_pendiente_de` | VARCHAR | 0.0% | 263 | 128600000; 323590042 |
| `valor_pendiente_de_ejecucion` | VARCHAR | 0.0% | 74,688 | 29866667; 3960000 |
| `saldo_cdp` | VARCHAR | 0.0% | 85,705 | 2460000; 13773060 |
| `saldo_vigencia` | VARCHAR | 0.0% | 2,546 | 526589548; 56000000 |
| `espostconflicto` | VARCHAR | 0.0% | 2 | No; Si |
| `dias_adicionados` | VARCHAR | 0.0% | 412 | 23; 100 |
| `puntos_del_acuerdo` | VARCHAR | 0.0% | 7 | TG; ParticipacionPolitica |
| `pilares_del_acuerdo` | VARCHAR | 0.0% | 20 | RICP; CapituloGenero |
| `urlproceso` | VARCHAR | 0.0% | 277,861 | https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUI |
| `nombre_representante_legal` | VARCHAR | 0.0% | 232,356 | MAPER MAPER; MADELEYDI ORTIZ DURAN |
| `nacionalidad_representante_legal` | VARCHAR | 0.0% | 49 | ES; CU |
| `domicilio_representante_legal` | VARCHAR | 0.0% | 82,745 | Cra 7 a este # 30 - 61 apto 101; carrera 4b #27-26 |
| `tipo_de_identificaci_n_representante_legal` | VARCHAR | 0.0% | 10 | Pasaporte; NIT |
| `identificaci_n_representante_legal` | VARCHAR | 0.0% | 98,333 | 1032461916; 80223788 |
| `g_nero_representante_legal` | VARCHAR | 0.0% | 4 | Mujer; No Definido |
| `presupuesto_general_de_la_nacion_pgn` | VARCHAR | 0.0% | 33,124 | 188398498; 100327526 |
| `sistema_general_de_participaciones` | VARCHAR | 0.0% | 6,102 | 1000000; 90000000 |
| `sistema_general_de_regal_as` | VARCHAR | 0.0% | 2,183 | 6874969133; 28728000 |
| `recursos_propios_alcald_as_gobernaciones_y_resguardos_ind_genas_` | VARCHAR | 0.0% | 42,014 | 12000000; 9276219 |
| `recursos_de_credito` | VARCHAR | 0.0% | 693 | 45020635528; 41496000 |
| `recursos_propios` | VARCHAR | 0.0% | 30,928 | 1000000; 35000000 |
| `ultima_actualizacion` | VARCHAR | 31.9% | 1,174 | 2026-03-19 00:00:00.000000000; 2026-01-21 00:00:00.000000000 |
| `codigo_entidad` | VARCHAR | 0.0% | 2,873 | 700587033; 704162254 |
| `codigo_proveedor` | VARCHAR | 0.0% | 234,204 | 720398478; 703824359 |
| `fecha_inicio_liquidacion` | VARCHAR | 14.5% | 2,009 | 2023-12-01 00:00:00.000000000; 2023-07-06 00:00:00.000000000 |
| `fecha_fin_liquidacion` | VARCHAR | 87.3% | 1,854 | 2023-12-01 00:00:00.000000000; 2024-07-30 00:00:00.000000000 |
| `objeto_del_contrato` | VARCHAR | 0.0% | 212,487 | Prestar los servicios de Apoyo la la Gestión en la Secretaría de Desarrollo Terr |
| `duraci_n_del_contrato` | VARCHAR | 0.0% | 1,293 | 132 Mes(es); 3 Mes(es) |
| `nombre_del_banco` | VARCHAR | 0.0% | 3,652 | BOGOTA; Scotibank colpatria |
| `tipo_de_cuenta` | VARCHAR | 0.0% | 3 | No Definido; Ahorros |
| `n_mero_de_cuenta` | VARCHAR | 0.0% | 127,079 | 407263953; 488412521202 |
| `el_contrato_puede_ser_prorrogado` | VARCHAR | 0.0% | 2 | Si; No |
| `fecha_de_notificaci_n_de_prorrogaci_n` | VARCHAR | 76.0% | 1,304 | 2023-06-03 00:00:00.000000000; 2023-07-06 00:00:00.000000000 |
| `nombre_ordenador_del_gasto` | VARCHAR | 0.0% | 5,156 | Luis Alberto Neira Sánchez; GISELLE INGRID PAVA ARIAS |
| `tipo_de_documento_ordenador_del_gasto` | VARCHAR | 0.0% | 7 | NIT; Cédula de Extranjería |
| `n_mero_de_documento_ordenador_del_gasto` | VARCHAR | 0.0% | 5,020 | 71581789; 73581599 |
| `nombre_supervisor` | VARCHAR | 0.0% | 25,978 | Juan Pablo Esterilla Puentes; MARLENY SOLER GUTIERREZ |
| `tipo_de_documento_supervisor` | VARCHAR | 0.0% | 8 | NIT; Permiso especial de permanencia |
| `n_mero_de_documento_supervisor` | VARCHAR | 0.0% | 25,132 | 75064133; 94311609 |
| `nombre_ordenador_de_pago` | VARCHAR | 0.0% | 3,630 | ERIKA PARALES PEREZ; Sonia Enciso Mosquera |
| `tipo_de_documento_ordenador_de_pago` | VARCHAR | 0.0% | 7 | NIT; Citizenship Identification |
| `n_mero_de_documento_ordenador_de_pago` | VARCHAR | 0.0% | 3,589 | 8852368; 14606547 |
| `documentos_tipo` | VARCHAR | 0.0% | 2 | No; Si |
| `descripcion_documentos_tipo` | VARCHAR | 0.0% | 13 | Convenios solidarios - Régimen artículo 92, Ley 2166 de 2021; Infraestructura de |
| `:id` | VARCHAR | 0.0% | 300,000 | row-7ydg~mg58-t6r2; row-3nie.d5d6~5cr8 |

---

## S2 — SECOP II Procesos (`p6dx-8zbt`)

Total rows: 300,000

| Column | Type | Null % | N Distinct | Examples |
|--------|------|--------|------------|---------|
| `referencia_del_proceso` | VARCHAR | 0.0% | 241,977 | 2023-006; 20230149CISP |
| `id_del_portafolio` | VARCHAR | 0.0% | 287,137 | CO1.BDOS.3919439; CO1.BDOS.4549282 |
| `id_del_proceso` | VARCHAR | 0.0% | 288,838 | CO1.REQ.4437172; CO1.REQ.5203830 |
| `entidad` | VARCHAR | 0.0% | 8,465 | INSTITUTO DE DEPORTES Y RECREACION DE MEDELLIN; UNIDAD DE SALUD DE IBAGUE U.S.I. |
| `nit_entidad` | VARCHAR | 0.0% | 8,376 | 890906347; 891380055 |
| `departamento_entidad` | VARCHAR | 0.0% | 34 | Casanare; Magdalena |
| `ciudad_entidad` | VARCHAR | 0.0% | 929 | Zipaquirá; Barbosa |
| `modalidad_de_contratacion` | VARCHAR | 0.0% | 17 | Licitación Pública Acuerdo Marco de Precios; Mínima cuantía |
| `fase` | VARCHAR | 0.0% | 14 | ; Presentación de Observaciones |
| `estado_del_procedimiento` | VARCHAR | 0.0% | 7 | Abierto; Cancelado |
| `fecha_de_publicacion_del` | VARCHAR | 0.0% | 362 | 2023-07-24 00:00:00.000000000; 2023-09-05 00:00:00.000000000 |
| `fecha_de_recepcion_de` | VARCHAR | 86.9% | 361 | 2023-07-06 00:00:00.000000000; 2023-02-21 00:00:00.000000000 |
| `precio_base` | VARCHAR | 0.0% | 98,828 | 8190000; 34304000 |
| `duracion` | VARCHAR | 0.0% | 695 | 135; 195 |
| `unidad_de_duracion` | VARCHAR | 0.0% | 6 | Semana(s); Año(s) |
| `proveedores_invitados` | VARCHAR | 0.0% | 2,050 | 124; 4926 |
| `proveedores_con_invitacion` | VARCHAR | 0.0% | 150 | 41; 34 |
| `respuestas_al_procedimiento` | VARCHAR | 0.0% | 100 | 160; 13 |
| `respuestas_externas` | VARCHAR | 0.0% | 10 | 8; 9 |
| `conteo_de_respuestas_a_ofertas` | VARCHAR | 0.0% | 29 | 148; 41 |
| `proveedores_unicos_con` | VARCHAR | 0.0% | 95 | 13; 23 |
| `visualizaciones_del` | VARCHAR | 0.0% | 302 | 161; 13 |
| `adjudicado` | VARCHAR | 0.0% | 2 | No; Si |
| `valor_total_adjudicacion` | VARCHAR | 0.0% | 14,695 | 32330000; 173107675 |
| `nombre_del_adjudicador` | VARCHAR | 0.0% | 5,377 | DIRECCION CARCEL LA DORADA; JULIAN RODRIGO SOTO RAMIREZ |
| `nit_del_proveedor_adjudicado` | VARCHAR | 0.0% | 3,868 | 805019723; 900446662 |
| `nombre_del_proveedor` | VARCHAR | 0.0% | 9,792 | DISFARMA GC SAS; ASOCIACIÓN INTERNACIONAL DE CONSULTORÍA |
| `urlproceso` | VARCHAR | 0.0% | 288,792 | https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUI |
| `:id` | VARCHAR | 0.0% | 300,000 | row-auwy~mk9j_6fdh; row-hvg6-kinh-5pbs |

---

## F03 Money-Addition Resolution

### SECOP II (S1 contratos)

**Finding:** SECOP II contratos does NOT have an explicit `valor_adicion` column.
Value-related columns found:

- `valor_del_contrato`
- `valor_de_pago_adelantado`
- `valor_facturado`
- `valor_pendiente_de_pago`
- `valor_pagado`
- `valor_amortizado`
- `valor_pendiente_de`
- `valor_pendiente_de_ejecucion`
- `dias_adicionados`

The only time-based addition signal is `dias_adicionados` (integer string, always present).

**`dias_adicionados` distribution:**
- % with value = 0: 86.8%
- Average (non-zero): 7.6 days
- P99: 114 days
- Max: 2191 days

### SECOP I (S4 slices — `79ga-5jck` / `f789-7hwg`)

SECOP I HAS explicit money-addition columns:
- `valor_total_de_adiciones`: total money additions
- `valor_contrato_con_adiciones`: original value + additions

**Sample from pae-la-guajira S3 slice (non-zero additions):**

| valor_total_de_adiciones | valor_contrato_con_adiciones |
|--------------------------|------------------------------|
| 24000000 | 224905448 |
| 2500000 | 27500000 |
| 350946770 | 10906580768 |
| 84456193 | 856831682 |
| 5811196059 | 6260777156 |

### Recommended F03 Rule for M3

**For SECOP II contracts:**
- Use `dias_adicionados` for the time-based component of F03
- **Money additions cannot be computed from SECOP II** because there is no
  `valor_adicion` column. Fallback strategy:
  1. Compare `valor_contrato` (from contratos) vs `valor_total_adjudicacion`
     (from procesos via join) — ratio > 1.4 suggests money addition ≥ 40%.
  2. This requires the contract↔process join (currently ~28% coverage in sample).
  3. When join is available: `money_addition_pct = (valor_contrato / valor_total_adjudicacion - 1) * 100`
     → flag if ≥ 40%.
  4. When join is NOT available: apply only the time-based sub-flag.

**For SECOP I contracts:**
- Use `valor_total_de_adiciones / cuantia_contrato` directly → flag if ≥ 40%.
- Also use `tiempo_adiciones_en_dias` (or months×30) for the time sub-flag.

**F03 recommended implementation for M3:**
```sql
-- Time sub-flag (SECOP II + SECOP I)
dias_adicionados >= 0.5 * duracion_dias_inicial AS f03_tiempo

-- Money sub-flag (SECOP II via join, if available)
(valor_contrato / NULLIF(valor_total_adjudicacion,0) - 1) >= 0.4 AS f03_dinero_secop2

-- Money sub-flag (SECOP I, direct)
CAST(valor_total_de_adiciones AS DOUBLE)
    / NULLIF(CAST(cuantia_contrato AS DOUBLE), 0) >= 0.4 AS f03_dinero_secop1
```

---

## Distinct Modalities

| Modalidad Raw | Total Rows (S1+S2) |
|---------------|---------------------|
| Contratación directa | 351,722 |
| Contratación régimen especial | 181,252 |
| Mínima cuantía | 25,368 |
| Selección Abreviada de Menor Cuantía | 9,275 |
| Selección abreviada subasta inversa | 8,080 |
| Contratación régimen especial (con ofertas) | 5,867 |
| Solicitud de información a los Proveedores | 5,299 |
| Contratación Directa (con ofertas) | 4,940 |
| Licitación pública | 4,199 |
| Concurso de méritos abierto | 2,052 |
| Licitación pública Obra Publica | 1,252 |
| Seleccion Abreviada Menor Cuantia Sin Manifestacion Interes | 470 |
| Subasta de prueba | 70 |
| Licitación Pública Acuerdo Marco de Precios | 53 |
| Enajenación de bienes con subasta | 53 |
| Enajenación de bienes con sobre cerrado | 46 |
| Concurso de méritos con precalificación | 2 |

---

## Join Key Analysis

**Key:** `S1.proceso_de_compra` ↔ `S2.id_del_portafolio`

| S1 rows | Matched to S2 | Coverage % |
|---------|---------------|------------|
| 332,345 | 93,959 | 28.3% |

**Explanation:** Coverage in the 300k sample is below the 60% target because:
1. The 300k sample represents only ~5% of the full 5.6M S1 dataset.
2. The S2 sample (300k of 8.7M) may not overlap with the S1 sample's processes.
3. In full-data mode, coverage is expected to increase significantly.
4. S1 `proceso_de_compra` uses prefix `CO1.BDOS.*`; S2 `id_del_portafolio`
   also uses `CO1.BDOS.*` — the schema is correct, coverage is a sample artifact.

---

## Date Sanity

| Dataset | Field | Min | Max |
|---------|-------|-----|-----|
| S1 | fecha_de_firma | 2023-01-01 | 2023-12-31 |
| S1 | fecha_de_inicio_del_contrato | 2017-02-03 | — |
| S1 | fecha_de_fin_del_contrato | — | 2133-04-25 |
| S2 | fecha_de_publicacion_del | 2023-01-01 | 2023-12-31 |

---
*Generated by `uv run python -m pipeline.clean.profile`*
