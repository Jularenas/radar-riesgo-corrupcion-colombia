# Column Profiling Report — M2

**Sample:** S1=600,000 rows, S2=600,000 rows (2023 sample)

---

## S1 — SECOP II Contratos (`jbjy-vk9h`)

Total rows: 600,000

| Column | Type | Null % | N Distinct | Examples |
|--------|------|--------|------------|---------|
| `nombre_entidad` | VARCHAR | 0.0% | 3,189 | DISTRITO ESPECIAL DE CIENCIA TECNOLOGIA E INNOVACION DE MEDELLIN; Institución Un |
| `nit_entidad` | VARCHAR | 0.0% | 2,735 | 891780009; 8320017942 |
| `departamento` | VARCHAR | 0.0% | 34 | Guaviare; Magdalena |
| `ciudad` | VARCHAR | 0.0% | 629 | Ibagué; Lérida |
| `localizaci_n` | VARCHAR | 0.0% | 759 | Colombia, Bogotá, No Definido; Colombia,  Antioquia ,  Medellín |
| `orden` | VARCHAR | 0.0% | 4 | Nacional; No Definido |
| `sector` | VARCHAR | 0.0% | 26 | defensa; No aplica/No pertenece |
| `rama` | VARCHAR | 0.0% | 5 | Ejecutivo; Judicial |
| `entidad_centralizada` | VARCHAR | 0.0% | 2 | Centralizada; Descentralizada |
| `proceso_de_compra` | VARCHAR | 0.0% | 549,224 | CO1.BDOS.3997510; CO1.BDOS.4770343 |
| `id_contrato` | VARCHAR | 0.0% | 599,957 | CO1.PCCNTR.5440390; CO1.PCCNTR.5275141 |
| `referencia_del_contrato` | VARCHAR | 0.0% | 456,325 | CARRENDAMIENTO-024-2023; TT-38-2023 |
| `estado_contrato` | VARCHAR | 0.0% | 10 | Borrador; cedido |
| `codigo_de_categoria_principal` | VARCHAR | 0.0% | 6,745 | V1.80111501; V1.81101500 |
| `descripcion_del_proceso` | VARCHAR | 0.0% | 379,475 | Prestar sus servicios profesionales; por sus propios medios con plena
autonomía  |
| `tipo_de_contrato` | VARCHAR | 0.0% | 21 | Venta inmuebles; Negocio fiduciario |
| `modalidad_de_contratacion` | VARCHAR | 0.0% | 15 | Licitación Pública Acuerdo Marco de Precios; Concurso de méritos con precalifica |
| `justificacion_modalidad_de` | VARCHAR | 0.0% | 32 | Servicios profesionales y apoyo a la gestión; No existe pluralidad de oferentes  |
| `fecha_de_firma` | VARCHAR | 0.0% | 362 | 2023-02-20 00:00:00.000000000; 2023-07-06 00:00:00.000000000 |
| `fecha_de_inicio_del_contrato` | VARCHAR | 1.0% | 659 | 2023-07-24 00:00:00.000000000; 2023-04-27 00:00:00.000000000 |
| `fecha_de_fin_del_contrato` | VARCHAR | 0.0% | 3,132 | 2024-01-31 00:00:00.000000000; 2023-01-30 00:00:00.000000000 |
| `condiciones_de_entrega` | VARCHAR | 0.0% | 25 | NXTWY.DLVY.3; NXTWY.DLVY.10 |
| `tipodocproveedor` | VARCHAR | 0.0% | 10 | Pasaporte; NIT |
| `documento_proveedor` | VARCHAR | 0.0% | 392,873 | 899999420; 1024504736 |
| `proveedor_adjudicado` | VARCHAR | 0.0% | 391,886 | ANGIE TERESA TORO CUERVO; MARLON LOPEZ |
| `es_grupo` | VARCHAR | 0.0% | 2 | No; Si |
| `es_pyme` | VARCHAR | 0.0% | 2 | Si; No |
| `habilita_pago_adelantado` | VARCHAR | 0.0% | 3 | No; Si |
| `liquidaci_n` | VARCHAR | 0.0% | 2 | No; Si |
| `obligaci_n_ambiental` | VARCHAR | 0.0% | 2 | No; Si |
| `obligaciones_postconsumo` | VARCHAR | 0.0% | 2 | No; Si |
| `reversion` | VARCHAR | 0.0% | 2 | No; Si |
| `origen_de_los_recursos` | VARCHAR | 0.0% | 2 | Distribuido; Recursos Propios |
| `destino_gasto` | VARCHAR | 0.0% | 4 | No aplica; No Definido |
| `valor_del_contrato` | VARCHAR | 0.0% | 171,634 | 64200000; 60900000 |
| `valor_de_pago_adelantado` | VARCHAR | 0.0% | 577 | 12300000; 80000000 |
| `valor_facturado` | VARCHAR | 0.0% | 129,395 | 44528000; 154700633 |
| `valor_pendiente_de_pago` | VARCHAR | 0.0% | 131,494 | 6720000; 23100000 |
| `valor_pagado` | VARCHAR | 0.0% | 117,835 | 21630000; 9800000 |
| `valor_amortizado` | VARCHAR | 0.0% | 200 | 90635002; 180960000 |
| `valor_pendiente_de` | VARCHAR | 0.0% | 469 | 77500000; 25920000 |
| `valor_pendiente_de_ejecucion` | VARCHAR | 0.0% | 131,499 | 1000000; 241000 |
| `saldo_cdp` | VARCHAR | 0.0% | 141,561 | 417810000; 1326024562 |
| `saldo_vigencia` | VARCHAR | 0.0% | 4,206 | 2166143594; 526589548 |
| `espostconflicto` | VARCHAR | 0.0% | 2 | No; Si |
| `dias_adicionados` | VARCHAR | 0.0% | 505 | 183; 72 |
| `puntos_del_acuerdo` | VARCHAR | 0.0% | 7 | TG; ParticipacionPolitica |
| `pilares_del_acuerdo` | VARCHAR | 0.0% | 20 | RICP; CapituloGenero |
| `urlproceso` | VARCHAR | 0.0% | 549,008 | https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUI |
| `nombre_representante_legal` | VARCHAR | 0.0% | 390,124 | SONIA XIMENA TORRES DOMINGUEZ; Jose Nelson Flores Cárdenas |
| `nacionalidad_representante_legal` | VARCHAR | 0.0% | 58 | BR; PK |
| `domicilio_representante_legal` | VARCHAR | 0.0% | 137,858 | CALLE 200 Numero 13-36 Floridablanca Santander; cra 6 46 9 |
| `tipo_de_identificaci_n_representante_legal` | VARCHAR | 0.0% | 10 | Pasaporte; NIT |
| `identificaci_n_representante_legal` | VARCHAR | 0.0% | 165,037 | 16072243; 19495340 |
| `g_nero_representante_legal` | VARCHAR | 0.0% | 4 | Mujer; Hombre |
| `presupuesto_general_de_la_nacion_pgn` | VARCHAR | 0.0% | 56,898 | 15301971; 83947609 |
| `sistema_general_de_participaciones` | VARCHAR | 0.0% | 10,707 | 10930000; 90837060 |
| `sistema_general_de_regal_as` | VARCHAR | 0.0% | 3,984 | 10902312; 30958759 |
| `recursos_propios_alcald_as_gobernaciones_y_resguardos_ind_genas_` | VARCHAR | 0.0% | 71,133 | 17400000; 35000000 |
| `recursos_de_credito` | VARCHAR | 0.0% | 1,300 | 45020635528; 41496000 |
| `recursos_propios` | VARCHAR | 0.0% | 54,021 | 13845795; 11088000 |
| `ultima_actualizacion` | VARCHAR | 32.0% | 1,193 | 2023-12-25 00:00:00.000000000; 2023-12-01 00:00:00.000000000 |
| `codigo_entidad` | VARCHAR | 0.0% | 3,193 | 706486917; 704629146 |
| `codigo_proveedor` | VARCHAR | 0.0% | 394,494 | 703000075; 704951474 |
| `fecha_inicio_liquidacion` | VARCHAR | 36.4% | 2,619 | 2023-12-31T00:00:00.000; 2023-10-31T00:00:00.000 |
| `fecha_fin_liquidacion` | VARCHAR | 87.3% | 2,117 | 2024-12-01 00:00:00.000000000; 2024-06-15 00:00:00.000000000 |
| `objeto_del_contrato` | VARCHAR | 0.0% | 388,252 | PRESTACIÓN DE SERVICIOS PROFESIONALES DE INGENIERO (A) DE ALIMENTOS PARA LA EJEC |
| `duraci_n_del_contrato` | VARCHAR | 0.0% | 1,591 | 132 Mes(es); 3 Mes(es) |
| `nombre_del_banco` | VARCHAR | 0.0% | 5,478 | Mario Ernesto Correa Vera; COLPATRIA |
| `tipo_de_cuenta` | VARCHAR | 0.0% | 3 | Ahorros; No Definido |
| `n_mero_de_cuenta` | VARCHAR | 0.0% | 217,407 | 64179077963; 514088079 |
| `el_contrato_puede_ser_prorrogado` | VARCHAR | 0.0% | 2 | Si; No |
| `fecha_de_notificaci_n_de_prorrogaci_n` | VARCHAR | 76.0% | 1,607 | 2023-04-15 00:00:00.000000000; 2023-04-30 00:00:00.000000000 |
| `nombre_ordenador_del_gasto` | VARCHAR | 0.0% | 5,972 | LUIS EDGAR RAMIREZ ARBELAEZ; CESAR CAMILO ROJAS CRUZ |
| `tipo_de_documento_ordenador_del_gasto` | VARCHAR | 0.0% | 7 | NIT; Cédula de Extranjería |
| `n_mero_de_documento_ordenador_del_gasto` | VARCHAR | 0.0% | 5,800 | 19151231; 53118810 |
| `nombre_supervisor` | VARCHAR | 0.0% | 31,466 | HINDERMAN FIGUEROA RODRIGUEZ; ANDREA JIMENA HERRERA VIDAL |
| `tipo_de_documento_supervisor` | VARCHAR | 0.0% | 9 | NIT; Identity Card |
| `n_mero_de_documento_supervisor` | VARCHAR | 0.0% | 30,372 | 1057585211; 1018441782 |
| `nombre_ordenador_de_pago` | VARCHAR | 0.0% | 4,645 | Juan Esteban Espinel Díaz; RAFAEL DEL CRISTO CUESTA CASTRO |
| `tipo_de_documento_ordenador_de_pago` | VARCHAR | 0.0% | 7 | NIT; Otro |
| `n_mero_de_documento_ordenador_de_pago` | VARCHAR | 0.0% | 4,590 | 13364120.; 87069477 |
| `documentos_tipo` | VARCHAR | 0.0% | 2 | No; Si |
| `descripcion_documentos_tipo` | VARCHAR | 0.0% | 13 | Sector de agua potable y saneamiento básico; Convenios solidarios - Régimen artí |
| `:id` | VARCHAR | 0.0% | 600,000 | row-cuet.7bur~mq8p; row-9c7h~twsq-iusd |

