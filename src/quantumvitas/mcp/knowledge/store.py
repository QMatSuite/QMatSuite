"""KnowledgeStore — search and query interface for the knowledge database."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Optional

from quantumvitas.mcp.knowledge.schema import init_db

# Regex to extract word tokens (alphanumeric + underscore) from a raw query.
_FTS5_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")

# FTS5 boolean keywords that could interfere if left in the query.
_FTS5_RESERVED = frozenset({"AND", "OR", "NOT", "NEAR"})


def _sanitize_fts_query(raw: str) -> str:
    """Strip FTS5 operators/punctuation; keep only word tokens.

    FTS5 interprets ``-`` as NOT, ``"`` as phrase delimiter, and words like
    AND/OR/NOT/NEAR as boolean operators.  This helper strips all of them so
    that user queries such as ``"Quantum-ESPRESSO"`` or ``"SCF non-convergence"``
    never trigger FTS5 syntax errors.
    """
    tokens = _FTS5_TOKEN_RE.findall(raw)
    tokens = [t for t in tokens if t.upper() not in _FTS5_RESERVED]
    return " ".join(tokens)

# Confidence weights for ranking (higher = more trusted).
_CONFIDENCE_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}

# Grade ordering for tie-breaking (higher = more authoritative).
_GRADE_ORDER = {"principle": 4, "finding": 3, "observation": 2, "bookkeeping": 1}


def _default_db_path() -> Path:
    """Return the default builtin.db path under .qmatsuite/knowledge/."""
    from quantumvitas.core.paths import get_qmatsuite_home_root

    return get_qmatsuite_home_root() / "knowledge" / "builtin.db"


class KnowledgeStore:
    """Read-only search interface over a knowledge SQLite database.

    Parameters
    ----------
    db_path : Path | None
        Explicit database path.  When *None*, falls back to
        ``~/.qmatsuite/knowledge/builtin.db`` and lazily creates the
        schema if needed.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _default_db_path()
        self._conn: Optional[sqlite3.Connection] = None

    # -- connection management ------------------------------------------------

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = init_db(self._db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- public API -----------------------------------------------------------

    def count(self) -> int:
        """Return total number of active insights."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM insights WHERE status = 'active'"
        ).fetchone()
        return row[0] if row else 0

    def get_by_id(self, insight_id: str) -> Optional[dict]:
        """Return a single insight by ID, or *None*."""
        row = self.conn.execute(
            "SELECT * FROM insights WHERE id = ?", (insight_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def search(
        self,
        query_text: str = "",
        *,
        engine: str = "",
        workflow: str = "",
        system_type: str = "",
        method: str = "",
        grade_min: str = "",
        confidence_min: str = "",
        limit: int = 10,
    ) -> list[dict]:
        """Full-text + scope-filtered search with ranked results.

        Ranking formula: ``confidence_weight × bm25_rank``, with grade
        used as a secondary sort (principles above findings).
        """
        limit = max(1, min(limit, 50))

        if query_text.strip():
            return self._fts_search(
                query_text,
                engine=engine,
                workflow=workflow,
                system_type=system_type,
                method=method,
                grade_min=grade_min,
                confidence_min=confidence_min,
                limit=limit,
            )
        else:
            return self._scope_search(
                engine=engine,
                workflow=workflow,
                system_type=system_type,
                method=method,
                grade_min=grade_min,
                confidence_min=confidence_min,
                limit=limit,
            )

    # -- internal helpers -----------------------------------------------------

    def _fts_search(
        self,
        query_text: str,
        *,
        engine: str,
        workflow: str,
        system_type: str,
        method: str,
        grade_min: str,
        confidence_min: str,
        limit: int,
    ) -> list[dict]:
        """FTS5-based search with scope filters."""
        safe_query = _sanitize_fts_query(query_text)
        if not safe_query.strip():
            return []  # All tokens were stripped — nothing to match

        # Build FTS match expression — rank by bm25
        sql = """
            SELECT i.*, bm25(insights_fts) AS rank
            FROM insights_fts f
            JOIN insights i ON i.rowid = f.rowid
            WHERE insights_fts MATCH ?
              AND i.status = 'active'
        """
        params: list = [safe_query]

        sql, params = self._add_scope_filters(
            sql, params, engine, workflow, system_type, method,
            grade_min, confidence_min,
        )

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        results = [dict(r) for r in rows]

        # Re-rank: confidence_weight × abs(bm25_rank), then grade
        for r in results:
            cw = _CONFIDENCE_WEIGHT.get(r.get("confidence", "medium"), 2.0)
            r["_score"] = cw * abs(r.get("rank", 0))

        results.sort(
            key=lambda r: (r["_score"], _GRADE_ORDER.get(r.get("grade", ""), 0)),
            reverse=True,
        )

        # Clean up internal keys
        for r in results:
            r.pop("_score", None)
            r.pop("rank", None)

        return results

    def _scope_search(
        self,
        *,
        engine: str,
        workflow: str,
        system_type: str,
        method: str,
        grade_min: str,
        confidence_min: str,
        limit: int,
    ) -> list[dict]:
        """Non-FTS search using only scope filters."""
        sql = "SELECT i.* FROM insights i WHERE i.status = 'active'"
        params: list = []

        sql, params = self._add_scope_filters(
            sql, params, engine, workflow, system_type, method,
            grade_min, confidence_min,
        )

        sql += " ORDER BY i.grade DESC, i.confidence DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _add_scope_filters(
        sql: str,
        params: list,
        engine: str,
        workflow: str,
        system_type: str,
        method: str,
        grade_min: str,
        confidence_min: str,
    ) -> tuple[str, list]:
        """Append WHERE clauses for scope and quality filters."""
        if engine:
            sql += " AND (i.scope_engine = ? OR i.scope_engine = '*')"
            params.append(engine.lower())
        if workflow:
            sql += " AND (i.scope_workflow = ? OR i.scope_workflow = '*')"
            params.append(workflow.lower())
        if system_type:
            sql += " AND (i.scope_system_type = ? OR i.scope_system_type = '*')"
            params.append(system_type.lower())
        if method:
            sql += " AND (i.scope_method = ? OR i.scope_method = '*')"
            params.append(method.lower())

        if grade_min:
            min_order = _GRADE_ORDER.get(grade_min, 0)
            grades = [g for g, o in _GRADE_ORDER.items() if o >= min_order]
            if grades:
                placeholders = ", ".join("?" for _ in grades)
                sql += f" AND i.grade IN ({placeholders})"
                params.extend(grades)

        if confidence_min:
            min_weight = _CONFIDENCE_WEIGHT.get(confidence_min, 0)
            confs = [c for c, w in _CONFIDENCE_WEIGHT.items() if w >= min_weight]
            if confs:
                placeholders = ", ".join("?" for _ in confs)
                sql += f" AND i.confidence IN ({placeholders})"
                params.extend(confs)

        return sql, params
