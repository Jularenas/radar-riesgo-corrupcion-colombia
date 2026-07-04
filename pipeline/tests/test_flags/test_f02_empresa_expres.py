"""
Unit tests for F02 -- Empresa exprés.

Covers both states of the real mart this module has to handle: (a) the
common M3-era state where dim_proveedor has no fecha_matricula column yet
(RUES enrichment is M4's job) -- must degrade to an empty, not-applicable
result rather than erroring, and (b) the post-M4 state where the column
exists, exercising the actual date-window logic.
"""

from __future__ import annotations

from conftest import make_dim_proveedor, make_fct_contrato, make_fct_proceso

from pipeline.flags import f02_empresa_expres as f02


class TestF02NotYetApplicable:
    def test_missing_fecha_matricula_returns_empty(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "proceso_de_compra": "P1", "doc_proveedor_norm": "900111222"}])
        make_fct_proceso(mem_con, [{"referencia": "P1", "row_id": "r1", "fecha_publicacion": "2023-05-01"}])
        make_dim_proveedor(mem_con, [{"doc_proveedor_norm": "900111222"}], with_fecha_matricula=False)

        rows = f02.compute(mem_con)
        assert rows == []


class TestF02WithRuesData:
    def _setup(self, con, *, fecha_matricula, fecha_publicacion):
        make_fct_contrato(con, [{"id_contrato": "C1", "proceso_de_compra": "P1", "doc_proveedor_norm": "900111222"}])
        make_fct_proceso(con, [{"referencia": "P1", "row_id": "r1", "fecha_publicacion": fecha_publicacion}])
        make_dim_proveedor(
            con,
            [{"doc_proveedor_norm": "900111222", "fecha_matricula": fecha_matricula}],
            with_fecha_matricula=True,
        )

    def test_positive_registered_shortly_before_publication(self, mem_con):
        """Registered 10 days before the process was published -> fires."""
        self._setup(mem_con, fecha_matricula="2023-04-21", fecha_publicacion="2023-05-01")
        rows = f02.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True
        assert rows[0].evidence["dias_desde_matricula"] == 10

    def test_negative_registered_years_before(self, mem_con):
        """Long-established supplier -> does not fire."""
        self._setup(mem_con, fecha_matricula="2010-01-01", fecha_publicacion="2023-05-01")
        rows = f02.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False

    def test_edge_registered_after_publication_not_applicable(self, mem_con):
        """A supplier registered *after* the process was published isn't an 'express company
        ahead of this tender' -- must not fire (and DATE_DIFF would be negative)."""
        self._setup(mem_con, fecha_matricula="2023-06-01", fecha_publicacion="2023-05-01")
        rows = f02.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False
