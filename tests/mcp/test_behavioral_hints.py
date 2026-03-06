"""Tests for pre-experiment behavioral hints (M1-M6).

Verify that context_hints guide agents toward proper insight recording:
recording failures, recording multiple insights per session, searching
knowledge before configuring, and not prefixing search results.
"""

from __future__ import annotations

import pytest

from qmatsuite.mcp.knowledge.schema import init_db
from qmatsuite.mcp.knowledge.store import KnowledgeStore, _CONTRADICTION_THRESHOLD


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def _patch_knowledge(tmp_path, monkeypatch):
    """Patch knowledge store to use isolated temp DBs."""
    local_db = tmp_path / "knowledge" / "local.db"
    builtin_db = tmp_path / "knowledge" / "builtin.db"
    init_db(builtin_db)  # empty but valid

    store = KnowledgeStore(db_path=builtin_db, local_db_path=local_db)

    import qmatsuite.mcp.knowledge as km
    monkeypatch.setattr(km, "_store", store)
    yield store
    store.close()


@pytest.fixture
def _patch_journal(tmp_path, monkeypatch):
    """Patch journal for isolation."""
    from qmatsuite.core.journal import Journal, set_journal, reset_journal

    journal = Journal(journal_dir=tmp_path / "journal")
    set_journal(journal)
    yield
    reset_journal()


# ===========================================================================
# M1: Error enrichment should prompt recording the failure
# ===========================================================================

class TestM1ErrorHintMentionsRecordInsight:
    """M1: Error enrichment context_hint must mention record_insight."""

    def test_error_hint_mentions_record_insight(self):
        """The error enrichment hint should prompt the agent to record the failure."""
        from qmatsuite.mcp.error_enrichment import enrich_run_error

        # Create a minimal mock result_dto
        class _Step:
            step_type_gen = "scf"
            message = "SCF did not converge"
            status = "failed"

        class _DTO:
            calc_ulid = "01TESTCALC"
            run_ulid = "01TESTRUN"
            status = "failed"
            exit_code = 1
            steps = [_Step()]

        result = enrich_run_error(
            calc_ulid="01TESTCALC",
            result_dto=_DTO(),
            digest={"converged": False, "n_iterations": 100},
            engine="qe",
            workflow="scf",
        )
        hint = result.get("context_hint", "")
        assert "record_insight" in hint, (
            "Error enrichment hint must mention record_insight so agents record failures"
        )
        assert "error-recovery" in hint, (
            "Error enrichment hint should suggest 'error-recovery' tag"
        )


# ===========================================================================
# M2: After recording a finding, hint should encourage additional insights
# ===========================================================================

class TestM2RecordInsightHintEncouragesMore:
    """M2: After recording a finding, context_hint must encourage more insights."""

    @pytest.fixture(autouse=True)
    def _setup(self, _patch_knowledge, _patch_journal):
        pass

    def test_promoted_hint_encourages_additional(self):
        """After recording a finding, hint should mention 'additional' or 'separate'."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        result = record_insight.fn(
            content="Test finding for hint check",
            grade="finding",
        )
        assert result["status"] == "success"
        hint = result.get("context_hint", "")
        assert "additional" in hint.lower() or "separate" in hint.lower(), (
            f"Promoted insight hint must encourage additional insights, got: {hint!r}"
        )

    def test_promoted_hint_not_termination_signal(self):
        """After recording, hint must NOT be the old 'verify it's findable' dead-end."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        result = record_insight.fn(
            content="Test finding for termination check",
            grade="finding",
        )
        hint = result.get("context_hint", "")
        assert "verify it's findable" not in hint.lower(), (
            f"Promoted insight hint must not contain old termination signal, got: {hint!r}"
        )


# ===========================================================================
# M3: Preamble finding definition includes methodology
# ===========================================================================

class TestM3PreambleFindingDefinition:
    """M3: Preamble should mention methodology lessons in finding definition."""

    def test_finding_grade_includes_methodology(self):
        """The 'finding' grade definition must mention methodology or failure."""
        from qmatsuite.mcp.app import _MCP_INSTRUCTIONS

        # Find the line(s) defining 'finding'
        lines = _MCP_INSTRUCTIONS.split("\n")
        finding_lines = [
            l for l in lines if "finding" in l.lower() and "→" in l
        ]
        assert len(finding_lines) >= 1, "Preamble must define the 'finding' grade"
        finding_text = " ".join(finding_lines)
        assert "methodology" in finding_text.lower() or "failure" in finding_text.lower(), (
            f"Finding definition must mention methodology or failure, got: {finding_text!r}"
        )


# ===========================================================================
# M4b: Search results should not prefix content with [UNDER REVIEW]
# ===========================================================================

class TestM4bNoUnderReviewPrefix:
    """M4b: Search results must not prefix content with [UNDER REVIEW]."""

    @pytest.fixture(autouse=True)
    def _setup(self, _patch_knowledge):
        self._store = _patch_knowledge

    def test_search_results_no_under_review_prefix(self):
        """Entries with high contradiction_count must not get [UNDER REVIEW] prefix."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        self._store.local_conn.execute(
            """
            INSERT INTO insights (
                id, grade, scope_engine, scope_workflow, scope_system_type, scope_method,
                content, confidence, source_type, created_by, tags,
                status, contradiction_count, upvotes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                "M4BTEST01", "finding", "*", "*", "*", "*",
                "GaAs lattice constant is 5.743 angstrom",
                "medium", "local", "agent", "[]",
                "active", _CONTRADICTION_THRESHOLD, now, now,
            ),
        )
        self._store.local_conn.commit()

        results = self._store.search("GaAs lattice")
        matched = [r for r in results if r.get("id") == "M4BTEST01"]
        assert len(matched) == 1
        content = matched[0]["content"]
        assert not content.startswith("[UNDER REVIEW]"), (
            f"Search results must not prefix content, got: {content!r}"
        )
        assert content == "GaAs lattice constant is 5.743 angstrom"


# ===========================================================================
# M5: Preamble mentions multiple insights per session
# ===========================================================================

class TestM5PreambleMultipleInsights:
    """M5: Preamble should mention separate insights per session."""

    def test_preamble_mentions_separate_insights(self):
        """Preamble must mention that a session may produce multiple insights."""
        from qmatsuite.mcp.app import _MCP_INSTRUCTIONS

        text = _MCP_INSTRUCTIONS.lower()
        assert "separate insight" in text or "one or several" in text, (
            "Preamble must mention separate/multiple insights per session"
        )

    def test_preamble_mentions_methodology_lesson(self):
        """Preamble must mention methodology lessons as valid insight content."""
        from qmatsuite.mcp.app import _MCP_INSTRUCTIONS

        text = _MCP_INSTRUCTIONS.lower()
        assert "methodology lesson" in text or "methodology" in text, (
            "Preamble must mention methodology lessons"
        )


# ===========================================================================
# M6: create_calculation should remind agent to search knowledge
# ===========================================================================

class TestM6CreateCalculationSearchHint:
    """M6: create_calculation context_hint must mention search_knowledge."""

    def test_create_calculation_hint_mentions_search(self, qms_project):
        """After creating a calculation, hint should mention search_knowledge."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation

        result = create_calculation.fn(
            engine="qe",
            workflow="scf",
            structure_selector="Silicon",
        )
        assert result["status"] == "success", f"create_calculation failed: {result}"
        hint = result.get("context_hint", "")
        assert "search_knowledge" in hint, (
            f"create_calculation hint must mention search_knowledge, got: {hint!r}"
        )
