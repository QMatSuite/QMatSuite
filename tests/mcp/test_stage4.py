"""Stage 4 MCP knowledge infrastructure tests.

Tests the knowledge schema, builtin content, search store, and
search_knowledge MCP tool.

All tests use a temporary database (no side effects on the real builtin.db).
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from qmatsuite.mcp.knowledge.schema import SCHEMA_DDL, init_db
from qmatsuite.mcp.knowledge.builtin_entries import BUILTIN_ENTRIES
from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db
from qmatsuite.mcp.knowledge.store import KnowledgeStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Return a temp path for a knowledge database."""
    return tmp_path / "knowledge" / "test.db"


@pytest.fixture
def populated_db(db_path):
    """Build a populated builtin.db in a temp directory and return its path."""
    build_builtin_db(output_path=db_path)
    return db_path


@pytest.fixture
def store(populated_db):
    """Return a KnowledgeStore backed by the populated temp db."""
    s = KnowledgeStore(db_path=populated_db)
    yield s
    s.close()


# ===========================================================================
# Schema tests (2)
# ===========================================================================


class TestSchema:
    def test_creates_tables(self, db_path):
        """init_db creates the insights table and FTS5 virtual table."""
        conn = init_db(db_path)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
                ).fetchall()
            }
            assert "insights" in tables
            assert "insights_fts" in tables
        finally:
            conn.close()

    def test_idempotent(self, db_path):
        """Calling init_db twice does not error."""
        conn1 = init_db(db_path)
        conn1.close()
        conn2 = init_db(db_path)
        try:
            count = conn2.execute("SELECT COUNT(*) FROM insights").fetchone()[0]
            assert count == 0  # empty, no data yet
        finally:
            conn2.close()


# ===========================================================================
# Builtin content tests (4)
# ===========================================================================


