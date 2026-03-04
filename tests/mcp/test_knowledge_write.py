"""Tests for the knowledge write path: add(), multi-DB search, trust weights,
contradiction detection, record_insight, and record_intent MCP tools.

All tests use tmp_path fixtures for isolated DB paths.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qmatsuite.mcp.knowledge.schema import init_db
from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db
from qmatsuite.mcp.knowledge.store import (
    KnowledgeStore,
    TRUST_WEIGHTS,
    _DEFAULT_TRUST,
    _CONTRADICTION_THRESHOLD,
    _GRADE_ORDER,
    LOCAL_RESERVED_SLOTS,
    _merge_with_reserved_slots,
    _builtin_enabled,
)
from qmatsuite.mcp.knowledge.insight_record import InsightRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    content: str = "Test insight content for FTS matching",
    grade: str = "finding",
    scope: dict | None = None,
    tags: list[str] | None = None,
) -> InsightRecord:
    return InsightRecord(
        content=content,
        grade=grade,
        scope=scope or {},
        tags=tags or [],
        created_by="agent",
    )


def _insert_entry(
    conn,
    content: str,
    entry_id: str = "TEST001",
    grade: str = "finding",
    scope_engine: str = "*",
    scope_workflow: str = "*",
    scope_system_type: str = "*",
    scope_method: str = "*",
    source_type: str = "builtin",
    confidence: str = "medium",
    contradiction_count: int = 0,
    status: str = "active",
):
    """Insert a test entry directly into a DB connection."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO insights (
            id, grade, scope_engine, scope_workflow, scope_system_type, scope_method,
            content, confidence, source_type, created_by, tags,
            status, contradiction_count, upvotes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            entry_id, grade, scope_engine, scope_workflow, scope_system_type,
            scope_method, content, confidence, source_type, "test", "[]",
            status, contradiction_count, now, now,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def builtin_db(tmp_path):
    """Return path to an empty builtin.db with schema initialized."""
    p = tmp_path / "knowledge" / "builtin.db"
    init_db(p)
    return p


@pytest.fixture
def local_db_path(tmp_path):
    """Return path for local.db (file NOT created yet — lazily on write)."""
    return tmp_path / "knowledge" / "local.db"


@pytest.fixture
def store(builtin_db, local_db_path):
    """Return a KnowledgeStore with both builtin and local DB paths."""
    s = KnowledgeStore(db_path=builtin_db, local_db_path=local_db_path)
    yield s
    s.close()


@pytest.fixture
def populated_builtin(tmp_path):
    """Return path to a builtin.db populated with BUILTIN_ENTRIES."""
    p = tmp_path / "knowledge" / "builtin.db"
    build_builtin_db(output_path=p)
    return p


@pytest.fixture
def populated_store(populated_builtin, local_db_path):
    """Return a store with populated builtin.db and a local_db_path."""
    s = KnowledgeStore(db_path=populated_builtin, local_db_path=local_db_path)
    yield s
    s.close()


# ===========================================================================
# TestKnowledgeStoreAdd (8 tests)
# ===========================================================================

