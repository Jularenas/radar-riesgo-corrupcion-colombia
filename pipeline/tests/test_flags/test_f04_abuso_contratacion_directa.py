"""Unit tests for F04 -- Abuso de contratación directa (entity-level z-score vs department peers)."""

from __future__ import annotations

from conftest import make_dim_entidad, make_fct_contrato

from pipeline.flags import f04_abuso_contratacion_directa as f04


def _entity_contracts(nit, cod_dpto, n, direct_frac, base_value=10_000_000.0):
    """n contracts for `nit`; direct_frac of them (by count) are CONTRATACION_DIRECTA."""
    n_direct = round(n * direct_frac)
    rows = []
    for i in range(n):
        rows.append(
            {
                "id_contrato": f"{nit}-{i}",
                "nit_entidad_norm": nit,
                "modalidad_norm": "CONTRATACION_DIRECTA" if i < n_direct else "LICITACION_PUBLICA",
                "valor_contrato": base_value,
            }
        )
    return rows


class TestF04:
    def test_positive_outlier_entity_z_score(self, mem_con):
        """One entity is ~100% direct-contracting while 9 similar-sized peers in the same
        department hover around 20-30% -> the outlier's z-score clears the 2.0 threshold."""
        rows = []
        peer_nits = []
        for i in range(9):
            nit = f"PEER{i}"
            peer_nits.append(nit)
            rows += _entity_contracts(nit, "11", n=10, direct_frac=0.2 + 0.02 * i)
        outlier_nit = "OUTLIER1"
        rows += _entity_contracts(outlier_nit, "11", n=10, direct_frac=1.0)

        make_fct_contrato(mem_con, rows)
        make_dim_entidad(
            mem_con,
            [{"nit_entidad_norm": nit, "cod_dpto": "11"} for nit in [*peer_nits, outlier_nit]],
        )

        out = f04.compute(mem_con)
        by_key = {r.key: r for r in out}
        assert outlier_nit in by_key
        assert by_key[outlier_nit].fired is True
        # peers with typical shares should not fire
        assert not any(by_key[n].fired for n in peer_nits if n in by_key)

    def test_negative_uniform_peer_group(self, mem_con):
        """All entities in the department behave similarly -> no z-score clears the threshold."""
        rows = []
        nits = []
        for i in range(8):
            nit = f"UNIFORM{i}"
            nits.append(nit)
            rows += _entity_contracts(nit, "05", n=10, direct_frac=0.3)
        make_fct_contrato(mem_con, rows)
        make_dim_entidad(mem_con, [{"nit_entidad_norm": nit, "cod_dpto": "05"} for nit in nits])

        out = f04.compute(mem_con)
        assert not any(r.fired for r in out)

    def test_edge_small_peer_group_excluded(self, mem_con):
        """A department with fewer than the minimum peer-group size is entirely excluded,
        even if one entity looks like an extreme outlier -- too few peers for a stable z-score."""
        rows = _entity_contracts("SOLO1", "94", n=10, direct_frac=1.0)
        rows += _entity_contracts("SOLO2", "94", n=10, direct_frac=0.1)
        make_fct_contrato(mem_con, rows)
        make_dim_entidad(mem_con, [{"nit_entidad_norm": "SOLO1", "cod_dpto": "94"}, {"nit_entidad_norm": "SOLO2", "cod_dpto": "94"}])

        out = f04.compute(mem_con)
        assert out == []

    def test_edge_entity_missing_department_excluded(self, mem_con):
        """An entity with no DIVIPOLA match (cod_dpto NULL) can't be assigned a peer group."""
        rows = _entity_contracts("NODPTO", None, n=10, direct_frac=1.0)
        make_fct_contrato(mem_con, rows)
        make_dim_entidad(mem_con, [{"nit_entidad_norm": "NODPTO", "cod_dpto": None}])

        out = f04.compute(mem_con)
        assert out == []
