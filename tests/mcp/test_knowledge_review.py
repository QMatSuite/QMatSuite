"""Tests for the knowledge review system: review_insight, grade-based auto status,
status rename, search/list integration, contradiction simplification, migration.

All tests use tmp_path fixtures for isolated DB paths.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qmatsuite.mcp.knowledge.schema import init_db
from qmatsuite.mcp.knowledge.store import (
    KnowledgeStore,
    _CONTRADICTION_THRESHOLD,
)
from qmatsuite.mcp.knowledge.insight_record import InsightRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    content: str = "Test insight content for review",
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
    status: str = "confirmed",
    scope_engine: str = "*",
    source_type: str = "builtin",
    contradiction_count: int = 0,
):
    """Insert a test entry directly into a DB connection."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO insights (
            id, grade, scope_engine, scope_workflow, scope_system_type, scope_method,
            content, confidence, source_type, created_by, tags,
            status, contradiction_count, upvotes, created_at, updated_at
        ) VALUES (?, ?, ?, '*', '*', '*', ?, 'medium', ?, 'test', '[]',
                  ?, ?, 0, ?, ?)
        """,
        (entry_id, grade, scope_engine, content, source_type,
         status, contradiction_count, now, now),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def builtin_db(tmp_path):
    p = tmp_path / "knowledge" / "builtin.db"
    init_db(p)
    return p


@pytest.fixture
def local_db_path(tmp_path):
    return tmp_path / "knowledge" / "local.db"


@pytest.fixture
def store(builtin_db, local_db_path):
    return KnowledgeStore(db_path=builtin_db, local_db_path=local_db_path)


# ===========================================================================
# Auto Status by Grade
# ===========================================================================

class TestAutoStatusByGrade:
    def test_finding_auto_under_review(self, store):
        """record_insight(grade='finding') → status == 'under_review'."""
        result = store.add(_make_record(grade="finding"))
        assert result["promoted"] is True
        row = store.local_conn.execute(
            "SELECT status FROM insights WHERE id = ?", (result["insight_id"],)
        ).fetchone()
        assert row[0] == "under_review"

    def test_pattern_auto_confirmed(self, store):
        """record_insight(grade='pattern') → status == 'confirmed'."""
        result = store.add(_make_record(grade="pattern"))
        assert result["promoted"] is True
        row = store.local_conn.execute(
            "SELECT status FROM insights WHERE id = ?", (result["insight_id"],)
        ).fetchone()
        assert row[0] == "confirmed"

    def test_principle_auto_confirmed(self, store):
        """record_insight(grade='principle') → status == 'confirmed'."""
        result = store.add(_make_record(grade="principle"))
        assert result["promoted"] is True
        row = store.local_conn.execute(
            "SELECT status FROM insights WHERE id = ?", (result["insight_id"],)
        ).fetchone()
        assert row[0] == "confirmed"


# ===========================================================================
# review_insight — Basic Operations
# ===========================================================================

class TestReviewInsight:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        import qmatsuite.mcp.knowledge as knowledge_mod
        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal
        journal = Journal(journal_dir=tmp_path / "journal_review")
        set_journal(journal)
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_confirm_sets_status_confirmed(self):
        """review(verdict='confirmed') → status == 'confirmed'."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding to confirm", grade="finding")
        assert r["status"] == "success"
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid, verdict="confirmed", reasoning="Data looks correct"
        )
        assert result["status"] == "success"
        assert result["data"]["new_status"] == "confirmed"

        row = self._store.local_conn.execute(
            "SELECT status, last_validated FROM insights WHERE id = ?", (iid,)
        ).fetchone()
        assert row["status"] == "confirmed"
        assert row["last_validated"] is not None

    def test_deprecate_sets_status_deprecated(self):
        """review(verdict='deprecated') → status == 'deprecated'."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding to deprecate", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid, verdict="deprecated", reasoning="Incorrect methodology"
        )
        assert result["status"] == "success"
        assert result["data"]["new_status"] == "deprecated"

        row = self._store.local_conn.execute(
            "SELECT status, deprecated_reason FROM insights WHERE id = ?", (iid,)
        ).fetchone()
        assert row["status"] == "deprecated"
        assert row["deprecated_reason"] == "Incorrect methodology"

    def test_deprecate_with_superseded_by(self):
        """Deprecate with superseded_by → old deprecated, new confirmed."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r_old = record_insight.fn(content="Old finding", grade="finding")
        r_new = record_insight.fn(content="Corrected finding", grade="finding")
        old_id = r_old["data"]["insight_id"]
        new_id = r_new["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=old_id,
            verdict="deprecated",
            reasoning="Superseded by corrected version",
            superseded_by=new_id,
        )
        assert result["status"] == "success"
        assert result["data"]["superseded_by"] == new_id
        assert result["data"]["superseded_by_status"] == "confirmed"

        old_row = self._store.local_conn.execute(
            "SELECT status, superseded_by FROM insights WHERE id = ?", (old_id,)
        ).fetchone()
        assert old_row["status"] == "deprecated"
        assert old_row["superseded_by"] == new_id

        new_row = self._store.local_conn.execute(
            "SELECT status FROM insights WHERE id = ?", (new_id,)
        ).fetchone()
        assert new_row["status"] == "confirmed"

    def test_confirm_with_superseded_by(self):
        """Confirm with superseded_by → both confirmed."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r_old = record_insight.fn(content="Finding A", grade="finding")
        r_new = record_insight.fn(content="Finding B", grade="finding")
        old_id = r_old["data"]["insight_id"]
        new_id = r_new["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=old_id,
            verdict="confirmed",
            reasoning="Both are valid",
            superseded_by=new_id,
        )
        assert result["status"] == "success"

        for iid in (old_id, new_id):
            row = self._store.local_conn.execute(
                "SELECT status FROM insights WHERE id = ?", (iid,)
            ).fetchone()
            assert row["status"] == "confirmed"


# ===========================================================================
# review_insight — Validation
# ===========================================================================

class TestReviewValidation:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        import qmatsuite.mcp.knowledge as knowledge_mod
        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal
        journal = Journal(journal_dir=tmp_path / "journal_val")
        set_journal(journal)
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_review_requires_reasoning(self):
        """Empty reasoning → error."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Some finding", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(insight_id=iid, verdict="confirmed", reasoning="")
        assert result["status"] == "error"

    def test_review_invalid_verdict_rejected(self):
        """verdict='maybe' → error."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Some finding", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(insight_id=iid, verdict="maybe", reasoning="Unsure")
        assert result["status"] == "error"

    def test_review_nonexistent_id_rejected(self):
        """Bad ULID → error."""
        from qmatsuite.mcp.tools.review_insight import review_insight

        result = review_insight.fn(
            insight_id="NONEXISTENT_ULID", verdict="confirmed", reasoning="Test"
        )
        assert result["status"] == "error"

    def test_review_already_deprecated_rejected(self):
        """Deprecate → deprecate again → error."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Will be deprecated twice", grade="finding")
        iid = r["data"]["insight_id"]

        review_insight.fn(insight_id=iid, verdict="deprecated", reasoning="First")
        result = review_insight.fn(insight_id=iid, verdict="deprecated", reasoning="Second")
        assert result["status"] == "error"
        assert "deprecated" in result["message"].lower()

    def test_review_superseded_by_nonexistent_rejected(self):
        """superseded_by='BADULID' → error, no changes made."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding for bad supersede", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid,
            verdict="deprecated",
            reasoning="Bad supersede",
            superseded_by="NONEXISTENT_ULID",
        )
        assert result["status"] == "error"

        # Original should be unchanged
        row = self._store.local_conn.execute(
            "SELECT status FROM insights WHERE id = ?", (iid,)
        ).fetchone()
        assert row["status"] == "under_review"

    def test_review_builtin_rejected(self):
        """Can't review builtin.db entries."""
        from qmatsuite.mcp.tools.review_insight import review_insight

        _insert_entry(
            self._store.conn, content="Builtin entry", entry_id="BUILTIN001"
        )
        result = review_insight.fn(
            insight_id="BUILTIN001", verdict="confirmed", reasoning="Test"
        )
        assert result["status"] == "error"
        assert "builtin" in result["message"].lower() or "curated" in result["message"].lower()


