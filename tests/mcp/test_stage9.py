"""Stage 9 MCP tests — promote_structure + knowledge evolution.

Tests for:
- promote_structure tool (error cases, auto-detect, no-relax)
- Knowledge schema evolution (last_validated, contradiction_count)
- Builtin.db expansion (35+ entries, new categories)
- InsightRecord dataclass

Shared fixtures (qms_project, etc.) are in conftest.py.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


# ===========================================================================
# promote_structure tests (no QE execution — error paths only)
# ===========================================================================


class TestPromoteStructure:
    """Tests for the promote_structure tool — error paths and validation.

    Real relax execution tests require QE and are covered separately.
    """

    def test_promote_no_relax_step_error(self, qms_project):
        """SCF-only calculation → error: no relax step."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.promote_structure import promote_structure

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = promote_structure.fn(calc_ulid=calc_ulid)
        assert result["status"] == "error"
        assert result["error_type"] == "no_relax_step"
        assert "relax" in result["message"].lower()

    def test_promote_invalid_calc_ulid(self, qms_project):
        """Non-existent calc → not_found error."""
        from qmatsuite.mcp.tools.promote_structure import promote_structure

        result = promote_structure.fn(calc_ulid="NONEXISTENT_ULID")
        assert result["status"] == "error"
        assert result["error_type"] == "not_found"

    def test_promote_invalid_step_index(self, qms_project):
        """Out-of-range step index → error."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.promote_structure import promote_structure

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = promote_structure.fn(calc_ulid=calc_ulid, step_index=99)
        assert result["status"] == "error"
        assert result["error_type"] == "invalid_step_index"

    def test_promote_step_not_relax_type(self, qms_project):
        """Explicitly selecting an SCF step → not_relax_step error."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.promote_structure import promote_structure

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = promote_structure.fn(calc_ulid=calc_ulid, step_index=0)
        assert result["status"] == "error"
        assert result["error_type"] == "not_relax_step"

    def test_promote_relax_step_not_run(self, qms_project):
        """Relax step that hasn't been executed → error about missing output."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.promote_structure import promote_structure

        calc = create_calculation.fn(
            engine="qe", workflow="relax", structure_selector="Silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        # Don't run the calculation — just try to promote
        result = promote_structure.fn(calc_ulid=calc_ulid)
        assert result["status"] == "error"
        # Should be either no_output or promote_failed
        assert result["error_type"] in ("no_output", "promote_failed", "not_relax_step")


# ===========================================================================
# Knowledge schema evolution tests
# ===========================================================================


class TestKnowledgeSchemaEvolution:
    """Tests for the updated knowledge schema with new columns."""

    def test_schema_has_last_validated(self, tmp_path):
        """The insights table has a last_validated column."""
        from qmatsuite.mcp.knowledge.schema import init_db

        db_path = tmp_path / "test_schema.db"
        conn = init_db(db_path)
        try:
            # Query table info
            cursor = conn.execute("PRAGMA table_info(insights)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "last_validated" in columns
        finally:
            conn.close()

    def test_schema_has_contradiction_count(self, tmp_path):
        """The insights table has contradiction_count with default 0."""
        from qmatsuite.mcp.knowledge.schema import init_db

        db_path = tmp_path / "test_schema.db"
        conn = init_db(db_path)
        try:
            cursor = conn.execute("PRAGMA table_info(insights)")
            col_info = {row[1]: row for row in cursor.fetchall()}
            assert "contradiction_count" in col_info
            # Check default value is 0
            default_val = col_info["contradiction_count"][4]  # dflt_value
            assert default_val == "0" or default_val == 0
        finally:
            conn.close()

    def test_existing_search_still_works(self, tmp_path):
        """Search works after schema evolution — no regression."""
        from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db
        from qmatsuite.mcp.knowledge.store import KnowledgeStore

        db_path = tmp_path / "test_search.db"
        build_builtin_db(db_path)

        store = KnowledgeStore(db_path)
        try:
            results = store.search("convergence")
            assert len(results) > 0
            # Results should have content
            assert all(r.get("content") for r in results)
        finally:
            store.close()

    def test_new_columns_populated_in_builtin(self, tmp_path):
        """Builtin entries have last_validated set and contradiction_count=0."""
        from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db

        db_path = tmp_path / "test_cols.db"
        build_builtin_db(db_path)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT last_validated, contradiction_count FROM insights LIMIT 1"
            ).fetchone()
            assert row is not None
            assert row["last_validated"] is not None  # Should be set to creation time
            assert row["contradiction_count"] == 0
        finally:
            conn.close()


# ===========================================================================
# Builtin expansion tests
# ===========================================================================


class TestBuiltinExpansion:
    """Tests for the expanded builtin knowledge base (35+ entries)."""

    def test_entry_count_at_least_35(self, tmp_path):
        """KnowledgeStore has at least 35 active entries."""
        from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db
        from qmatsuite.mcp.knowledge.store import KnowledgeStore

        db_path = tmp_path / "test_count.db"
        build_builtin_db(db_path)

        store = KnowledgeStore(db_path)
        try:
            count = store.count()
            assert count >= 35, f"Expected >= 35 entries, got {count}"
        finally:
            store.close()

    def test_methodology_entries_exist(self, tmp_path):
        """Entries tagged with 'methodology' or 'cross_engine' exist."""
        from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db
        from qmatsuite.mcp.knowledge.store import KnowledgeStore

        db_path = tmp_path / "test_meth.db"
        build_builtin_db(db_path)

        store = KnowledgeStore(db_path)
        try:
            results = store.search("methodology")
            assert len(results) > 0, "No methodology entries found"
        finally:
            store.close()

    def test_interpretation_entries_exist(self, tmp_path):
        """Entries about result interpretation exist."""
        from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db
        from qmatsuite.mcp.knowledge.store import KnowledgeStore

        db_path = tmp_path / "test_interp.db"
        build_builtin_db(db_path)

        store = KnowledgeStore(db_path)
        try:
            # Search for band gap interpretation
            results = store.search("band gap interpretation")
            assert len(results) > 0, "No interpretation entries found"
        finally:
            store.close()

    def test_workflow_sequence_entries_exist(self, tmp_path):
        """Entries about workflow sequencing (relax before bands, etc.) exist."""
        from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db
        from qmatsuite.mcp.knowledge.store import KnowledgeStore

        db_path = tmp_path / "test_wf.db"
        build_builtin_db(db_path)

        store = KnowledgeStore(db_path)
        try:
            results = store.search("relax before bands workflow")
            assert len(results) > 0, "No workflow sequencing entries found"
        finally:
            store.close()

    def test_no_duplicate_entry_ids(self, tmp_path):
        """All deterministic ULIDs are unique."""
        from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db

        db_path = tmp_path / "test_dedup.db"
        build_builtin_db(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute("SELECT id FROM insights").fetchall()
            ids = [r[0] for r in rows]
            assert len(ids) == len(set(ids)), "Duplicate IDs found"
        finally:
            conn.close()

    def test_builtin_entries_match_db(self, tmp_path):
        """Number of BUILTIN_ENTRIES matches DB count."""
        from qmatsuite.mcp.knowledge.builtin_entries import BUILTIN_ENTRIES
        from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db

        db_path = tmp_path / "test_match.db"
        build_builtin_db(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("SELECT COUNT(*) FROM insights").fetchone()
            assert row[0] == len(BUILTIN_ENTRIES)
        finally:
            conn.close()


# ===========================================================================
# InsightRecord tests
# ===========================================================================


class TestInsightRecord:
    """Tests for the InsightRecord dataclass."""

    def test_insight_record_fields(self):
        """InsightRecord has all required fields with correct defaults."""
        from qmatsuite.mcp.knowledge.insight_record import InsightRecord

        record = InsightRecord(content="Test insight")
        assert record.content == "Test insight"
        assert record.reasoning is None
        assert record.grade == "observation"
        assert record.scope == {}
        assert record.run_refs == []
        assert record.tags == []
        assert record.intent_id is None
        assert record.created_by == "agent"

    def test_insight_record_content_reasoning_separation(self):
        """content and reasoning are separate fields."""
        from qmatsuite.mcp.knowledge.insight_record import InsightRecord

        record = InsightRecord(
            content="PBE underestimates Si band gap",
            reasoning="Observed 0.6 eV vs 1.17 eV experimental across 5 runs",
            grade="finding",
            scope={"engine": "qe", "system_type": "semiconductor"},
            run_refs=["01ABC", "01DEF"],
            tags=["bandgap", "pbe"],
        )
        assert record.content != record.reasoning
        assert "PBE" in record.content
        assert "0.6 eV" in record.reasoning
        assert record.grade == "finding"
        assert record.scope["engine"] == "qe"
        assert len(record.run_refs) == 2