---

## S2 — SECOP II Procesos (`p6dx-8zbt`)

Total rows: 600,000

| Column | Type | Null % | N Distinct | Examples |
|--------|------|--------|------------|---------|
| `referencia_del_proceso` | VARCHAR | 0.0% | 243,745 | 427762; OSE_1876_2023 |
| `id_del_portafolio` | VARCHAR | 0.0% | 289,502 | CO1.BDOS.5108044; CO1.BDOS.4839147 |
| `id_del_proceso` | VARCHAR | 0.0% | 291,239 | CO1.REQ.4484345; CO1.REQ.3990717 |
| `entidad` | VARCHAR | 0.0% | 8,468 | COLEGIO EDUARDO SANTOS I.E.D.; ESE HOSPITAL SAN ROQUE CHIMA |
| `nit_entidad` | VARCHAR | 0.0% | 8,378 | 901387801; 800130625 |
| `departamento_entidad` | VARCHAR | 0.0% | 34 | Magdalena; Caquetá |
| `ciudad_entidad` | VARCHAR | 0.0% | 930 | San Francisco; Sabaneta |
| `modalidad_de_contratacion` | VARCHAR | 0.0% | 17 | Licitación Pública Acuerdo Marco de Precios; Contratación régimen especial (con  |
| `fase` | VARCHAR | 0.0% | 14 | ; Presentación de Observaciones |
| `estado_del_procedimiento` | VARCHAR | 0.0% | 7 | Seleccionado; Suspendido |
| `fecha_de_publicacion_del` | VARCHAR | 0.0% | 362 | 2023-10-09 00:00:00.000000000; 2023-06-27 00:00:00.000000000 |
| `fecha_de_recepcion_de` | VARCHAR | 86.9% | 361 | 2023-02-21 00:00:00.000000000; 2023-09-05 00:00:00.000000000 |
| `precio_base` | VARCHAR | 0.0% | 99,656 | 1222705; 1546983513 |
| `duracion` | VARCHAR | 0.0% | 700 | 305; 0 |
| `unidad_de_duracion` | VARCHAR | 0.0% | 6 | Semana(s); Año(s) |
| `proveedores_invitados` | VARCHAR | 0.0% | 2,061 | 4506; 382 |
| `proveedores_con_invitacion` | VARCHAR | 0.0% | 150 | 34; 98 |
| `respuestas_al_procedimiento` | VARCHAR | 0.0% | 100 | 17; 8 |
| `respuestas_externas` | VARCHAR | 0.0% | 10 | 8; 6 |
| `conteo_de_respuestas_a_ofertas` | VARCHAR | 0.0% | 29 | 148; 41 |
| `proveedores_unicos_con` | VARCHAR | 0.0% | 95 | 41; 34 |
| `visualizaciones_del` | VARCHAR | 0.0% | 302 | 43; 79 |
| `adjudicado` | VARCHAR | 0.0% | 2 | No; Si |
| `valor_total_adjudicacion` | VARCHAR | 0.0% | 14,825 | 0; 600050000 |
| `nombre_del_adjudicador` | VARCHAR | 0.0% | 5,395 | DIANA MARCELA MARTÍNEZ RODRÍGUEZ; Cristian Arleth Chacón Samboni |
| `nit_del_proveedor_adjudicado` | VARCHAR | 0.0% | 3,885 | 800200257; 811032187 |
| `nombre_del_proveedor` | VARCHAR | 0.0% | 9,835 | ADEQUIM S.A.S; LEON GRAFICAS S.A.S |
| `urlproceso` | VARCHAR | 0.0% | 291,192 | https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUI |
| `:id` | VARCHAR | 0.0% | 600,000 | row-xe6k~cpgh-6jjq; row-a8tu_2abg-347t |

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
- % with value = 0: 86.9%
- Average (non-zero): 7.5 days
- P99: 111 days
- Max: 3652 days

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
| Contratación directa | 703,754 |
| Contratación régimen especial | 362,631 |
| Mínima cuantía | 50,549 |
| Selección Abreviada de Menor Cuantía | 18,506 |
| Selección abreviada subasta inversa | 15,962 |
| Contratación régimen especial (con ofertas) | 11,769 |
| Solicitud de información a los Proveedores | 10,576 |
| Contratación Directa (con ofertas) | 9,859 |
| Licitación pública | 8,373 |
| Concurso de méritos abierto | 4,151 |
| Licitación pública Obra Publica | 2,503 |
| Seleccion Abreviada Menor Cuantia Sin Manifestacion Interes | 927 |
| Subasta de prueba | 141 |
| Licitación Pública Acuerdo Marco de Precios | 118 |
| Enajenación de bienes con sobre cerrado | 88 |
| Enajenación de bienes con subasta | 88 |
| Concurso de méritos con precalificación | 5 |

---

## Join Key Analysis

**Key:** `S1.proceso_de_compra` ↔ `S2.id_del_portafolio`

| S1 rows | Matched to S2 | Coverage % |
|---------|---------------|------------|
| 832,238 | 355,678 | 42.7% |

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
| S1 | fecha_de_fin_del_contrato | — | 2923-09-30 |
| S2 | fecha_de_publicacion_del | 2023-01-01 | 2023-12-31 |

---
*Generated by `uv run python -m pipeline.clean.profile`*