class TestKnowledgeStoreAdd:
    def test_add_finding_writes_to_local_db(self, store, local_db_path):
        """A finding grade is written to local.db."""
        record = _make_record(grade="finding")
        result = store.add(record)
        assert result["promoted"] is True
        assert result["insight_id"] is not None
        assert local_db_path.exists()

    def test_add_principle_writes_to_local_db(self, store, local_db_path):
        """A principle grade is written to local.db."""
        record = _make_record(grade="principle")
        result = store.add(record)
        assert result["promoted"] is True
        assert result["insight_id"] is not None

    def test_add_observation_not_promoted(self, store, local_db_path):
        """An observation is not promoted to the knowledge DB."""
        record = _make_record(grade="observation")
        result = store.add(record)
        assert result["promoted"] is False
        assert result["insight_id"] is None
        assert not local_db_path.exists()

    def test_add_bookkeeping_not_promoted(self, store, local_db_path):
        """Bookkeeping is not promoted to the knowledge DB."""
        record = _make_record(grade="bookkeeping")
        result = store.add(record)
        assert result["promoted"] is False
        assert not local_db_path.exists()

    def test_add_invalid_grade_raises(self, store):
        """Invalid grade raises ValueError."""
        record = _make_record(grade="invalid")
        with pytest.raises(ValueError, match="Invalid grade"):
            store.add(record)

    def test_add_empty_content_raises(self, store):
        """Empty content raises ValueError."""
        record = _make_record(content="")
        with pytest.raises(ValueError, match="Content must be non-empty"):
            store.add(record)

    def test_local_db_created_on_first_write(self, store, local_db_path):
        """local.db file is created on first write, not before."""
        assert not local_db_path.exists()
        store.add(_make_record(grade="finding"))
        assert local_db_path.exists()

    def test_local_does_not_pollute_builtin(self, store, builtin_db):
        """Writes to local.db do not appear in builtin.db."""
        store.add(_make_record(content="unique local content xyz", grade="finding"))
        import sqlite3
        conn = sqlite3.connect(str(builtin_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT COUNT(*) FROM insights WHERE content LIKE '%unique local content xyz%'"
        ).fetchone()
        assert row[0] == 0
        conn.close()


# ===========================================================================
# TestMultiDBSearch (4 tests)
# ===========================================================================

class TestMultiDBSearch:
    def test_search_returns_both_builtin_and_local(self, store, builtin_db):
        """Search merges results from both builtin and local DBs."""
        # Add an entry to builtin
        _insert_entry(
            store.conn,
            content="Builtin SCF convergence tip for testing multi-DB search",
            entry_id="BUILTIN001",
            source_type="builtin",
        )
        # Add a finding to local
        store.add(_make_record(
            content="Local SCF convergence finding for testing multi-DB search",
            grade="finding",
        ))
        results = store.search("SCF convergence multi DB search")
        contents = [r["content"] for r in results]
        assert any("Builtin" in c for c in contents)
        assert any("Local" in c for c in contents)

    def test_local_entries_findable_via_fts(self, store):
        """A locally added finding is findable via FTS search."""
        store.add(_make_record(
            content="Unique xylophone convergence finding",
            grade="finding",
        ))
        results = store.search("xylophone convergence")
        assert len(results) >= 1
        assert any("xylophone" in r["content"] for r in results)

    def test_search_without_local_db_works(self, builtin_db, tmp_path):
        """Search works gracefully when no local.db exists."""
        nonexistent = tmp_path / "knowledge" / "nonexistent_local.db"
        s = KnowledgeStore(db_path=builtin_db, local_db_path=nonexistent)
        try:
            _insert_entry(s.conn, content="Builtin entry for search test", entry_id="B1")
            results = s.search("Builtin entry search")
            assert len(results) >= 1
        finally:
            s.close()

    def test_cross_session_persistence(self, builtin_db, local_db_path):
        """Write a finding, close store, reopen, and find it."""
        s1 = KnowledgeStore(db_path=builtin_db, local_db_path=local_db_path)
        s1.add(_make_record(
            content="Persistent xylophone cross session finding",
            grade="finding",
        ))
        s1.close()

        # New store instance at same paths
        s2 = KnowledgeStore(db_path=builtin_db, local_db_path=local_db_path)
        try:
            results = s2.search("Persistent xylophone cross session")
            assert len(results) >= 1
            assert any("Persistent" in r["content"] for r in results)
        finally:
            s2.close()


# ===========================================================================
# TestTrustWeights (3 tests)
# ===========================================================================

class TestTrustWeights:
    def test_trust_weight_affects_ranking(self, store):
        """Entries with higher trust weight rank above lower ones."""
        # Insert a builtin entry (trust 1.0) and a community entry (trust 0.6)
        _insert_entry(
            store.conn,
            content="SCF convergence tip from builtin source for ranking test",
            entry_id="TW_BUILTIN",
            source_type="builtin",
            confidence="medium",
        )
        _insert_entry(
            store.conn,
            content="SCF convergence tip from community source for ranking test",
            entry_id="TW_COMMUNITY",
            source_type="community",
            confidence="medium",
        )
        results = store.search("SCF convergence ranking test")
        if len(results) >= 2:
            ids = [r["id"] for r in results]
            # Builtin (trust=1.0) should rank above community (trust=0.6)
            if "TW_BUILTIN" in ids and "TW_COMMUNITY" in ids:
                assert ids.index("TW_BUILTIN") < ids.index("TW_COMMUNITY")

    def test_builtin_and_local_equal_trust(self):
        """Builtin and local have the same trust weight."""
        assert TRUST_WEIGHTS["builtin"] == TRUST_WEIGHTS["local"]

    def test_unknown_source_type_gets_default(self):
        """An unknown source_type falls back to _DEFAULT_TRUST."""
        assert TRUST_WEIGHTS.get("alien_source") is None
        assert _DEFAULT_TRUST == 0.5


# ===========================================================================
# TestContradictionDetection (5 tests)
# ===========================================================================

class TestContradictionDetection:
    def test_contradiction_increments_count(self, store):
        """Adding a finding with matching scope increments contradiction_count."""
        # Seed an existing entry in builtin with scope_engine=qe
        _insert_entry(
            store.conn,
            content="QE SCF convergence tip for contradiction test",
            entry_id="CONTRA001",
            scope_engine="qe",
        )
        # Add a local finding with the same scope
        store.add(_make_record(
            content="Contradicting QE SCF convergence finding",
            grade="finding",
            scope={"engine": "qe"},
        ))
        # Check that CONTRA001's count was incremented
        row = store.conn.execute(
            "SELECT contradiction_count FROM insights WHERE id = 'CONTRA001'"
        ).fetchone()
        assert row[0] == 1

    def test_contradiction_threshold_flags_review(self, store):
        """Reaching the contradiction threshold sets status to under_review."""
        _insert_entry(
            store.conn,
            content="QE SCF tip that will be flagged for contradiction review",
            entry_id="REVIEW001",
            scope_engine="qe",
            contradiction_count=_CONTRADICTION_THRESHOLD - 1,
        )
        store.add(_make_record(
            content="Another QE SCF finding triggering review",
            grade="finding",
            scope={"engine": "qe"},
        ))
        row = store.conn.execute(
            "SELECT status, contradiction_count FROM insights WHERE id = 'REVIEW001'"
        ).fetchone()
        assert row[0] == "under_review"
        assert row[1] == _CONTRADICTION_THRESHOLD

    def test_no_contradiction_for_different_scope(self, store):
        """Entries with different non-wildcard scope don't contradict."""
        _insert_entry(
            store.conn,
            content="VASP tip that should not be contradicted by QE finding",
            entry_id="DIFF001",
            scope_engine="vasp",
        )
        result = store.add(_make_record(
            content="QE finding with different engine scope",
            grade="finding",
            scope={"engine": "qe"},
        ))
        # DIFF001 should not be in contradictions
        contra_ids = [c["id"] for c in result["contradictions"]]
        assert "DIFF001" not in contra_ids
        row = store.conn.execute(
            "SELECT contradiction_count FROM insights WHERE id = 'DIFF001'"
        ).fetchone()
        assert row[0] == 0

    def test_wildcard_scope_not_matched_as_contradiction(self, store):
        """A wildcard scope_engine='*' entry is NOT contradicted by engine-specific findings."""
        _insert_entry(
            store.conn,
            content="Universal principle that applies to all engines",
            entry_id="WILD001",
            scope_engine="*",
        )
        result = store.add(_make_record(
            content="QE-specific finding should not contradict wildcard",
            grade="finding",
            scope={"engine": "qe"},
        ))
        contra_ids = [c["id"] for c in result["contradictions"]]
        assert "WILD001" not in contra_ids
        row = store.conn.execute(
            "SELECT contradiction_count FROM insights WHERE id = 'WILD001'"
        ).fetchone()
        assert row[0] == 0

    def test_search_annotates_under_review(self, store):
        """Entries with contradiction_count >= threshold show [UNDER REVIEW] prefix."""
        _insert_entry(
            store.conn,
            content="Entry that is under review for contradictions",
            entry_id="UR001",
            contradiction_count=_CONTRADICTION_THRESHOLD,
            status="active",
        )
        results = store.search("under review contradictions")
        matched = [r for r in results if "UR001" == r.get("id")]
        assert len(matched) == 1
        assert matched[0]["content"].startswith("[UNDER REVIEW]")


# ===========================================================================
# TestRecordInsightTool (6 tests)
# ===========================================================================

class TestRecordInsightTool:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        """Patch the knowledge store singleton and journal for isolation."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod, "_store", store)

        # Patch journal to use tmp_path
        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal")
        set_journal(journal)
        self._journal = journal
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_finding_writes_to_knowledge(self):
        """A finding is promoted to the knowledge DB."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        result = record_insight.fn(
            content="Test finding for knowledge write",
            grade="finding",
            scope_engine="qe",
        )
        assert result["status"] == "success"
        assert result["data"]["promoted"] is True
        assert result["data"]["insight_id"] is not None
        assert result["data"]["journal_recorded"] is True

    def test_observation_journal_only(self):
        """An observation is recorded in journal but not promoted."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        result = record_insight.fn(
            content="Test observation for journal only",
            grade="observation",
        )
        assert result["status"] == "success"
        assert result["data"]["promoted"] is False
        assert result["data"]["insight_id"] is None
        assert result["data"]["journal_recorded"] is True

    def test_returns_contradiction_warning(self, store):
        """Contradictions are reported in the response."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        # Seed a builtin entry
        _insert_entry(
            store.conn,
            content="QE convergence tip seeded for contradiction",
            entry_id="TOOL_CONTRA",
            scope_engine="qe",
        )
        result = record_insight.fn(
            content="Contradicting QE convergence finding from tool",
            grade="finding",
            scope_engine="qe",
        )
        assert result["status"] == "success"
        assert len(result["data"]["contradictions"]) > 0

    def test_invalid_grade_returns_error(self):
        """Invalid grade returns an error envelope, not an exception."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        result = record_insight.fn(content="test", grade="legendary")
        assert result["status"] == "error"
        assert result["error_type"] == "VALIDATION_ERROR"

    def test_empty_content_returns_error(self):
        """Empty content returns an error envelope."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        result = record_insight.fn(content="", grade="observation")
        assert result["status"] == "error"
        assert result["error_type"] == "VALIDATION_ERROR"

    def test_envelope_structure(self):
        """Response has standard envelope fields."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        result = record_insight.fn(
            content="Envelope structure test insight",
            grade="finding",
        )
        assert "status" in result
        assert "data" in result
        assert "context_hint" in result
        data = result["data"]
        assert "insight_id" in data
        assert "promoted" in data
        assert "journal_recorded" in data
        assert "contradictions" in data
        assert "grade" in data


# ===========================================================================
# TestRecordIntentTool (4 tests)
# ===========================================================================

class TestRecordIntentTool:
    @pytest.fixture(autouse=True)
    def _patch_journal(self, tmp_path, monkeypatch):
        """Patch journal for isolation."""
        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal")
        set_journal(journal)
        self._journal = journal
        yield
        reset_journal()

    def test_writes_to_journal(self):
        """Intent is recorded in the journal."""
        from qmatsuite.mcp.tools.record_intent import record_intent

        result = record_intent.fn(intent="Run SCF calculation for Si")
        assert result["status"] == "success"
        entries = self._journal.list_entries()
        assert len(entries) >= 1
        assert "Agent intent:" in entries[0].summary

    def test_returns_intent_id(self):
        """Response includes an intent_id (journal entry ULID)."""
        from qmatsuite.mcp.tools.record_intent import record_intent

        result = record_intent.fn(intent="Plan convergence test")
        assert result["status"] == "success"
        assert result["data"]["intent_id"] is not None
        assert len(result["data"]["intent_id"]) > 0

    def test_empty_intent_returns_error(self):
        """Empty intent returns an error envelope."""
        from qmatsuite.mcp.tools.record_intent import record_intent

        result = record_intent.fn(intent="")
        assert result["status"] == "error"
        assert result["error_type"] == "VALIDATION_ERROR"

    def test_envelope_structure(self):
        """Response has standard envelope fields."""
        from qmatsuite.mcp.tools.record_intent import record_intent

        result = record_intent.fn(
            intent="Test intent for envelope structure",
            calc_ulid="01EXAMPLE",
            tags="tag1,tag2",
        )
        assert "status" in result
        assert "data" in result
        assert "context_hint" in result
        data = result["data"]
        assert "intent_id" in data
        assert "intent" in data
        assert data["calc_ulid"] == "01EXAMPLE"
        assert data["tags"] == ["tag1", "tag2"]


# ===========================================================================
# TestFTS5OrJoin — regression tests for the implicit-AND bug (Task 2.2b)
# ===========================================================================

class TestFTS5OrJoin:
    """FTS5 multi-word queries must use OR-join so partial matches are returned.

    Prior to the fix, ``_sanitize_fts_query()`` joined tokens with spaces,
    which FTS5 interpreted as implicit AND.  Multi-word queries like
    ``"BN band structure band gap"`` required ALL tokens in a single row,
    returning 0 hits.
    """

    def test_multiword_query_returns_results(self, store):
        """Multi-word queries must not require ALL tokens (regression)."""
        store.add(_make_record(
            content="PBE lattice constant for cubic BN zinc blende a0 3.622",
            grade="finding",
            scope={"engine": "qe", "workflow": "relax"},
        ))
        results = store.search("BN band structure band gap")
        assert len(results) >= 1
        assert any("BN" in r["content"] for r in results)

    def test_long_query_returns_results(self, store):
        """Long queries with many tokens still return relevant results."""
        store.add(_make_record(
            content="Lattice constant optimization using equation of state fitting",
            grade="finding",
            scope={"engine": "qe"},
        ))
        results = store.search("lattice constant optimization equation of state")
        assert len(results) >= 1

    def test_single_token_still_works(self, store):
        """Single-token queries still work after the OR-join fix."""
        store.add(_make_record(
            content="Unique zirconium convergence insight for single token test",
            grade="finding",
        ))
        results = store.search("zirconium")
        assert len(results) >= 1
        assert any("zirconium" in r["content"] for r in results)

    def test_two_token_query_returns_results(self, store):
        """Two-token queries work with OR-join."""
        store.add(_make_record(
            content="GaAs lattice constant from vc-relax calculation",
            grade="finding",
            scope={"engine": "qe"},
        ))
        results = store.search("GaAs lattice")
        assert len(results) >= 1

    def test_bm25_ranks_more_matches_higher(self, store):
        """Documents matching more query tokens rank higher than partial matches."""
        store.add(_make_record(
            content="Silicon SCF convergence tip for metals",
            grade="finding",
        ))
        store.add(_make_record(
            content="Silicon SCF convergence tip for semiconductors with smearing",
            grade="finding",
        ))
        store.add(_make_record(
            content="Unrelated topic about molecular dynamics",
            grade="finding",
        ))
        results = store.search("Silicon SCF convergence")
        assert len(results) >= 2
        # Both Silicon entries should appear before the unrelated one
        contents = [r["content"] for r in results]
        si_indices = [i for i, c in enumerate(contents) if "Silicon" in c]
        unrelated = [i for i, c in enumerate(contents) if "molecular" in c]
        if unrelated:
            assert all(si < unrelated[0] for si in si_indices)

    def test_sanitize_fts_query_uses_or(self):
        """Verify _sanitize_fts_query produces OR-joined output."""
        from qmatsuite.mcp.knowledge.store import _sanitize_fts_query

        result = _sanitize_fts_query("BN band structure band gap")
        assert "OR" in result
        assert result == "BN OR band OR structure OR band OR gap"

    def test_sanitize_fts_query_strips_reserved(self):
        """Reserved FTS5 keywords are stripped even with OR-join."""
        from qmatsuite.mcp.knowledge.store import _sanitize_fts_query

        result = _sanitize_fts_query("SCF NOT converging AND failing")
        assert "NOT" not in result.split(" OR ")
        assert "AND" not in result.split(" OR ")
        assert "SCF" in result
        assert "converging" in result
        assert "failing" in result


# ===========================================================================
# TestWorkflowScopeFilter — regression tests for cross-workflow search
# ===========================================================================

class TestWorkflowScopeFilter:
    """Workflow filter must NOT hard-exclude insights from other workflows.

    Prior to the fix, passing ``workflow="bands"`` to ``search_knowledge``
    excluded all insights with ``scope_workflow="relax"`` or ``scope_workflow="scf"``.
    This meant bands sessions could never find relax-phase insights about the
    same compound.
    """

    def test_search_finds_relax_insights_without_workflow_filter(self, store):
        """Insights from relax should be findable without workflow constraint."""
        store.add(_make_record(
            content="GaAs relax equilibrium lattice constant a=5.74 Angstrom",
            grade="finding",
            scope={"engine": "qe", "workflow": "relax"},
        ))
        results = store.search("GaAs lattice", workflow="")
        assert len(results) >= 1

    def test_search_finds_relax_insights_from_bands_context(self, store):
        """A bands-workflow search must still find relax insights."""
        store.add(_make_record(
            content="GaAs relax Pulay stress from mixed pseudopotentials",
            grade="finding",
            scope={"engine": "qe", "workflow": "relax"},
        ))
        results = store.search("GaAs Pulay stress", workflow="bands")
        assert len(results) >= 1
        assert any("Pulay" in r["content"] for r in results)

    def test_bands_search_finds_scf_insights(self, store):
        """A bands search should find scf-scoped insights too."""
        store.add(_make_record(
            content="SCF convergence failure in GaAs with mixed pseudos",
            grade="finding",
            scope={"engine": "qe", "workflow": "scf"},
        ))
        results = store.search("GaAs SCF convergence", workflow="bands")
        assert len(results) >= 1

    def test_engine_filter_still_works(self, store):
        """Engine filter should still exclude non-matching engines."""
        store.add(_make_record(
            content="VASP specific convergence tip for metals",
            grade="finding",
            scope={"engine": "vasp"},
        ))
        results = store.search("convergence metals", engine="qe")
        vasp_results = [r for r in results if "VASP" in r["content"]]
        assert len(vasp_results) == 0

    def test_workflow_param_accepted_without_error(self, store):
        """Passing workflow parameter must not cause an error."""
        store.add(_make_record(
            content="Test insight for workflow param acceptance",
            grade="finding",
        ))
        # Should not raise
        results = store.search("workflow param acceptance", workflow="bands")
        assert isinstance(results, list)


# ===========================================================================
# TestBuiltinToggle (Change 0) — 3 tests
# ===========================================================================

class TestBuiltinToggle:
    def test_builtin_disabled_skips_builtin_results(self, store, monkeypatch):
        """When QMS_KNOWLEDGE_BUILTIN=0, builtin entries are excluded."""
        _insert_entry(store.conn, content="Builtin SCF tip toggle test", entry_id="BT001")
        store.add(_make_record(content="Local SCF tip toggle test", grade="finding"))
        monkeypatch.setenv("QMS_KNOWLEDGE_BUILTIN", "0")
        results = store.search("SCF tip toggle test")
        assert all(r.get("id") != "BT001" for r in results)
        assert any("Local" in r["content"] for r in results)

    def test_builtin_enabled_by_default(self, store):
        """Builtin is included by default (no env override)."""
        _insert_entry(store.conn, content="Builtin default check entry", entry_id="BT002")
        results = store.search("Builtin default check")
        result_ids = [r.get("id") for r in results]
        assert "BT002" in result_ids

    def test_builtin_disabled_scope_search(self, store, monkeypatch):
        """Empty query (scope search) also respects the builtin toggle."""
        _insert_entry(
            store.conn, content="Builtin scope toggle test", entry_id="BT003",
            scope_engine="qe",
        )
        store.add(_make_record(
            content="Local scope toggle test", grade="finding",
            scope={"engine": "qe"},
        ))
        monkeypatch.setenv("QMS_KNOWLEDGE_BUILTIN", "0")
        results = store.search("", engine="qe")
        assert all(r.get("id") != "BT003" for r in results)


# ===========================================================================
# TestReservedSlots (Change 1) — 5 tests
# ===========================================================================

class TestReservedSlots:
    def test_local_entries_get_reserved_slots(self, store):
        """With 10 builtin + 2 local, limit=5, both local entries appear."""
        for i in range(10):
            _insert_entry(
                store.conn,
                content=f"Builtin reserved slot test entry {i}",
                entry_id=f"RS_B{i:03d}",
            )
        store.add(_make_record(content="Local reserved slot alpha", grade="finding"))
        store.add(_make_record(content="Local reserved slot beta", grade="finding"))
        results = store.search("reserved slot test entry alpha beta", limit=5)
        local_results = [r for r in results if "Local" in r["content"]]
        assert len(local_results) == 2

    def test_local_first_in_order(self, store):
        """Local results precede builtin in merged output."""
        _insert_entry(store.conn, content="Builtin order test xyz", entry_id="RS_ORD1")
        store.add(_make_record(content="Local order test xyz", grade="finding"))
        results = store.search("order test xyz")
        if len(results) >= 2:
            local_idx = next(
                (i for i, r in enumerate(results) if "Local" in r["content"]), None
            )
            builtin_idx = next(
                (i for i, r in enumerate(results) if "Builtin" in r["content"]), None
            )
            if local_idx is not None and builtin_idx is not None:
                assert local_idx < builtin_idx

    def test_all_local_when_builtin_disabled(self, store, monkeypatch):
        """With builtin disabled, all slots go to local."""
        for i in range(5):
            store.add(_make_record(
                content=f"Local only reserved slot {i}", grade="finding",
            ))
        monkeypatch.setenv("QMS_KNOWLEDGE_BUILTIN", "0")
        results = store.search("Local only reserved slot", limit=10)
        assert all("Local" in r["content"] for r in results)

    def test_all_builtin_when_no_local(self, builtin_db, tmp_path):
        """With no local DB, all results come from builtin."""
        nonexistent = tmp_path / "knowledge" / "no_local.db"
        s = KnowledgeStore(db_path=builtin_db, local_db_path=nonexistent)
        try:
            for i in range(5):
                _insert_entry(
                    s.conn,
                    content=f"Builtin no local test {i}",
                    entry_id=f"RS_NL{i:03d}",
                )
            results = s.search("Builtin no local test")
            assert len(results) == 5
        finally:
            s.close()

    def test_merge_helper_directly(self):
        """Unit test the _merge_with_reserved_slots helper."""
        local = [{"key": "L1"}, {"key": "L2"}]
        builtin = [{"key": f"B{i}"} for i in range(10)]
        merged = _merge_with_reserved_slots(local, builtin, limit=5, reserved=3)
        assert len(merged) == 5
        keys = [m["key"] for m in merged]
        assert keys == ["L1", "L2", "B0", "B1", "B2"]


# ===========================================================================
# TestPatternGrade (Change 3) — 4 tests
# ===========================================================================

class TestPatternGrade:
    def test_pattern_promoted_to_local_db(self, store, local_db_path):
        """A pattern grade is promoted to local.db."""
        record = _make_record(grade="pattern")
        result = store.add(record)
        assert result["promoted"] is True
        assert result["insight_id"] is not None
        assert local_db_path.exists()

    def test_pattern_searchable_via_fts(self, store):
        """A pattern insight is searchable via FTS."""
        store.add(_make_record(
            content="Unique zebra pattern test insight",
            grade="pattern",
        ))
        results = store.search("zebra pattern test")
        assert len(results) >= 1
        assert any("zebra" in r["content"] for r in results)

    def test_pattern_grade_order(self):
        """finding < pattern < principle in grade ordering."""
        assert _GRADE_ORDER["finding"] < _GRADE_ORDER["pattern"]
        assert _GRADE_ORDER["pattern"] < _GRADE_ORDER["principle"]

    def test_all_grades_valid(self, store, local_db_path):
        """Record one of each promotable grade, verify persistence."""
        for grade in ("finding", "pattern", "principle"):
            result = store.add(_make_record(
                content=f"Grade test {grade} content",
                grade=grade,
            ))
            assert result["promoted"] is True
        assert local_db_path.exists()
        count = store.local_conn.execute(
            "SELECT COUNT(*) FROM insights WHERE status = 'active'"
        ).fetchone()[0]
        assert count == 3


# ===========================================================================
# TestMetadata (Change 6) — 10 tests
# ===========================================================================

class TestMetadata:
    def test_metadata_column_exists(self, store, local_db_path):
        """The metadata column exists in the insights table."""
        store.add(_make_record(grade="finding"))
        cols = {
            row[1]
            for row in store.local_conn.execute("PRAGMA table_info(insights)").fetchall()
        }
        assert "metadata" in cols

    def test_metadata_stores_agent_model(self, store, monkeypatch):
        """Metadata includes agent_model from env."""
        monkeypatch.setenv("QMS_AGENT_MODEL", "claude-test-v1")
        store.add(_make_record(content="Agent model test", grade="finding"))
        row = store.local_conn.execute(
            "SELECT metadata FROM insights WHERE content = 'Agent model test'"
        ).fetchone()
        meta = json.loads(row[0])
        assert meta["agent_model"] == "claude-test-v1"

    def test_metadata_default_agent_model(self, store, monkeypatch):
        """Without QMS_AGENT_MODEL env, agent_model defaults to 'unknown'."""
        monkeypatch.delenv("QMS_AGENT_MODEL", raising=False)
        store.add(_make_record(content="Default model test", grade="finding"))
        row = store.local_conn.execute(
            "SELECT metadata FROM insights WHERE content = 'Default model test'"
        ).fetchone()
        meta = json.loads(row[0])
        assert meta["agent_model"] == "unknown"

    def test_source_calculation_stored(self, store):
        """source_calculation is stored in metadata JSON."""
        record = _make_record(content="Source calc test", grade="finding")
        record.source_calculation = "01ABC123"
        store.add(record)
        row = store.local_conn.execute(
            "SELECT metadata FROM insights WHERE content = 'Source calc test'"
        ).fetchone()
        meta = json.loads(row[0])
        assert meta["source_calculation"] == "01ABC123"

    def test_references_stored(self, store):
        """references are stored in metadata JSON."""
        record = _make_record(content="References test", grade="finding")
        record.references = ["REF001", "REF002"]
        store.add(record)
        row = store.local_conn.execute(
            "SELECT metadata FROM insights WHERE content = 'References test'"
        ).fetchone()
        meta = json.loads(row[0])
        assert meta["references"] == ["REF001", "REF002"]

    def test_search_results_include_metadata(self, store):
        """Search results include metadata field."""
        store.add(_make_record(content="Metadata search test unique", grade="finding"))
        results = store.search("Metadata search test unique")
        assert len(results) >= 1
        row = results[0]
        assert "metadata" in row

    def test_pattern_requires_references(self, store, tmp_path, monkeypatch):
        """Pattern grade without references returns error."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal_meta")
        set_journal(journal)
        try:
            from qmatsuite.mcp.tools.record_insight import record_insight

            result = record_insight.fn(content="Pattern without refs", grade="pattern")
            assert result["status"] == "error"
            assert "reference" in result["message"].lower()
        finally:
            monkeypatch.setattr(knowledge_mod, "_store", None)
            reset_journal()

    def test_principle_requires_references(self, store, tmp_path, monkeypatch):
        """Principle grade without references returns error."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal_meta2")
        set_journal(journal)
        try:
            from qmatsuite.mcp.tools.record_insight import record_insight

            result = record_insight.fn(content="Principle without refs", grade="principle")
            assert result["status"] == "error"
            assert "reference" in result["message"].lower()
        finally:
            monkeypatch.setattr(knowledge_mod, "_store", None)
            reset_journal()

    def test_references_validated_warn_on_missing(self, store, tmp_path, monkeypatch):
        """Nonexistent reference IDs produce warnings but still save."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal_meta3")
        set_journal(journal)
        try:
            from qmatsuite.mcp.tools.record_insight import record_insight

            result = record_insight.fn(
                content="Pattern with missing ref",
                grade="pattern",
                references="NONEXISTENT_REF_001",
            )
            assert result["status"] == "success"
            assert any("not found" in w for w in result.get("warnings", []))
        finally:
            monkeypatch.setattr(knowledge_mod, "_store", None)
            reset_journal()

    def test_journal_entry_includes_references(self, store, tmp_path, monkeypatch):
        """Journal entry 'after' dict includes references."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal_meta4")
        set_journal(journal)
        try:
            from qmatsuite.mcp.tools.record_insight import record_insight

            record_insight.fn(
                content="Finding with refs for journal test",
                grade="finding",
                references="REF_A,REF_B",
            )
            entries = journal.list_entries()
            assert len(entries) >= 1
            after = entries[0].after
            assert after["references"] == ["REF_A", "REF_B"]
        finally:
            monkeypatch.setattr(knowledge_mod, "_store", None)
            reset_journal()


# ===========================================================================
# TestListInsights (Change 7) — 5 tests
# ===========================================================================

class TestListInsights:
    def test_list_insights_by_grade(self, store):
        """list_by_grade returns only the requested grade."""
        store.add(_make_record(content="Finding for list test", grade="finding"))
        store.add(_make_record(content="Pattern for list test", grade="pattern"))
        data = store.list_by_grade("finding")
        assert all(r["grade"] == "finding" for r in data["insights"])
        assert data["total"] >= 1

    def test_list_insights_limit(self, store):
        """Limit parameter is respected."""
        for i in range(15):
            store.add(_make_record(
                content=f"Finding for limit test {i}", grade="finding",
            ))
        data = store.list_by_grade("finding", limit=10)
        assert len(data["insights"]) == 10
        assert data["total"] == 15

    def test_list_insights_compound_filter(self, store):
        """Compound filter matches tags."""
        store.add(_make_record(
            content="Silicon finding for compound filter", grade="finding",
            tags=["Si", "semiconductor"],
        ))
        store.add(_make_record(
            content="Iron finding for compound filter", grade="finding",
            tags=["Fe", "metal"],
        ))
        data = store.list_by_grade("finding", compound="Si")
        assert data["total"] >= 1
        assert all("Si" in r.get("tags", "") for r in data["insights"])

    def test_list_insights_includes_metadata(self, store, monkeypatch):
        """Insights include metadata field."""
        monkeypatch.setenv("QMS_AGENT_MODEL", "test-model")
        store.add(_make_record(content="Metadata list test", grade="finding"))
        data = store.list_by_grade("finding")
        assert len(data["insights"]) >= 1
        row = data["insights"][0]
        assert "metadata" in row

    def test_list_insights_empty(self, store):
        """No matching grade returns empty list."""
        data = store.list_by_grade("principle")
        assert data["total"] == 0
        assert data["insights"] == []


# ===========================================================================
# TestMCPInstructions (Change 5) — 2 tests
# ===========================================================================

class TestMCPInstructions:
    def test_instructions_set(self):
        """MCP instructions are set on the FastMCP instance."""
        from qmatsuite.mcp.app import mcp

        assert mcp.instructions is not None
        assert len(mcp.instructions) > 0

    def test_instructions_mention_core_grades(self):
        """Instructions mention the three promoted grades."""
        from qmatsuite.mcp.app import mcp

        text = mcp.instructions
        for grade in ("finding", "pattern", "principle"):
            assert grade in text, f"Missing grade: {grade}"

    def test_instructions_workflow(self):
        """Preamble describes both calculation and synthesis modes."""
        from qmatsuite.mcp.app import mcp

        text = mcp.instructions
        assert "CALCULATION MODE" in text
        assert "KNOWLEDGE SYNTHESIS MODE" in text
        assert "search_knowledge" in text
        assert "record_insight" in text

    def test_instructions_citation_semantics(self):
        """Preamble explains record vs report guidance."""
        from qmatsuite.mcp.app import mcp

        text = mcp.instructions
        assert "WHEN TO RECORD" in text

    def test_instructions_upvotes_downvotes(self):
        """Preamble mentions vote mechanism for knowledge evolution."""
        from qmatsuite.mcp.app import mcp

        text = mcp.instructions
        assert "vote entries up or down" in text


# ===========================================================================
# TestFullSynthesisFlow (E2E integration) — 1 test
# ===========================================================================

class TestFullSynthesisFlow:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        """Patch the knowledge store singleton and journal."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal_e2e")
        set_journal(journal)
        self._journal = journal
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_full_synthesis_flow(self):
        """End-to-end: 8 findings → nudge → list → pattern → search."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        store = self._store
        finding_ids = []  # full ULIDs from tool responses

        # 1. Record 8 findings (wildcard scope avoids contradiction detection)
        for i in range(8):
            result = record_insight.fn(
                content=f"E2E finding {i} about silicon convergence",
                grade="finding",
                tags="Si,convergence",
            )
            assert result["status"] == "success"
            finding_ids.append(result["data"]["insight_id"])

        # Verify full ULIDs (26 chars)
        for fid in finding_ids:
            assert len(fid) == 26

        # 2. Call list_by_grade and verify
        data = store.list_by_grade("finding")
        assert data["total"] == 8
        listed_ids = [r["id"] for r in data["insights"]]
        for fid in finding_ids:
            assert fid in listed_ids

        # 4. Record 1 pattern with references to all findings (short IDs, R8 resolves)
        refs_str = ",".join(finding_ids)
        pattern_result = record_insight.fn(
            content="Silicon convergence requires careful smearing",
            grade="pattern",
            references=refs_str,
            tags="Si,convergence,pattern",
        )
        assert pattern_result["status"] == "success"
        assert pattern_result["data"]["promoted"] is True

        # 5. Record another finding — verify L1→L2 nudge is gone (sliding window)
        extra = record_insight.fn(
            content="E2E extra finding after pattern",
            grade="finding",
        )
        assert extra["status"] == "success"

        # 6. Search for the pattern
        results = store.search("Silicon convergence smearing")
        pattern_results = [r for r in results if r["grade"] == "pattern"]
        assert len(pattern_results) >= 1
        # Check metadata has references (full ULIDs stored after R8 resolution)
        meta_raw = pattern_results[0].get("metadata", "{}")
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
        assert "references" in meta
        assert len(meta["references"]) == 8
        # References should be full ULIDs (26 chars)
        for ref in meta["references"]:
            assert len(ref) == 26

        # 7. Verify journal entry for pattern includes resolved full ULIDs
        entries = self._journal.list_entries()
        pattern_entries = [
            e for e in entries
            if e.after.get("grade") == "pattern"
        ]
        assert len(pattern_entries) >= 1
        journal_refs = pattern_entries[0].after["references"]
        assert len(journal_refs) == 8
        for ref in journal_refs:
            assert len(ref) == 26


# ===========================================================================
# TestCitations (7 tests) — Change 8
# ===========================================================================


class TestCitations:
    """Test citation tracking in record_insight."""

    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        """Patch the knowledge store singleton and journal for isolation."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod, "_store", store)

        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal")
        set_journal(journal)
        self._journal = journal
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_citations_parsed_and_stored(self):
        """Record with citations stores them in metadata."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(
            content="Finding with citations",
            grade="finding",
            citations="01AAA:up,01BBB:down",
        )
        assert r["status"] == "success"
        assert r["data"]["promoted"] is True
        iid = r["data"]["insight_id"]
        full_id = self._store.resolve_short_id(iid)
        row = self._store.get_by_id(full_id)
        meta = json.loads(row["metadata"])
        assert "citations" in meta
        cits = meta["citations"]
        assert len(cits) == 2
        assert cits[0]["vote"] == "up"
        assert cits[1]["vote"] == "down"

    def test_citations_update_upvotes(self):
        """Citing an insight with 'up' increments its upvotes."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        # Record insight A first
        r_a = record_insight.fn(content="Insight A", grade="finding")
        assert r_a["status"] == "success"
        a_id = r_a["data"]["insight_id"]  # 10-char short ID
        a_full = self._store.resolve_short_id(a_id)

        # Verify initial upvotes = 0
        row = self._store.get_by_id(a_full)
        assert row["upvotes"] == 0

        # Record insight B citing A as helpful (short ID, R8 resolves)
        r_b = record_insight.fn(
            content="Insight B cites A",
            grade="finding",
            citations=f"{a_id}:up",
        )
        assert r_b["status"] == "success"

        # Verify A's upvotes incremented
        row = self._store.get_by_id(a_full)
        assert row["upvotes"] == 1

    def test_citations_update_downvotes(self):
        """Citing an insight with 'down' increments its downvotes."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        r_a = record_insight.fn(content="Insight A for downvote", grade="finding")
        a_id = r_a["data"]["insight_id"]
        a_full = self._store.resolve_short_id(a_id)

        r_b = record_insight.fn(
            content="Insight B cites A negatively",
            grade="finding",
            citations=f"{a_id}:down",
        )
        assert r_b["status"] == "success"

        row = self._store.get_by_id(a_full)
        assert row["downvotes"] == 1

    def test_citations_empty_string_ok(self):
        """Empty citations string produces no error and no citations in metadata."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(
            content="Finding without citations",
            grade="finding",
            citations="",
        )
        assert r["status"] == "success"
        iid = r["data"]["insight_id"]
        full_id = self._store.resolve_short_id(iid)
        row = self._store.get_by_id(full_id)
        meta = json.loads(row["metadata"])
        assert "citations" not in meta
        assert "citation_summary" not in r["data"]

    def test_citations_invalid_format_warns(self):
        """Invalid citation format produces a warning but insight is still recorded."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(
            content="Finding with bad citations",
            grade="finding",
            citations="garbage,also_bad",
        )
        assert r["status"] == "success"
        assert r["data"]["promoted"] is True
        assert r["warnings"]
        assert any("Invalid citation format" in w for w in r["warnings"])

    def test_citations_missing_id_skipped(self):
        """Citing a nonexistent ULID skips silently — no crash."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(
            content="Finding citing ghost",
            grade="finding",
            citations="NONEXISTENT_ULID_123:up",
        )
        assert r["status"] == "success"
        assert r["data"]["promoted"] is True
        # Should still have citation summary showing skip (G1 fix)
        assert "citation_summary" in r["data"]
        assert "skipped" in r["data"]["citation_summary"]

    def test_citations_in_response(self):
        """Response includes citation summary string."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        r_a = record_insight.fn(content="Cited insight 1", grade="finding")
        r_b = record_insight.fn(content="Cited insight 2", grade="finding")
        a_id = r_a["data"]["insight_id"]
        b_id = r_b["data"]["insight_id"]

        r = record_insight.fn(
            content="Summarizer citing two insights",
            grade="finding",
            citations=f"{a_id}:up,{b_id}:down",
        )
        assert r["status"] == "success"
        summary = r["data"]["citation_summary"]
        assert "2 insight(s)" in summary
        assert "1 helpful" in summary
        assert "1 not" in summary

    def test_votes_visible_in_search_results(self):
        """R11: search_knowledge results include upvotes/downvotes."""
        from qmatsuite.mcp.tools.record_insight import record_insight
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        r_a = record_insight.fn(
            content="Unique xenon insight for vote search test",
            grade="finding",
        )
        a_id = r_a["data"]["insight_id"]

        # Cast an upvote
        record_insight.fn(
            content="Voter insight",
            grade="finding",
            citations=f"{a_id}:up",
        )

        result = search_knowledge.fn(query="xenon insight vote search test")
        assert result["status"] == "success"
        matched = [
            r for r in result["data"]["results"]
            if "xenon" in r["content"].lower()
        ]
        assert len(matched) >= 1
        assert matched[0]["upvotes"] == 1
        assert matched[0]["downvotes"] == 0

    def test_votes_visible_in_list_insights(self):
        """R11: list_insights results include upvotes/downvotes."""
        from qmatsuite.mcp.tools.record_insight import record_insight
        from qmatsuite.mcp.tools.list_insights import list_insights

        r_a = record_insight.fn(
            content="Unique krypton insight for vote list test",
            grade="finding",
        )
        a_id = r_a["data"]["insight_id"]

        # Cast a downvote
        record_insight.fn(
            content="Downvoter insight",
            grade="finding",
            citations=f"{a_id}:down",
        )

        result = list_insights.fn(grade="finding", mode="recent")
        assert result["status"] == "success"
        matched = [
            r for r in result["data"]["insights"]
            if "krypton" in r["content"].lower()
        ]
        assert len(matched) >= 1
        assert matched[0]["upvotes"] == 0
        assert matched[0]["downvotes"] == 1


# ===========================================================================
# TestShortIds (R7 + R8) — 5 tests
# ===========================================================================

class TestShortIds:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        """Patch the knowledge store singleton and journal for isolation."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal_short_ids")
        set_journal(journal)
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_full_ulid_length_is_26(self):
        """record_insight returns full 26-char ULIDs."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        result = record_insight.fn(content="Full ULID test", grade="finding")
        assert result["status"] == "success"
        assert len(result["data"]["insight_id"]) == 26

    def test_resolve_short_id_exact(self):
        """10-char prefix resolves to full 26-char ULID."""
        self._store.add(_make_record(content="Resolve test", grade="finding"))
        row = self._store.local_conn.execute(
            "SELECT id FROM insights ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        full_id = row[0]
        assert len(full_id) == 26
        resolved = self._store.resolve_short_id(full_id[:10])
        assert resolved == full_id

    def test_resolve_short_id_not_found(self):
        """Unknown prefix raises ValueError."""
        with pytest.raises(ValueError, match="No insight found"):
            self._store.resolve_short_id("ZZZZZZZZZZ")

    def test_resolve_short_id_no_local_db(self, builtin_db, tmp_path):
        """No local DB raises ValueError."""
        nonexistent = tmp_path / "knowledge" / "no_local_resolve.db"
        s = KnowledgeStore(db_path=builtin_db, local_db_path=nonexistent)
        try:
            with pytest.raises(ValueError, match="No insight found"):
                s.resolve_short_id("ABCDEFGHIJ")
        finally:
            s.close()

    def test_record_insight_with_full_references(self):
        """Pass full ULID refs from record_insight, verify stored metadata has full ULIDs."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        # Record two findings
        r1 = record_insight.fn(content="Finding 1 for ref test", grade="finding")
        r2 = record_insight.fn(content="Finding 2 for ref test", grade="finding")
        ref1 = r1["data"]["insight_id"]
        ref2 = r2["data"]["insight_id"]
        assert len(ref1) == 26
        assert len(ref2) == 26

        # Record pattern referencing full ULIDs
        result = record_insight.fn(
            content="Pattern from full refs",
            grade="pattern",
            references=f"{ref1},{ref2}",
        )
        assert result["status"] == "success"
        # Verify stored references are full ULIDs
        pid = result["data"]["insight_id"]
        row = self._store.get_by_id(pid)
        meta = json.loads(row["metadata"])
        assert len(meta["references"]) == 2
        for ref in meta["references"]:
            assert len(ref) == 26