# ===========================================================================
# Search Integration
# ===========================================================================

class TestSearchIntegration:
    def test_search_returns_status_field(self, store):
        """Search results include 'status' key."""
        store.add(_make_record(content="Unique xylophone search status test"))
        results = store.search("xylophone search status")
        assert len(results) >= 1
        assert "status" in results[0]

    def test_search_includes_all_statuses(self, store):
        """Deprecated insights still appear in search."""
        result = store.add(_make_record(
            content="Unique platypus deprecated search test"
        ))
        iid = result["insight_id"]
        # Manually deprecate
        store.local_conn.execute(
            "UPDATE insights SET status = 'deprecated' WHERE id = ?", (iid,)
        )
        store.local_conn.commit()

        results = store.search("platypus deprecated search")
        matched = [r for r in results if r["id"] == iid]
        assert len(matched) == 1
        assert matched[0]["status"] == "deprecated"


# ===========================================================================
# List Integration
# ===========================================================================

class TestListIntegration:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        import qmatsuite.mcp.knowledge as knowledge_mod
        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal
        journal = Journal(journal_dir=tmp_path / "journal_list")
        set_journal(journal)
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_list_returns_status_field(self):
        """list results include 'status' key."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        self._store.add(_make_record(content="Status field test", grade="finding"))
        result = list_insights.fn(grade="finding", mode="recent")
        assert result["status"] == "success"
        items = result["data"]["insights"]
        assert len(items) >= 1
        assert "status" in items[0]

    def test_list_filter_by_status(self):
        """list(status='under_review') returns only under_review."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        self._store.add(_make_record(
            content="Under review finding", grade="finding"
        ))
        self._store.add(_make_record(
            content="Confirmed pattern", grade="pattern"
        ))

        result = list_insights.fn(
            grade="finding", mode="recent", status="under_review"
        )
        items = result["data"]["insights"]
        for item in items:
            assert item["status"] == "under_review"

    def test_list_returns_contradiction_count(self):
        """list results include 'contradiction_count' key."""
        from qmatsuite.mcp.tools.list_insights import list_insights

        self._store.add(_make_record(content="CC test", grade="finding"))
        result = list_insights.fn(grade="finding", mode="recent")
        items = result["data"]["insights"]
        assert len(items) >= 1
        assert "contradiction_count" in items[0]


