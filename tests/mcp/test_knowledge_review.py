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
        """Deprecate with superseded_by (no citation) → old deprecated, new confirmed."""
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

    def test_superseded_by_with_citation_auto_verifies(self):
        """Deprecate with superseded_by + url+excerpt → old deprecated, new verified."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r_old = record_insight.fn(content="Old finding to replace", grade="finding")
        r_new = record_insight.fn(content="Corrected replacement", grade="finding")
        old_id = r_old["data"]["insight_id"]
        new_id = r_new["data"]["insight_id"]

        url = "https://example.com/valid-ref"
        excerpt = "This is a verbatim excerpt from the source that is long enough to pass validation"
        result = review_insight.fn(
            insight_id=old_id,
            verdict="deprecated",
            reasoning="Literature contradicts this",
            superseded_by=new_id,
            citation_url=url,
            citation_excerpt=excerpt,
        )
        assert result["status"] == "success"
        assert result["data"]["superseded_by_status"] == "verified"

        old_row = self._store.local_conn.execute(
            "SELECT status FROM insights WHERE id = ?", (old_id,)
        ).fetchone()
        assert old_row["status"] == "deprecated"

        new_row = self._store.local_conn.execute(
            "SELECT status, metadata FROM insights WHERE id = ?", (new_id,)
        ).fetchone()
        assert new_row["status"] == "verified"
        meta = json.loads(new_row["metadata"])
        assert meta["review"]["citation_url"] == url
        assert meta["review"]["citation_excerpt"] == excerpt

    def test_superseded_by_without_citation_stays_confirmed(self):
        """Deprecate with superseded_by, no citation → new confirmed (no citation)."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r_old = record_insight.fn(content="Old finding no cit", grade="finding")
        r_new = record_insight.fn(content="New replacement no cit", grade="finding")
        old_id = r_old["data"]["insight_id"]
        new_id = r_new["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=old_id,
            verdict="deprecated",
            reasoning="Outdated approach",
            superseded_by=new_id,
        )
        assert result["status"] == "success"
        assert result["data"]["superseded_by_status"] == "confirmed"

        new_row = self._store.local_conn.execute(
            "SELECT status, metadata FROM insights WHERE id = ?", (new_id,)
        ).fetchone()
        assert new_row["status"] == "confirmed"
        meta = json.loads(new_row["metadata"])
        assert "citation_url" not in meta.get("review", {})

    def test_superseded_by_does_not_downgrade_verified(self):
        """Auto-confirm must not downgrade a verified replacement to confirmed."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        # Create replacement and verify it first
        r_new = record_insight.fn(content="Already verified replacement", grade="finding")
        new_id = r_new["data"]["insight_id"]
        review_insight.fn(
            insight_id=new_id,
            verdict="verified",
            reasoning="Literature confirms this",
            citation_url="https://example.com/proof",
            citation_excerpt="This is a sufficiently long verbatim excerpt from the source document for validation",
        )
        row = self._store.local_conn.execute(
            "SELECT status FROM insights WHERE id = ?", (new_id,)
        ).fetchone()
        assert row["status"] == "verified"

        # Now deprecate an old insight with superseded_by pointing to the verified one (no citation)
        r_old = record_insight.fn(content="Old finding to deprecate", grade="finding")
        old_id = r_old["data"]["insight_id"]
        result = review_insight.fn(
            insight_id=old_id,
            verdict="deprecated",
            reasoning="Replaced by better version",
            superseded_by=new_id,
        )
        assert result["status"] == "success"
        assert result["data"]["superseded_by_status"] == "verified"

        # Replacement must still be verified, not downgraded to confirmed
        row = self._store.local_conn.execute(
            "SELECT status FROM insights WHERE id = ?", (new_id,)
        ).fetchone()
        assert row["status"] == "verified"

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

    _SAMPLE_URL = "https://www.quantum-espresso.org/Doc/INPUT_PW.html"
    _SAMPLE_EXCERPT = (
        "ecutwfc: kinetic energy cutoff (Ry) for wavefunctions. "
        "This is the main convergence parameter."
    )

    def test_verified_sets_status_and_citation(self):
        """review(verdict='verified', url+excerpt) → status='verified', both in metadata."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding to verify", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid,
            verdict="verified",
            reasoning="Matches QE documentation",
            citation_url=self._SAMPLE_URL,
            citation_excerpt=self._SAMPLE_EXCERPT,
        )
        assert result["status"] == "success"
        assert result["data"]["new_status"] == "verified"

        row = self._store.local_conn.execute(
            "SELECT status, last_validated, metadata FROM insights WHERE id = ?", (iid,)
        ).fetchone()
        assert row["status"] == "verified"
        assert row["last_validated"] is not None
        meta = json.loads(row["metadata"])
        assert meta["review"]["citation_url"] == self._SAMPLE_URL
        assert meta["review"]["citation_excerpt"] == self._SAMPLE_EXCERPT

    def test_verified_requires_url_nonempty(self):
        """review(verdict='verified', citation_url='') → error."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding no url", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid, verdict="verified", reasoning="Trust me",
            citation_excerpt=self._SAMPLE_EXCERPT,
        )
        assert result["status"] == "error"
        assert "citation_url" in result["message"]

    def test_verified_requires_url_format(self):
        """review(verdict='verified', citation_url='not a url') → error."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding bad url", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid, verdict="verified", reasoning="Bad URL",
            citation_url="not a url",
            citation_excerpt=self._SAMPLE_EXCERPT,
        )
        assert result["status"] == "error"
        assert "http" in result["message"].lower()

    def test_verified_requires_excerpt_nonempty(self):
        """review(verdict='verified', citation_excerpt='') → error."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding no excerpt", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid, verdict="verified", reasoning="No excerpt",
            citation_url=self._SAMPLE_URL,
            citation_excerpt="",
        )
        assert result["status"] == "error"
        assert "citation_excerpt" in result["message"]

    def test_verified_requires_excerpt_min_length(self):
        """review(verdict='verified', citation_excerpt='short') → error (<50 chars)."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding short excerpt", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid, verdict="verified", reasoning="Short excerpt",
            citation_url=self._SAMPLE_URL,
            citation_excerpt="too short to be a real excerpt",
        )
        assert result["status"] == "error"
        assert "50" in result["message"]

    def test_confirmed_accepts_empty_citation(self):
        """review(verdict='confirmed', no url/excerpt) → success."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding no cit ok", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid, verdict="confirmed", reasoning="Looks correct"
        )
        assert result["status"] == "success"

    def test_confirmed_stores_citation_if_given(self):
        """review(verdict='confirmed', url+excerpt given) → stored in metadata."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r = record_insight.fn(content="Finding with optional cit", grade="finding")
        iid = r["data"]["insight_id"]

        result = review_insight.fn(
            insight_id=iid,
            verdict="confirmed",
            reasoning="Confirmed with ref",
            citation_url="https://example.com/optional-reference",
            citation_excerpt="This optional excerpt is long enough to store but not required for confirmed",
        )
        assert result["status"] == "success"

        row = self._store.local_conn.execute(
            "SELECT metadata FROM insights WHERE id = ?", (iid,)
        ).fetchone()
        meta = json.loads(row[0])
        assert meta["review"]["citation_url"] == "https://example.com/optional-reference"
        assert "citation_excerpt" in meta["review"]

    def test_superseded_inherits_both_url_and_excerpt(self):
        """deprecated with superseded_by + url + excerpt → new has both in metadata."""
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.record_insight import record_insight

        r_old = record_insight.fn(content="Old finding inherit test", grade="finding")
        r_new = record_insight.fn(content="New replacement inherit test", grade="finding")
        old_id = r_old["data"]["insight_id"]
        new_id = r_new["data"]["insight_id"]

        url = "https://example.com/inheritance-source"
        excerpt = "This verbatim excerpt should propagate to the replacement insight metadata"
        result = review_insight.fn(
            insight_id=old_id,
            verdict="deprecated",
            reasoning="Superseded with citation",
            superseded_by=new_id,
            citation_url=url,
            citation_excerpt=excerpt,
        )
        assert result["status"] == "success"
        assert result["data"]["superseded_by_status"] == "verified"

        new_row = self._store.local_conn.execute(
            "SELECT status, metadata FROM insights WHERE id = ?", (new_id,)
        ).fetchone()
        assert new_row["status"] == "verified"
        meta = json.loads(new_row["metadata"])
        assert meta["review"]["citation_url"] == url
        assert meta["review"]["citation_excerpt"] == excerpt

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
        store.update_status(
            r1["insight_id"], "verified", "Verified",
            citation_url="https://example.com/long-enough-ref",
            citation_excerpt="A sufficiently long excerpt for the ranking test to pass validation",
        )
        store.update_status(r2["insight_id"], "confirmed", "Confirmed")

        results = store.search("quasar ranking test alpha beta gamma")
        matched = [r for r in results if r["id"] in (r1["insight_id"], r2["insight_id"])]
        assert len(matched) == 2
        # Verified should come first (higher weight)
        assert matched[0]["status"] == "verified"
        assert matched[1]["status"] == "confirmed"


