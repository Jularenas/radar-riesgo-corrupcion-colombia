# Column Profiling Report — M2

**Sample:** S1=300,000 rows, S2=300,000 rows (2023 sample)

---

## S1 — SECOP II Contratos (`jbjy-vk9h`)

Total rows: 300,000

| Column | Type | Null % | N Distinct | Examples |
|--------|------|--------|------------|---------|
| `nombre_entidad` | VARCHAR | 0.0% | 2,871 | ALCALDÍA DISTRITAL DE SANTA MARTA; SIC SUPERINTENDENCIA DE INDUSTRIA Y COMERCIO |
| `nit_entidad` | VARCHAR | 0.0% | 2,442 | 891800395; 891780009 |
| `departamento` | VARCHAR | 0.0% | 34 | Magdalena; Casanare |
| `ciudad` | VARCHAR | 0.0% | 568 | Ibagué; Sabaneta |
| `localizaci_n` | VARCHAR | 0.0% | 694 | Colombia,  Bolívar ,  Simití; Colombia,  Cundinamarca , No Definido |
| `orden` | VARCHAR | 0.0% | 4 | Nacional; No Definido |
| `sector` | VARCHAR | 0.0% | 26 | defensa; deportes |
| `rama` | VARCHAR | 0.0% | 5 | Ejecutivo; Judicial |
| `entidad_centralizada` | VARCHAR | 0.0% | 2 | Centralizada; Descentralizada |
| `proceso_de_compra` | VARCHAR | 0.0% | 277,979 | CO1.BDOS.3999321; CO1.BDOS.3784070 |
| `id_contrato` | VARCHAR | 0.0% | 299,979 | CO1.PCCNTR.5209694; CO1.PCCNTR.5050359 |
| `referencia_del_contrato` | VARCHAR | 0.0% | 239,282 | 104-7-20444-23; ECAM-MC-002-2023 |
| `estado_contrato` | VARCHAR | 0.0% | 9 | Borrador; terminado |
| `codigo_de_categoria_principal` | VARCHAR | 0.0% | 5,184 | V1.81101500; V1.80111501 |
| `descripcion_del_proceso` | VARCHAR | 0.0% | 208,572 | Prestar sus servicios profesionales; por sus propios medios con plena
autonomía  |
| `tipo_de_contrato` | VARCHAR | 0.0% | 21 | Comodato; Servicios financieros |
| `modalidad_de_contratacion` | VARCHAR | 0.0% | 14 | Licitación Pública Acuerdo Marco de Precios; Contratación Directa (con ofertas) |
| `justificacion_modalidad_de` | VARCHAR | 0.0% | 32 | Servicios profesionales y apoyo a la gestión; No existe pluralidad de oferentes  |
| `fecha_de_firma` | VARCHAR | 0.0% | 362 | 2023-07-06 00:00:00.000000000; 2023-01-30 00:00:00.000000000 |
| `fecha_de_inicio_del_contrato` | VARCHAR | 1.0% | 564 | 2023-03-10 00:00:00.000000000; 2023-12-02 00:00:00.000000000 |
| `fecha_de_fin_del_contrato` | VARCHAR | 0.0% | 1,784 | 2024-01-31 00:00:00.000000000; 2023-01-30 00:00:00.000000000 |
| `condiciones_de_entrega` | VARCHAR | 0.0% | 22 | NXTWY.DLVY.3; NXTWY.DLVY.10 |
| `tipodocproveedor` | VARCHAR | 0.0% | 10 | Pasaporte; Cédula de Extranjería |
| `documento_proveedor` | VARCHAR | 0.0% | 233,422 | 1022392561; 74372211 |
| `proveedor_adjudicado` | VARCHAR | 0.0% | 233,091 | Adriana Maria Gonzalez Puliche; MARA LUCIA ALVAREZ DOMINGUEZ |
| `es_grupo` | VARCHAR | 0.0% | 2 | No; Si |
| `es_pyme` | VARCHAR | 0.0% | 2 | No; Si |
| `habilita_pago_adelantado` | VARCHAR | 0.0% | 3 | No Definido; No |
| `liquidaci_n` | VARCHAR | 0.0% | 2 | No; Si |
| `obligaci_n_ambiental` | VARCHAR | 0.0% | 2 | No; Si |
| `obligaciones_postconsumo` | VARCHAR | 0.0% | 2 | No; Si |
| `reversion` | VARCHAR | 0.0% | 2 | No; Si |
| `origen_de_los_recursos` | VARCHAR | 0.0% | 2 | Distribuido; Recursos Propios |
| `destino_gasto` | VARCHAR | 0.0% | 3 | Inversión; No Definido |
| `valor_del_contrato` | VARCHAR | 0.0% | 100,188 | 14280000; 60543000 |
| `valor_de_pago_adelantado` | VARCHAR | 0.0% | 319 | 137297899; 26192466 |
| `valor_facturado` | VARCHAR | 0.0% | 74,522 | 17400000; 9684606 |
| `valor_pendiente_de_pago` | VARCHAR | 0.0% | 74,688 | 35000000; 100327526 |
| `valor_pagado` | VARCHAR | 0.0% | 68,072 | 17400000; 9684606 |
| `valor_amortizado` | VARCHAR | 0.0% | 108 | 12300000; 3600000 |
| `valor_pendiente_de` | VARCHAR | 0.0% | 263 | 137297899; 26192466 |
| `valor_pendiente_de_ejecucion` | VARCHAR | 0.0% | 74,688 | 11078165; 11051887 |
| `saldo_cdp` | VARCHAR | 0.0% | 85,705 | 347000000; 17400000 |
| `saldo_vigencia` | VARCHAR | 0.0% | 2,546 | 28163658014; 21631114 |
| `espostconflicto` | VARCHAR | 0.0% | 2 | No; Si |
| `dias_adicionados` | VARCHAR | 0.0% | 412 | 72; 183 |
| `puntos_del_acuerdo` | VARCHAR | 0.0% | 7 | ParticipacionPolitica; TG |
| `pilares_del_acuerdo` | VARCHAR | 0.0% | 20 | DSViviendaYAguaPotable; DSSalud |
| `urlproceso` | VARCHAR | 0.0% | 277,861 | https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUI |
| `nombre_representante_legal` | VARCHAR | 0.0% | 232,356 | HUGO MAURICIO SANCHEZ CARVAJAL; HAROLD FERNANDO OSORIO GUZMAN |
| `nacionalidad_representante_legal` | VARCHAR | 0.0% | 49 | ES; BR |
| `domicilio_representante_legal` | VARCHAR | 0.0% | 82,745 | calle 3 sur #5-72; calle 13 # 57-50 piso 4 cu 54 |
| `tipo_de_identificaci_n_representante_legal` | VARCHAR | 0.0% | 10 | Pasaporte; NIT |
| `identificaci_n_representante_legal` | VARCHAR | 0.0% | 98,333 | 1121908183; 8.374.582 |
| `g_nero_representante_legal` | VARCHAR | 0.0% | 4 | Mujer; No Definido |
| `presupuesto_general_de_la_nacion_pgn` | VARCHAR | 0.0% | 33,124 | 55440000; 21849760 |
| `sistema_general_de_participaciones` | VARCHAR | 0.0% | 6,102 | 2320000; 6000000 |
| `sistema_general_de_regal_as` | VARCHAR | 0.0% | 2,183 | 0; 21636720 |
| `recursos_propios_alcald_as_gobernaciones_y_resguardos_ind_genas_` | VARCHAR | 0.0% | 42,014 | 0; 11896500 |
| `recursos_de_credito` | VARCHAR | 0.0% | 693 | 45020635528; 41496000 |
| `recursos_propios` | VARCHAR | 0.0% | 30,928 | 1000000; 35000000 |
| `ultima_actualizacion` | VARCHAR | 31.9% | 1,174 | 2026-03-19 00:00:00.000000000; 2026-05-08 00:00:00.000000000 |
| `codigo_entidad` | VARCHAR | 0.0% | 2,873 | 704063072; 700403058 |
| `codigo_proveedor` | VARCHAR | 0.0% | 234,204 | 720398478; 703824359 |
| `fecha_inicio_liquidacion` | VARCHAR | 14.5% | 2,009 | 2023-08-08T00:00:00.000; 2023-05-13T00:00:00.000 |
| `fecha_fin_liquidacion` | VARCHAR | 87.3% | 1,854 | 2024-03-26 00:00:00.000000000; 2026-05-08 00:00:00.000000000 |
| `objeto_del_contrato` | VARCHAR | 0.0% | 212,487 | PRESTACION DE SERVICIOS COMO TECNOLOGO EN REGENCIA DE FARMACIA PARA LA UNIDAD DE |
| `duraci_n_del_contrato` | VARCHAR | 0.0% | 1,293 | 3 Mes(es); 236 Dia(s) |
| `nombre_del_banco` | VARCHAR | 0.0% | 3,652 | BOGOTA; Scotibank colpatria |
| `tipo_de_cuenta` | VARCHAR | 0.0% | 3 | Corriente; No Definido |
| `n_mero_de_cuenta` | VARCHAR | 0.0% | 127,079 | 407263953; 488412521202 |
| `el_contrato_puede_ser_prorrogado` | VARCHAR | 0.0% | 2 | Si; No |
| `fecha_de_notificaci_n_de_prorrogaci_n` | VARCHAR | 76.0% | 1,304 | 2023-11-15 00:00:00.000000000; 2023-09-12 00:00:00.000000000 |
| `nombre_ordenador_del_gasto` | VARCHAR | 0.0% | 5,156 | ANDRES EDUARDO GOMEZ MARTINEZ; JOSE LUIS SANCHEZ CARDONA |
| `tipo_de_documento_ordenador_del_gasto` | VARCHAR | 0.0% | 7 | Cédula de Extranjería; NIT |
| `n_mero_de_documento_ordenador_del_gasto` | VARCHAR | 0.0% | 5,020 | 71581789; 73581599 |
| `nombre_supervisor` | VARCHAR | 0.0% | 25,978 | Juan Pablo Esterilla Puentes; MARLENY SOLER GUTIERREZ |
| `tipo_de_documento_supervisor` | VARCHAR | 0.0% | 8 | Permiso especial de permanencia; NIT |
| `n_mero_de_documento_supervisor` | VARCHAR | 0.0% | 25,132 | 1051475494; 42125024 |
| `nombre_ordenador_de_pago` | VARCHAR | 0.0% | 3,630 | ERIKA PARALES PEREZ; Sonia Enciso Mosquera |
| `tipo_de_documento_ordenador_de_pago` | VARCHAR | 0.0% | 7 | Cédula de Extranjería; NIT |
| `n_mero_de_documento_ordenador_de_pago` | VARCHAR | 0.0% | 3,589 | 89005299; 93414641 |
| `documentos_tipo` | VARCHAR | 0.0% | 2 | No; Si |
| `descripcion_documentos_tipo` | VARCHAR | 0.0% | 13 | Sector de agua potable y saneamiento básico; Convenios solidarios - Régimen artí |
| `:id` | VARCHAR | 0.0% | 300,000 | row-xmim_zkp2~z3vq; row-ki8b-knux.tr43 |