class TestBuiltinContent:
    def test_minimum_entry_count(self):
        """BUILTIN_ENTRIES has at least 20 curated entries."""
        assert len(BUILTIN_ENTRIES) >= 20

    def test_entries_have_valid_schema(self):
        """Every entry has the required fields with valid values."""
        valid_grades = {"bookkeeping", "observation", "finding", "pattern", "principle"}
        valid_confidences = {"low", "medium", "high"}
        valid_source_types = {
            "local", "builtin", "literature", "docs",
            "mailinglist", "tutorial", "community",
        }

        for i, entry in enumerate(BUILTIN_ENTRIES):
            assert entry["grade"] in valid_grades, f"entry {i}: bad grade"
            assert entry.get("confidence", "medium") in valid_confidences, (
                f"entry {i}: bad confidence"
            )
            assert entry.get("source_type", "local") in valid_source_types, (
                f"entry {i}: bad source_type"
            )
            assert entry["content"], f"entry {i}: empty content"
            assert entry["created_by"], f"entry {i}: empty created_by"
            # Tags should be valid JSON array
            tags = entry.get("tags")
            if tags:
                parsed = json.loads(tags)
                assert isinstance(parsed, list), f"entry {i}: tags not a list"

    def test_error_recovery_tagged(self):
        """At least 5 entries are tagged with 'error_recovery'."""
        count = 0
        for entry in BUILTIN_ENTRIES:
            tags = entry.get("tags", "[]")
            if "error_recovery" in tags:
                count += 1
        assert count >= 5

    def test_multi_engine_coverage(self):
        """Entries cover multiple engines (at least wildcard + 1 specific)."""
        engines = {entry.get("scope_engine", "*") for entry in BUILTIN_ENTRIES}
        assert "*" in engines, "should have wildcard entries"
        specific = engines - {"*"}
        assert len(specific) >= 1, "should have at least one engine-specific entry"

    def test_build_populates_db(self, populated_db):
        """build_builtin_db creates a DB with all entries."""
        conn = sqlite3.connect(str(populated_db))
        conn.row_factory = sqlite3.Row
        try:
            count = conn.execute("SELECT COUNT(*) FROM insights").fetchone()[0]
            assert count == len(BUILTIN_ENTRIES)
        finally:
            conn.close()

    def test_build_idempotent(self, db_path):
        """Running build_builtin_db twice produces the same count."""
        build_builtin_db(output_path=db_path)
        build_builtin_db(output_path=db_path)
        conn = sqlite3.connect(str(db_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM insights").fetchone()[0]
            assert count == len(BUILTIN_ENTRIES)
        finally:
            conn.close()


# ===========================================================================
# Search tests (6)
# ===========================================================================


class TestSearch:
    def test_fts_query(self, store):
        """Free-text query for 'SCF convergence' returns results."""
        results = store.search("SCF convergence")
        assert len(results) > 0
        # All results should have content
        for r in results:
            assert r["content"]

    def test_engine_filter(self, store):
        """Filtering by engine='qe' returns only QE or wildcard entries."""
        results = store.search("convergence", engine="qe")
        for r in results:
            assert r["scope_engine"] in ("qe", "*")

    def test_system_type_filter(self, store):
        """Filtering by system_type='metal' returns metal or wildcard entries."""
        results = store.search("smearing", system_type="metal")
        for r in results:
            assert r["scope_system_type"] in ("metal", "*")

    def test_empty_results(self, store):
        """Query for nonsense returns empty list."""
        results = store.search("xyzzy_nonexistent_term_12345")
        assert results == []

    def test_ranking_principles_above_findings(self, store):
        """Principles should appear before findings when both match."""
        results = store.search("smearing metal")
        grades = [r["grade"] for r in results]
        if "principle" in grades and "finding" in grades:
            first_principle = grades.index("principle")
            first_finding = grades.index("finding")
            assert first_principle < first_finding

    def test_count(self, store):
        """count() returns the total number of active entries."""
        assert store.count() == len(BUILTIN_ENTRIES)

    def test_get_by_id(self, store):
        """get_by_id returns a full entry dict."""
        results = store.search("SCF")
        assert results, "should have SCF results"
        entry = store.get_by_id(results[0]["id"])
        assert entry is not None
        assert entry["content"] == results[0]["content"]

    def test_get_by_id_missing(self, store):
        """get_by_id returns None for nonexistent ID."""
        assert store.get_by_id("NONEXISTENT_ID") is None


# ===========================================================================
# MCP tool tests (3)
# ===========================================================================


class TestMCPTool:
    @pytest.fixture(autouse=True)
    def _patch_store(self, populated_db, monkeypatch):
        """Patch the knowledge store singleton to use our temp DB."""
        import qmatsuite.mcp.knowledge as knowledge_mod

        s = KnowledgeStore(db_path=populated_db)
        monkeypatch.setattr(knowledge_mod, "_store", s)
        yield
        s.close()
        monkeypatch.setattr(knowledge_mod, "_store", None)

    def test_envelope_structure(self):
        """Tool returns standard MCP envelope with status/data/context_hint."""
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        result = search_knowledge.fn(query="SCF convergence")
        assert result["status"] == "success"
        assert "data" in result
        assert "context_hint" in result
        assert result["data"]["total_results"] > 0

    def test_filter_passthrough(self):
        """Engine filter is reflected in the response and filters results."""
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        result = search_knowledge.fn(query="convergence", engine="qe")
        assert result["status"] == "success"
        assert result["data"]["filters"]["engine"] == "qe"
        for item in result["data"]["results"]:
            assert item["scope_engine"] in ("qe", "*")

    def test_no_results_hint(self):
        """Empty results produce a helpful context_hint."""
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        result = search_knowledge.fn(query="xyzzy_nonexistent_12345")
        assert result["status"] == "success"
        assert result["data"]["total_results"] == 0
        assert "No matching" in result["context_hint"]

    def test_content_truncation(self):
        """Content in results is truncated to ~500 chars."""
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        result = search_knowledge.fn(query="SCF")
        for item in result["data"]["results"]:
            assert len(item["content"]) <= 503  # 500 + "..."
