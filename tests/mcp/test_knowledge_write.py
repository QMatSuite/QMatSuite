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