# ===========================================================================
# Contradiction Detection — Simplified
# ===========================================================================

class TestContradictionSimplified:
    def test_contradiction_count_only_no_status_change(self, store):
        """4+ same-scope findings → count increments but status stays."""
        _insert_entry(
            store.conn,
            content="QE tip for contradiction count test",
            entry_id="NOSTATUS001",
            scope_engine="qe",
            status="confirmed",
            contradiction_count=_CONTRADICTION_THRESHOLD - 1,
        )
        store.add(_make_record(
            content="New QE finding that triggers count",
            grade="finding",
            scope={"engine": "qe"},
        ))
        row = store.conn.execute(
            "SELECT status, contradiction_count FROM insights WHERE id = 'NOSTATUS001'"
        ).fetchone()
        # Count incremented past threshold
        assert row[1] >= _CONTRADICTION_THRESHOLD
        # But status NOT changed (no longer auto-flagged)
        assert row[0] == "confirmed"

    def test_contradiction_matches_non_deprecated(self, store):
        """Deprecated insights don't participate in contradiction matching."""
        _insert_entry(
            store.conn,
            content="Deprecated entry should not contradict",
            entry_id="DEP001",
            scope_engine="qe",
            status="deprecated",
        )
        result = store.add(_make_record(
            content="Finding that should not match deprecated",
            grade="finding",
            scope={"engine": "qe"},
        ))
        contra_ids = [c["id"] for c in result["contradictions"]]
        assert "DEP001" not in contra_ids


# ===========================================================================
# Migration
# ===========================================================================

