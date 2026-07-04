"""
M2 unit tests: NIT/name normalization, modality mapping, quarantine logic, dedup.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from pipeline.clean.normalize import (
    is_persona_natural,
    normalize_doc,
    normalize_name,
)

# ---------------------------------------------------------------------------
# NIT / doc normalization
# ---------------------------------------------------------------------------

class TestNormalizeDoc:
    def test_nit_with_dots_and_hyphen(self):
        """'900.123.456-7' → doc_norm='9001234567', nit_base='900123456'"""
        r = normalize_doc("900.123.456-7")
        assert r["doc_norm"] == "9001234567"
        assert r["nit_base"] == "900123456"

    def test_nit_10digit_starting_8(self):
        """'8001234567' → nit_base = '800123456' (9 digits)"""
        r = normalize_doc("8001234567")
        assert r["doc_norm"] == "8001234567"
        assert r["nit_base"] == "800123456"

    def test_cedula_10digit_starting_1(self):
        """'1020304050' → nit_base = '1020304050' (full, not stripped)"""
        r = normalize_doc("1020304050")
        assert r["doc_norm"] == "1020304050"
        assert r["nit_base"] == "1020304050"

    def test_cedula_8digits(self):
        """'12345678' → nit_base = '12345678' (short cédula)"""
        r = normalize_doc("12345678")
        assert r["doc_norm"] == "12345678"
        assert r["nit_base"] == "12345678"

    def test_none_input(self):
        r = normalize_doc(None)
        assert r["doc_raw"] is None
        assert r["doc_norm"] is None
        assert r["nit_base"] is None

    def test_letters_only(self):
        r = normalize_doc("ABC")
        assert r["doc_norm"] is None

    def test_mixed(self):
        """'NIT: 800.234.517-3' → digits='8002345173', nit_base='800234517'"""
        r = normalize_doc("NIT: 800.234.517-3")
        assert r["doc_norm"] == "8002345173"
        assert r["nit_base"] == "800234517"

    def test_9digit_starting_9(self):
        """9-digit NIT without check digit → entity"""
        r = normalize_doc("900000001")
        assert r["doc_norm"] == "900000001"
        assert r["nit_base"] == "900000001"


class TestIsPersonaNatural:
    def test_short_cedula(self):
        assert is_persona_natural("12345678") is True

    def test_nit_10_starts_8(self):
        assert is_persona_natural("8001234567") is False

    def test_nit_10_starts_9(self):
        assert is_persona_natural("9001234567") is False

    def test_cedula_10_starts_1(self):
        assert is_persona_natural("1020304050") is True

    def test_nit_9_starts_9(self):
        assert is_persona_natural("900000001") is False

    def test_none(self):
        assert is_persona_natural(None) is None

    def test_empty(self):
        assert is_persona_natural("") is None

    def test_7digits(self):
        assert is_persona_natural("1234567") is True


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

class TestNormalizeName:
    def test_strips_sas(self):
        assert normalize_name("Empresa XYZ S.A.S.") == "EMPRESA XYZ"

    def test_strips_sa(self):
        assert normalize_name("Banco Bogotá S.A.") == "BANCO BOGOTA"

    def test_strips_ltda(self):
        assert normalize_name("Transportes del Sur LTDA") == "TRANSPORTES DEL SUR"

    def test_strips_accents(self):
        assert normalize_name("Construcción & Asociados") == "CONSTRUCCION & ASOCIADOS"

    def test_strips_eu(self):
        assert normalize_name("Soluciones Tech E.U.") == "SOLUCIONES TECH"

    def test_strips_s_en_c(self):
        assert normalize_name("Comercios S EN C") == "COMERCIOS"

    def test_none(self):
        assert normalize_name(None) is None

    def test_empty(self):
        assert normalize_name("") is None

    def test_collapses_whitespace(self):
        assert normalize_name("  Empresa   S.A.S  ") == "EMPRESA"

    def test_no_suffix(self):
        assert normalize_name("EMPRESA XYZ") == "EMPRESA XYZ"


# ---------------------------------------------------------------------------
# Modality mapping completeness
# ---------------------------------------------------------------------------

class TestModalidadMapping:
    """Every distinct raw modality in the sample must map to a known norm."""

    EXPECTED_NORMS = {
        "LICITACION_PUBLICA",
        "SELECCION_ABREVIADA",
        "CONCURSO_MERITOS",
        "CONTRATACION_DIRECTA",
        "MINIMA_CUANTIA",
        "REGIMEN_ESPECIAL",
        "OTRO",
    }

    def test_all_modalities_map(self):
        refs_dir = Path(__file__).parents[1] / "src/pipeline/refs/modalidades.csv"
        db = duckdb.connect()
        rows = db.execute(
            f"SELECT raw_value, modalidad_norm FROM read_csv('{refs_dir}', header=true)"
        ).fetchall()
        assert len(rows) > 0, "modalidades.csv is empty"
        for raw, norm in rows:
            assert norm in self.EXPECTED_NORMS, (
                f"Unknown modalidad_norm '{norm}' for raw '{raw}'"
            )

    def test_sample_s1_modalities_covered(self):
        """All S1 sample modalities must be in modalidades.csv."""
        raw_dir = Path(__file__).parents[1] / "data/raw/sample"
        refs_dir = Path(__file__).parents[1] / "src/pipeline/refs/modalidades.csv"
        if not raw_dir.exists():
            pytest.skip("Sample data not available")

        db = duckdb.connect()
        refs = {
            r[0] for r in db.execute(
                f"SELECT raw_value FROM read_csv('{refs_dir}', header=true)"
            ).fetchall()
        }
        sample_mods = {
            r[0] for r in db.execute(f"""
                SELECT DISTINCT modalidad_de_contratacion
                FROM read_parquet('{raw_dir}/s1_secop2_contratos/part-*.parquet', union_by_name=true)
                WHERE modalidad_de_contratacion IS NOT NULL
            """).fetchall()
        }
        unmapped = sample_mods - refs
        assert not unmapped, f"S1 modalities not in CSV: {unmapped}"

    def test_sample_s2_modalities_covered(self):
        """All S2 sample modalities must be in modalidades.csv."""
        raw_dir = Path(__file__).parents[1] / "data/raw/sample"
        refs_dir = Path(__file__).parents[1] / "src/pipeline/refs/modalidades.csv"
        if not raw_dir.exists():
            pytest.skip("Sample data not available")

        db = duckdb.connect()
        refs = {
            r[0] for r in db.execute(
                f"SELECT raw_value FROM read_csv('{refs_dir}', header=true)"
            ).fetchall()
        }
        sample_mods = {
            r[0] for r in db.execute(f"""
                SELECT DISTINCT modalidad_de_contratacion
                FROM read_parquet('{raw_dir}/s2_secop2_procesos/part-*.parquet', union_by_name=true)
                WHERE modalidad_de_contratacion IS NOT NULL
            """).fetchall()
        }
        unmapped = sample_mods - refs
        assert not unmapped, f"S2 modalities not in CSV: {unmapped}"


# ---------------------------------------------------------------------------
# Quarantine logic on synthetic fixture
# ---------------------------------------------------------------------------

class TestQuarantineLogic:
    """Test that rows with bad valor or bad fecha go to quarantine."""

    def test_bad_valor_quarantined(self):
        db = duckdb.connect()
        db.execute("""
            CREATE TABLE synthetic_s1 (
                ":id" VARCHAR,
                valor_del_contrato VARCHAR,
                fecha_de_firma VARCHAR
            )
        """)
        db.execute("""
            INSERT INTO synthetic_s1 VALUES
                ('row1', '1000000', '2023-01-15'),      -- good
                ('row2', 'INVALID', '2023-01-16'),       -- bad valor
                ('row3', '2000000', 'NOT-A-DATE'),        -- bad fecha
                ('row4', '3000000', '2023-03-01')        -- good
        """)
        db.execute("CREATE TABLE quarantine (source VARCHAR, row_id VARCHAR, reason VARCHAR, raw_valor VARCHAR, raw_fecha VARCHAR)")

        # Replicate quarantine logic
        db.execute("""
            INSERT INTO quarantine
            SELECT
                'S1',
                ":id",
                CASE
                    WHEN TRY_CAST(valor_del_contrato AS DOUBLE) IS NULL
                         AND valor_del_contrato IS NOT NULL
                         AND trim(valor_del_contrato) != ''
                    THEN 'bad_valor_del_contrato'
                    WHEN TRY_CAST(fecha_de_firma AS DATE) IS NULL
                         AND fecha_de_firma IS NOT NULL
                         AND trim(fecha_de_firma) != ''
                    THEN 'bad_fecha_de_firma'
                    ELSE NULL
                END AS reason,
                valor_del_contrato,
                fecha_de_firma
            FROM synthetic_s1
            WHERE (
                (TRY_CAST(valor_del_contrato AS DOUBLE) IS NULL
                    AND valor_del_contrato IS NOT NULL
                    AND trim(valor_del_contrato) != '')
                OR
                (TRY_CAST(fecha_de_firma AS DATE) IS NULL
                    AND fecha_de_firma IS NOT NULL
                    AND trim(fecha_de_firma) != '')
            )
        """)

        n_q = db.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        assert n_q == 2, f"Expected 2 quarantine rows, got {n_q}"

        reasons = {r[0] for r in db.execute("SELECT reason FROM quarantine").fetchall()}
        assert "bad_valor_del_contrato" in reasons
        assert "bad_fecha_de_firma" in reasons

    def test_good_rows_pass(self):
        db = duckdb.connect()
        db.execute("""
            CREATE TABLE synth_good (
                ":id" VARCHAR,
                valor_del_contrato VARCHAR,
                fecha_de_firma VARCHAR
            )
        """)
        db.execute("""
            INSERT INTO synth_good VALUES
                ('r1', '500000', '2023-06-01'),
                ('r2', '750000.50', '2023-12-31')
        """)
        db.execute("CREATE TABLE q2 (source VARCHAR, row_id VARCHAR, reason VARCHAR, raw_valor VARCHAR, raw_fecha VARCHAR)")
        db.execute("""
            INSERT INTO q2
            SELECT 'S1', ":id", NULL, valor_del_contrato, fecha_de_firma
            FROM synth_good
            WHERE (TRY_CAST(valor_del_contrato AS DOUBLE) IS NULL
                    AND valor_del_contrato IS NOT NULL AND trim(valor_del_contrato) != '')
               OR (TRY_CAST(fecha_de_firma AS DATE) IS NULL
                    AND fecha_de_firma IS NOT NULL AND trim(fecha_de_firma) != '')
        """)
        n_q = db.execute("SELECT COUNT(*) FROM q2").fetchone()[0]
        assert n_q == 0, "No rows should be quarantined"


# ---------------------------------------------------------------------------
# Dedup keep-latest logic
# ---------------------------------------------------------------------------

class TestDedupLogic:
    """Dedup: highest-numbered part file wins for same :id."""

    def _make_db_with_parts(self, tmp_path: Path) -> tuple[Path, Path]:
        import pyarrow as pa
        import pyarrow.parquet as pq

        schema = pa.schema([
            (":id", pa.string()),
            ("valor_del_contrato", pa.string()),
            ("nombre_entidad", pa.string()),
        ])
        # Part 0: row1=100, row2=200
        t0 = pa.table(
            {":id": ["row1", "row2"], "valor_del_contrato": ["100", "200"], "nombre_entidad": ["E1", "E2"]},
            schema=schema,
        )
        # Part 1 (higher): row1 is updated to 999, row2 unchanged
        t1 = pa.table(
            {":id": ["row1"], "valor_del_contrato": ["999"], "nombre_entidad": ["E1_updated"]},
            schema=schema,
        )
        p0 = tmp_path / "part-00000.parquet"
        p1 = tmp_path / "part-00001.parquet"
        pq.write_table(t0, p0)
        pq.write_table(t1, p1)
        return p0, p1

    def test_dedup_keeps_latest_part(self, tmp_path):
        p0, p1 = self._make_db_with_parts(tmp_path)
        db = duckdb.connect()

        result = db.execute(f"""
            WITH raw AS (
                SELECT *, filename
                FROM read_parquet('{tmp_path}/part-*.parquet', union_by_name=true, filename=true)
            ),
            deduped AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY ":id"
                        ORDER BY filename DESC
                    ) AS rn
                FROM raw
            )
            SELECT ":id", valor_del_contrato, nombre_entidad
            FROM deduped WHERE rn = 1
            ORDER BY ":id"
        """).fetchall()

        assert len(result) == 2, f"Expected 2 rows, got {len(result)}"
        row1 = next(r for r in result if r[0] == "row1")
        assert row1[1] == "999", f"Expected '999' (from part-00001), got {row1[1]}"
        assert row1[2] == "E1_updated"

        row2 = next(r for r in result if r[0] == "row2")
        assert row2[1] == "200"