# ===========================================================================
# TestListInsightsMode (R5 + R6) — 6 tests
# ===========================================================================

class TestListInsightsMode:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        """Patch the knowledge store singleton and journal for isolation."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal_list_mode")
        set_journal(journal)
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_pending_mode_default(self):
        """Default mode is 'pending'."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        for i in range(3):
            self._store.add(_make_record(content=f"Finding {i} pending mode", grade="finding"))
        result = list_insights.fn(grade="finding")
        assert result["status"] == "success"
        assert "total_pending" in result["data"]

    def test_recent_mode_returns_total(self):
        """Mode 'recent' returns total field."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        for i in range(3):
            self._store.add(_make_record(content=f"Finding {i} recent mode", grade="finding"))
        result = list_insights.fn(grade="finding", mode="recent")
        assert result["status"] == "success"
        assert "total" in result["data"]
        assert result["data"]["total"] == 3

    def test_pending_after_synthesis_shows_only_new(self):
        """After pattern synthesis, pending only shows new findings."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        for i in range(5):
            self._store.add(_make_record(content=f"Finding {i} before synth", grade="finding"))
        self._store.add(_make_record(content="Pattern after findings", grade="pattern"))
        for i in range(2):
            self._store.add(_make_record(content=f"Finding {i} after synth", grade="finding"))
        result = list_insights.fn(grade="finding")
        assert result["status"] == "success"
        assert result["data"]["total_pending"] == 2

    def test_pending_header_no_synthesis(self):
        """Pending header says 'no pattern synthesis yet' when none exist."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        for i in range(3):
            self._store.add(_make_record(content=f"Finding {i} no synth", grade="finding"))
        result = list_insights.fn(grade="finding")
        assert "no pattern synthesis yet" in result["context_hint"].lower()

    def test_pending_header_with_synthesis(self):
        """Pending header mentions 'since last' when synthesis exists."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        self._store.add(_make_record(content="Old finding", grade="finding"))
        self._store.add(_make_record(content="Pattern exists", grade="pattern"))
        self._store.add(_make_record(content="New finding after", grade="finding"))
        result = list_insights.fn(grade="finding")
        assert "since last pattern synthesis" in result["context_hint"].lower()

    def test_list_pending_store_method(self):
        """Store.list_pending returns correct structure."""
        for i in range(5):
            self._store.add(_make_record(content=f"Finding {i} list_pending", grade="finding"))
        data = self._store.list_pending("finding")
        assert "total_pending" in data
        assert "since" in data
        assert data["total_pending"] == 5
        assert data["since"] is None  # no patterns yet