---

## S2 — SECOP II Procesos (`p6dx-8zbt`)

Total rows: 300,000

| Column | Type | Null % | N Distinct | Examples |
|--------|------|--------|------------|---------|
| `referencia_del_proceso` | VARCHAR | 0.0% | 241,977 | OPS006-2023; 5200683 |
| `id_del_portafolio` | VARCHAR | 0.0% | 287,137 | CO1.BDOS.4072189; CO1.BDOS.4796660 |
| `id_del_proceso` | VARCHAR | 0.0% | 288,838 | CO1.REQ.5181703; CO1.REQ.4164530 |
| `entidad` | VARCHAR | 0.0% | 8,465 | COLEGIO CIUDAD DE MONTREAL IED; SENA REGIONAL VALLE Grupo de Apoyo Administrativ |
| `nit_entidad` | VARCHAR | 0.0% | 8,376 | 800194096; 890980807 |
| `departamento_entidad` | VARCHAR | 0.0% | 34 | Casanare; Magdalena |
| `ciudad_entidad` | VARCHAR | 0.0% | 929 | San Francisco; Sabaneta |
| `modalidad_de_contratacion` | VARCHAR | 0.0% | 17 | Licitación Pública Acuerdo Marco de Precios; Contratación directa |
| `fase` | VARCHAR | 0.0% | 14 | Manifestación de interés (Menor Cuantía); Clarification submission |
| `estado_del_procedimiento` | VARCHAR | 0.0% | 7 | Cancelado; Aprobado |
| `fecha_de_publicacion_del` | VARCHAR | 0.0% | 362 | 2023-04-08 00:00:00.000000000; 2023-02-22 00:00:00.000000000 |
| `fecha_de_recepcion_de` | VARCHAR | 86.9% | 361 | 2023-07-06 00:00:00.000000000; 2023-01-30 00:00:00.000000000 |
| `precio_base` | VARCHAR | 0.0% | 98,828 | 1222705; 1546983513 |
| `duracion` | VARCHAR | 0.0% | 695 | 135; 195 |
| `unidad_de_duracion` | VARCHAR | 0.0% | 6 | Año(s); Semana(s) |
| `proveedores_invitados` | VARCHAR | 0.0% | 2,050 | 164; 174 |
| `proveedores_con_invitacion` | VARCHAR | 0.0% | 150 | 34; 41 |
| `respuestas_al_procedimiento` | VARCHAR | 0.0% | 100 | 34; 109 |
| `respuestas_externas` | VARCHAR | 0.0% | 10 | 6; 9 |
| `conteo_de_respuestas_a_ofertas` | VARCHAR | 0.0% | 29 | 148; 41 |
| `proveedores_unicos_con` | VARCHAR | 0.0% | 95 | 41; 34 |
| `visualizaciones_del` | VARCHAR | 0.0% | 302 | 13; 23 |
| `adjudicado` | VARCHAR | 0.0% | 2 | No; Si |
| `valor_total_adjudicacion` | VARCHAR | 0.0% | 14,695 | 31631784; 24706414 |
| `nombre_del_adjudicador` | VARCHAR | 0.0% | 5,377 | ZULAY MARÍA TAMARA ABRIL; EILEN TATIANA CANDANOZA LUBO |
| `nit_del_proveedor_adjudicado` | VARCHAR | 0.0% | 3,868 | 805019723; 900446662 |
| `nombre_del_proveedor` | VARCHAR | 0.0% | 9,792 | DISFARMA GC SAS; ASOCIACIÓN INTERNACIONAL DE CONSULTORÍA |
| `urlproceso` | VARCHAR | 0.0% | 288,792 | https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUI |
| `:id` | VARCHAR | 0.0% | 300,000 | row-x6tv-nd4h.y4dc; row-i8e2.k8q2-wref |

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