# ===========================================================================
# search_knowledge context_hint — deprecated/replacement warnings
# ===========================================================================

class TestSearchDeprecatedWarnings:
    @pytest.fixture(autouse=True)
    def _patch_deps(self, store, tmp_path, monkeypatch):
        import qmatsuite.mcp.knowledge as knowledge_mod
        monkeypatch.setattr(knowledge_mod, "_store", store)
        from qmatsuite.core.journal import Journal, set_journal, reset_journal
        journal = Journal(journal_dir=tmp_path / "journal_search_warn")
        set_journal(journal)
        self._store = store
        yield
        monkeypatch.setattr(knowledge_mod, "_store", None)
        reset_journal()

    def test_search_warns_about_deprecated_with_replacement(self):
        """context_hint warns when deprecated findings with replacements are returned."""
        from qmatsuite.mcp.tools.record_insight import record_insight
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        r_old = record_insight.fn(
            content="Zirconium deprecated search warn test old finding",
            grade="finding",
        )
        old_id = r_old["data"]["insight_id"]
        r_new = record_insight.fn(
            content="Zirconium deprecated search warn test corrected replacement",
            grade="finding",
        )
        new_id = r_new["data"]["insight_id"]
        review_insight.fn(
            insight_id=old_id,
            verdict="deprecated",
            reasoning="Replaced by corrected version",
            superseded_by=new_id,
        )

        result = search_knowledge.fn(query="zirconium deprecated search warn test")
        hint = result["context_hint"]
        assert "was deprecated" in hint
        assert "replaced by" in hint
        assert "Read replacement findings before choosing parameters" in hint

    def test_search_no_warning_when_no_deprecated(self):
        """context_hint does NOT contain deprecated warning for active-only results."""
        from qmatsuite.mcp.tools.record_insight import record_insight
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        record_insight.fn(
            content="Hafnium active search no warn test finding",
            grade="finding",
        )

        result = search_knowledge.fn(query="hafnium active search no warn test")
        hint = result["context_hint"]
        assert "deprecated" not in hint

    def test_replacement_finding_has_prefix_in_search(self):
        """Replacement findings are prefixed with [CORRECTS DEPRECATED FINDING]."""
        from qmatsuite.mcp.tools.record_insight import record_insight
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        r_old = record_insight.fn(
            content="Plutonium replacement prefix test old finding",
            grade="finding",
        )
        old_id = r_old["data"]["insight_id"]
        r_new = record_insight.fn(
            content="Plutonium replacement prefix test corrected version",
            grade="finding",
        )
        new_id = r_new["data"]["insight_id"]
        review_insight.fn(
            insight_id=old_id,
            verdict="deprecated",
            reasoning="Replaced by corrected version",
            superseded_by=new_id,
        )

        result = search_knowledge.fn(query="plutonium replacement prefix test")
        items = result["data"]["results"]
        replacement = [i for i in items if i["id"] == new_id]
        assert len(replacement) == 1
        assert replacement[0]["content"].startswith("\u26a0\ufe0f[CORRECTS DEPRECATED FINDING]")

    def test_replacement_finding_ranks_above_normal_confirmed(self):
        """Replacement findings get 2x rank boost, appearing in top 3."""
        from qmatsuite.mcp.tools.record_insight import record_insight
        from qmatsuite.mcp.tools.review_insight import review_insight
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        # Create 5 confirmed findings about the same topic
        for i in range(5):
            r = record_insight.fn(
                content=f"Osmium AHC rank boost test normal finding number {i}",
                grade="finding",
            )
            review_insight.fn(
                insight_id=r["data"]["insight_id"],
                verdict="confirmed",
                reasoning="Looks correct",
            )

        # Create old finding + replacement
        r_old = record_insight.fn(
            content="Osmium AHC rank boost test old wrong finding",
            grade="finding",
        )
        old_id = r_old["data"]["insight_id"]
        r_new = record_insight.fn(
            content="Osmium AHC rank boost test corrected replacement",
            grade="finding",
        )
        new_id = r_new["data"]["insight_id"]
        review_insight.fn(
            insight_id=old_id,
            verdict="deprecated",
            reasoning="Replaced by corrected version",
            superseded_by=new_id,
        )

        result = search_knowledge.fn(query="osmium AHC rank boost test")
        items = result["data"]["results"]
        non_deprecated = [i for i in items if i["status"] != "deprecated"]
        # Replacement should be in top 3 of non-deprecated results
        top3_ids = [i["id"] for i in non_deprecated[:3]]
        assert new_id in top3_ids, (
            f"Replacement {new_id} not in top 3: {top3_ids}"
        )