# ===========================================================================
# TestGapFixes (G1, G2, G7, G8, G9) — final polish tests
# ===========================================================================

class TestGapFixes:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        """Patch the knowledge store singleton and journal for isolation."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal

        journal = Journal(journal_dir=tmp_path / "journal_gap_fixes")
        set_journal(journal)
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    # -- G2: reference error hint is grade-aware --

    def test_pattern_missing_refs_hints_finding(self):
        """G2: pattern missing refs → hint says grade='finding'."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(
            content="Pattern without refs",
            grade="pattern",
        )
        assert r["status"] == "error"
        assert "grade='finding'" in r["context_hint"]
        assert "grade='pattern'" not in r["context_hint"]

    def test_principle_missing_refs_hints_pattern(self):
        """G2: principle missing refs → hint says grade='pattern'."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(
            content="Principle without refs",
            grade="principle",
        )
        assert r["status"] == "error"
        assert "grade='pattern'" in r["context_hint"]
        assert "grade='finding'" not in r["context_hint"]

    # -- G1: citation summary uses applied counts --

    def test_citation_summary_reports_skipped(self):
        """G1: citing nonexistent ID → summary says 'skipped'."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(
            content="Finding with ghost citation",
            grade="finding",
            citations="ZZZZZZZZZZZZZZZ:up",
        )
        assert r["status"] == "success"
        summary = r["data"]["citation_summary"]
        assert "1 skipped" in summary
        assert "helpful" not in summary

    def test_citation_summary_reports_applied(self):
        """G1: citing existing local ID → summary says 'helpful'."""
        from qmatsuite.mcp.tools.record_insight import record_insight

        r_a = record_insight.fn(content="Citable insight", grade="finding")
        a_id = r_a["data"]["insight_id"]

        r = record_insight.fn(
            content="Finding citing existing",
            grade="finding",
            citations=f"{a_id}:up",
        )
        assert r["status"] == "success"
        summary = r["data"]["citation_summary"]
        assert "1 helpful" in summary
        assert "skipped" not in summary

    # -- G7: tags returned as list --

    def test_search_tags_are_list(self):
        """G7: search_knowledge returns tags as a parsed list, not JSON string."""
        from qmatsuite.mcp.tools.record_insight import record_insight
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        record_insight.fn(
            content="Unique helium insight for tags test",
            grade="finding",
            tags="helium,noble_gas",
        )
        result = search_knowledge.fn(query="helium insight tags test")
        assert result["status"] == "success"
        matched = [r for r in result["data"]["results"] if "helium" in r["content"].lower()]
        assert len(matched) >= 1
        assert isinstance(matched[0]["tags"], list)
        assert "helium" in matched[0]["tags"]

    def test_list_insights_tags_are_list(self):
        """G7: list_insights returns tags as a parsed list."""
        from qmatsuite.mcp.tools.record_insight import record_insight
        from qmatsuite.mcp.tools.list_insights import list_insights

        record_insight.fn(
            content="Unique neon insight for list tags test",
            grade="finding",
            tags="neon,noble_gas",
        )
        result = list_insights.fn(grade="finding", mode="recent")
        assert result["status"] == "success"
        matched = [r for r in result["data"]["insights"] if "neon" in r["content"].lower()]
        assert len(matched) >= 1
        assert isinstance(matched[0]["tags"], list)
        assert "neon" in matched[0]["tags"]

    # -- G8: mode validation --

    def test_list_insights_invalid_mode(self):
        """G8: invalid mode returns VALIDATION_ERROR."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        result = list_insights.fn(grade="finding", mode="everything")
        assert result["status"] == "error"
        assert "VALIDATION_ERROR" in result["error_type"]
        assert "everything" in result["message"]

    # -- G9: mode in response --

    def test_list_insights_pending_has_mode(self):
        """G9: pending response includes mode='pending'."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        self._store.add(_make_record(content="Finding for mode test", grade="finding"))
        result = list_insights.fn(grade="finding")
        assert result["data"]["mode"] == "pending"

    def test_list_insights_recent_has_mode(self):
        """G9: recent response includes mode='recent'."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        self._store.add(_make_record(content="Finding for recent mode test", grade="finding"))
        result = list_insights.fn(grade="finding", mode="recent")
        assert result["data"]["mode"] == "recent"
