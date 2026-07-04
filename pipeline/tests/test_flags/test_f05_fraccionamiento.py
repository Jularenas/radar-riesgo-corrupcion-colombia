"""Unit tests for F05 -- Fraccionamiento."""

from __future__ import annotations

from conftest import make_fct_contrato, make_ref_smmlv

from pipeline.flags import f05_fraccionamiento as f05

# 2023 SMMLV in the test fixture is 1,160,000 -> threshold = 280 * 1,160,000 = 324,800,000
_ABOVE_THRESHOLD_EACH = 120_000_000.0  # 3 of these = 360,000,000 > threshold


class TestF05:
    def test_positive_three_clustered_contracts_over_threshold(self, mem_con):
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": f"C{i}", "modalidad_norm": "CONTRATACION_DIRECTA",
                    "nit_entidad_norm": "900111222", "doc_proveedor_norm": "800333444",
                    "unspsc_segmento": 80, "fecha_firma": d, "valor_contrato": _ABOVE_THRESHOLD_EACH, "anio": 2023,
                }
                for i, d in enumerate(["2023-01-01", "2023-01-20", "2023-02-15"])
            ],
        )
        make_ref_smmlv(mem_con)
        rows = f05.compute(mem_con)
        assert len(rows) == 3
        assert all(r.fired for r in rows)

    def test_negative_only_two_contracts(self, mem_con):
        """Only 2 contracts in the cluster -- below the >=3 floor, must NOT fire."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": f"C{i}", "modalidad_norm": "CONTRATACION_DIRECTA",
                    "nit_entidad_norm": "900111222", "doc_proveedor_norm": "800333444",
                    "unspsc_segmento": 80, "fecha_firma": d, "valor_contrato": _ABOVE_THRESHOLD_EACH, "anio": 2023,
                }
                for i, d in enumerate(["2023-01-01", "2023-01-20"])
            ],
        )
        make_ref_smmlv(mem_con)
        rows = f05.compute(mem_con)
        assert len(rows) == 2
        assert not any(r.fired for r in rows)

    def test_negative_below_value_threshold(self, mem_con):
        """3 contracts, clustered, but their sum stays under the SMMLV threshold."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": f"C{i}", "modalidad_norm": "CONTRATACION_DIRECTA",
                    "nit_entidad_norm": "900111222", "doc_proveedor_norm": "800333444",
                    "unspsc_segmento": 80, "fecha_firma": d, "valor_contrato": 10_000_000.0, "anio": 2023,
                }
                for i, d in enumerate(["2023-01-01", "2023-01-20", "2023-02-15"])
            ],
        )
        make_ref_smmlv(mem_con)
        rows = f05.compute(mem_con)
        assert len(rows) == 3
        assert not any(r.fired for r in rows)

    def test_negative_outside_90_day_window(self, mem_con):
        """3 contracts over threshold value but spread far apart in time -- no single 90-day
        window contains all 3, so none of them individually see >=3 neighbours."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": f"C{i}", "modalidad_norm": "CONTRATACION_DIRECTA",
                    "nit_entidad_norm": "900111222", "doc_proveedor_norm": "800333444",
                    "unspsc_segmento": 80, "fecha_firma": d, "valor_contrato": _ABOVE_THRESHOLD_EACH, "anio": 2023,
                }
                for i, d in enumerate(["2023-01-01", "2023-05-01", "2023-09-01"])
            ],
        )
        make_ref_smmlv(mem_con)
        rows = f05.compute(mem_con)
        assert len(rows) == 3
        assert not any(r.fired for r in rows)

    def test_negative_different_unspsc_segments_not_grouped(self, mem_con):
        """Same entity+supplier+dates, but different UNSPSC segments -- not the same 'need',
        so they must not be grouped into one fraccionamiento cluster."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": f"C{i}", "modalidad_norm": "CONTRATACION_DIRECTA",
                    "nit_entidad_norm": "900111222", "doc_proveedor_norm": "800333444",
                    "unspsc_segmento": 80 + i, "fecha_firma": d, "valor_contrato": _ABOVE_THRESHOLD_EACH, "anio": 2023,
                }
                for i, d in enumerate(["2023-01-01", "2023-01-20", "2023-02-15"])
            ],
        )
        make_ref_smmlv(mem_con)
        rows = f05.compute(mem_con)
        assert len(rows) == 3
        assert not any(r.fired for r in rows)

    def test_edge_competitive_modality_not_applicable(self, mem_con):
        """F05 only applies to contratación directa -- a competitive cluster is out of scope."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": f"C{i}", "modalidad_norm": "LICITACION_PUBLICA",
                    "nit_entidad_norm": "900111222", "doc_proveedor_norm": "800333444",
                    "unspsc_segmento": 80, "fecha_firma": d, "valor_contrato": _ABOVE_THRESHOLD_EACH, "anio": 2023,
                }
                for i, d in enumerate(["2023-01-01", "2023-01-20", "2023-02-15"])
            ],
        )
        make_ref_smmlv(mem_con)
        rows = f05.compute(mem_con)
        assert rows == []