class TestMigration:
    def test_migrate_active_to_confirmed(self, tmp_path):
        """Insert with 'active' → run migration → status == 'confirmed'."""
        import sqlite3
        db_path = tmp_path / "migration_test.db"
        # Create DB with old schema manually
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        from qmatsuite.mcp.knowledge.schema import SCHEMA_DDL
        conn.executescript(SCHEMA_DDL)
        conn.commit()
        # Insert with old 'active' status
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO insights (id, grade, content, confidence,
               source_type, created_by, tags, status, created_at, updated_at)
               VALUES ('MIG001', 'finding', 'test', 'medium', 'local', 'test',
               '[]', 'active', ?, ?)""",
            (now, now),
        )
        conn.commit()
        conn.close()

        # Re-open via init_db (triggers migration)
        conn2 = init_db(db_path)
        row = conn2.execute(
            "SELECT status FROM insights WHERE id = 'MIG001'"
        ).fetchone()
        assert row[0] == "confirmed"
        conn2.close()


# ===========================================================================
# Review Metadata
# ===========================================================================

class TestReviewMetadata:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        import qmatsuite.mcp.knowledge as knowledge_mod
        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal
        journal = Journal(journal_dir=tmp_path / "journal_meta")
        set_journal(journal)
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_review_stores_metadata(self):
        """Review verdict is stored in metadata.review."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Metadata review test", grade="finding")
        iid = r["data"]["insight_id"]

        review_insight.fn(
            insight_id=iid, verdict="confirmed", reasoning="Looks good"
        )

        row = self._store.local_conn.execute(
            "SELECT metadata FROM insights WHERE id = ?", (iid,)
        ).fetchone()
        meta = json.loads(row[0])
        assert "review" in meta
        assert meta["review"]["verdict"] == "confirmed"
        assert meta["review"]["reasoning"] == "Looks good"
        assert "reviewed_at" in meta["review"]


# ===========================================================================
# Verified Status
# ===========================================================================

class TestVerifiedStatus:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        import qmatsuite.mcp.knowledge as knowledge_mod
        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal
        journal = Journal(journal_dir=tmp_path / "journal_verified")
        set_journal(journal)
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_verified_sets_status_and_citation(self):
        """review(verdict='verified', citation=...) → status='verified', citation in metadata."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding to verify", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid,
            verdict="verified",
            reasoning="Matches QE documentation",
            citation="https://www.quantum-espresso.org/Doc/INPUT_PW.html",
        )
        assert result["status"] == "success"
        assert result["data"]["new_status"] == "verified"

        row = self._store.local_conn.execute(
            "SELECT status, last_validated, metadata FROM insights WHERE id = ?", (iid,)
        ).fetchone()
        assert row["status"] == "verified"
        assert row["last_validated"] is not None
        meta = json.loads(row["metadata"])
        assert meta["review"]["citation"] == "https://www.quantum-espresso.org/Doc/INPUT_PW.html"

    def test_verified_requires_citation(self):
        """review(verdict='verified', citation='') → error."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding no citation", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid, verdict="verified", reasoning="Trust me"
        )
        assert result["status"] == "error"
        assert "citation" in result["message"].lower()

    def test_verified_requires_citation_min_length(self):
        """review(verdict='verified', citation='short') → error (<=10 chars)."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding short cit", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid, verdict="verified", reasoning="Short ref", citation="short"
        )
        assert result["status"] == "error"
        assert "citation" in result["message"].lower()

    def test_confirmed_citation_optional(self):
        """review(verdict='confirmed', citation='') → success."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding no cit ok", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid, verdict="confirmed", reasoning="Looks correct"
        )
        assert result["status"] == "success"

    def test_confirmed_stores_citation_if_given(self):
        """review(verdict='confirmed', citation=...) → citation in metadata."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding with optional cit", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid,
            verdict="confirmed",
            reasoning="Confirmed with ref",
            citation="https://example.com/optional-reference",
        )
        assert result["status"] == "success"

        row = self._store.local_conn.execute(
            "SELECT metadata FROM insights WHERE id = ?", (iid,)
        ).fetchone()
        meta = json.loads(row[0])
        assert meta["review"]["citation"] == "https://example.com/optional-reference"

    def test_verified_in_search_ranking(self):
        """Verified insight ranks above confirmed with same content."""
        store = self._store
        # Add two insights with same content
        r1 = store.add(_make_record(
            content="Unique quasar ranking test alpha beta gamma",
            grade="finding",
        ))
        r2 = store.add(_make_record(
            content="Unique quasar ranking test alpha beta gamma",
            grade="finding",
        ))
        # Make one verified, one confirmed
        store.update_status(r1["insight_id"], "verified", "Verified",
                            citation="https://example.com/long-enough-ref")
        store.update_status(r2["insight_id"], "confirmed", "Confirmed")

        results = store.search("quasar ranking test alpha beta gamma")
        matched = [r for r in results if r["id"] in (r1["insight_id"], r2["insight_id"])]
        assert len(matched) == 2
        # Verified should come first (higher weight)
        assert matched[0]["status"] == "verified"
        assert matched[1]["status"] == "confirmed"
