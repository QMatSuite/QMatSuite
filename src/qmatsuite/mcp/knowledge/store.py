"""KnowledgeStore — search, query, and write interface for the knowledge database."""

from __future__ import annotations

import json
import os
import random
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from qmatsuite.mcp.knowledge.schema import init_db

# Regex to extract word tokens (alphanumeric + underscore) from a raw query.
_FTS5_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")

# FTS5 boolean keywords that could interfere if left in the query.
_FTS5_RESERVED = frozenset({"AND", "OR", "NOT", "NEAR"})


def _sanitize_fts_query(raw: str) -> str:
    """Strip FTS5 operators/punctuation; keep only word tokens joined with OR.

    FTS5 interprets ``-`` as NOT, ``"`` as phrase delimiter, and words like
    AND/OR/NOT/NEAR as boolean operators.  This helper strips all of them so
    that user queries such as ``"Quantum-ESPRESSO"`` or ``"SCF non-convergence"``
    never trigger FTS5 syntax errors.

    Tokens are joined with OR so that multi-word queries return documents
    matching *any* token.  BM25 ranking naturally scores documents matching
    more tokens higher, so the most relevant results appear first.
    """
    tokens = _FTS5_TOKEN_RE.findall(raw)
    tokens = [t for t in tokens if t.upper() not in _FTS5_RESERVED]
    return " OR ".join(tokens)

# Confidence weights for ranking (higher = more trusted).
_CONFIDENCE_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}

# Grade ordering for tie-breaking (higher = more authoritative).
_GRADE_ORDER = {"principle": 5, "pattern": 4, "finding": 3, "observation": 2, "bookkeeping": 1}

# Trust weights by source_type (multiplier in ranking formula).
TRUST_WEIGHTS = {
    "builtin": 1.0,
    "local": 1.0,
    "literature": 0.9,
    "docs": 0.85,
    "mailinglist": 0.7,
    "tutorial": 0.7,
    "community": 0.6,
}
_DEFAULT_TRUST = 0.5

# Contradiction threshold: entries reaching this count are set to "under_review".
_CONTRADICTION_THRESHOLD = 3

# Scope fields used for contradiction matching.
_SCOPE_FIELDS = ("scope_engine", "scope_workflow", "scope_system_type", "scope_method")

# Valid grades for the add() method.
_VALID_GRADES = frozenset(_GRADE_ORDER.keys())

# Grades that get promoted to the knowledge DB.
_PROMOTABLE_GRADES = frozenset({"finding", "pattern", "principle"})


def _builtin_enabled() -> bool:
    """Return True unless QMS_KNOWLEDGE_BUILTIN is explicitly set to '0'."""
    return os.environ.get("QMS_KNOWLEDGE_BUILTIN", "1") != "0"


# Number of result slots reserved for local (session-generated) insights.
LOCAL_RESERVED_SLOTS = 3


def _merge_with_reserved_slots(
    local_results: list[dict],
    builtin_results: list[dict],
    limit: int,
    reserved: int = LOCAL_RESERVED_SLOTS,
) -> list[dict]:
    """Merge local and builtin results, reserving *reserved* slots for local.

    Local entries come first (up to *reserved*), then builtin entries fill
    the remaining slots up to *limit*.
    """
    local_take = local_results[: min(reserved, len(local_results))]
    remaining = limit - len(local_take)
    builtin_take = builtin_results[:max(0, remaining)]
    return local_take + builtin_take


def _default_db_path() -> Path:
    """Return the default builtin.db path under .qmatsuite/knowledge/."""
    from qmatsuite.core.paths import get_qmatsuite_home_root

    return get_qmatsuite_home_root() / "knowledge" / "builtin.db"


def _local_db_path() -> Path:
    """Return the default local.db path under .qmatsuite/knowledge/."""
    from qmatsuite.core.paths import get_qmatsuite_home_root

    return get_qmatsuite_home_root() / "knowledge" / "local.db"


class KnowledgeStore:
    """Search and write interface over builtin + local knowledge databases.

    Parameters
    ----------
    db_path : Path | None
        Explicit builtin database path.  When *None*, falls back to
        ``~/.qmatsuite/knowledge/builtin.db``.
    local_db_path : Path | None
        Explicit local database path.  When *None*, no local DB is used.
        The local DB is created lazily on first write.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        local_db_path: Optional[Path] = None,
    ) -> None:
        self._db_path = db_path or _default_db_path()
        self._local_db_path = local_db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._local_conn: Optional[sqlite3.Connection] = None

    # -- connection management ------------------------------------------------

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = init_db(self._db_path)
        return self._conn

    @property
    def local_conn(self) -> sqlite3.Connection:
        """Lazy-init local.db connection — creates the file on first access."""
        if self._local_conn is None:
            if self._local_db_path is None:
                raise RuntimeError("No local_db_path configured for writes")
            self._local_conn = init_db(self._local_db_path)
        return self._local_conn

    def _has_local_db(self) -> bool:
        """Return True if local.db file exists (for read-only checks)."""
        if self._local_conn is not None:
            return True
        return self._local_db_path is not None and self._local_db_path.exists()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self._local_conn is not None:
            self._local_conn.close()
            self._local_conn = None

    # -- public API -----------------------------------------------------------

    def count(self) -> int:
        """Return total number of active insights in builtin DB."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM insights WHERE status = 'active'"
        ).fetchone()
        return row[0] if row else 0

    def get_by_id(self, insight_id: str) -> Optional[dict]:
        """Return a single insight by ID, or *None*."""
        row = self.conn.execute(
            "SELECT * FROM insights WHERE id = ?", (insight_id,)
        ).fetchone()
        if row is not None:
            return dict(row)
        # Check local DB
        if self._has_local_db():
            local = self.local_conn.execute(
                "SELECT * FROM insights WHERE id = ?", (insight_id,)
            ).fetchone()
            if local is not None:
                return dict(local)
        return None

    def add(self, record) -> dict:
        """Add an insight record to the knowledge store.

        Parameters
        ----------
        record : InsightRecord
            The insight to add.

        Returns
        -------
        dict
            ``{"promoted": bool, "insight_id": str|None, "contradictions": list}``

        Raises
        ------
        ValueError
            If grade is invalid or content is empty.
        """
        if record.grade not in _VALID_GRADES:
            raise ValueError(
                f"Invalid grade {record.grade!r}; must be one of {sorted(_VALID_GRADES)}"
            )
        if not record.content or not record.content.strip():
            raise ValueError("Content must be non-empty")

        # Grades below finding are journal-only (caller handles journal write).
        if record.grade not in _PROMOTABLE_GRADES:
            return {"promoted": False, "insight_id": None, "contradictions": []}

        import ulid as _ulid

        insight_id = str(_ulid.new())
        now = datetime.now(timezone.utc).isoformat()

        scope_engine = record.scope.get("engine", "*")
        scope_workflow = record.scope.get("workflow", "*")
        scope_system_type = record.scope.get("system_type", "*")
        scope_method = record.scope.get("method", "*")

        tags_json = json.dumps(record.tags) if record.tags else "[]"

        # Build provenance metadata
        metadata = {
            "agent_model": os.environ.get("QMS_AGENT_MODEL", "unknown"),
            "created_at": now,
        }
        if record.source_calculation:
            metadata["source_calculation"] = record.source_calculation
        if record.references:
            metadata["references"] = record.references
        if record.citations:
            metadata["citations"] = record.citations
        metadata_json = json.dumps(metadata)

        # Write to local DB (creates file if needed).
        self.local_conn.execute(
            """
            INSERT INTO insights (
                id, grade,
                scope_engine, scope_workflow, scope_system_type, scope_method,
                content, confidence,
                source_type, source_origin, provenance_ref,
                created_by, tags,
                status, contradiction_count, upvotes, metadata,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, 0, ?, ?, ?)
            """,
            (
                insight_id,
                record.grade,
                scope_engine,
                scope_workflow,
                scope_system_type,
                scope_method,
                record.content,
                "medium",
                "local",
                None,
                None,
                record.created_by,
                tags_json,
                metadata_json,
                now,
                now,
            ),
        )
        self.local_conn.commit()

        # Contradiction detection
        contradictions = self._detect_contradictions(
            insight_id, scope_engine, scope_workflow, scope_system_type, scope_method,
        )

        return {
            "promoted": True,
            "insight_id": insight_id,
            "contradictions": contradictions,
        }

    def list_by_grade(self, grade: str, limit: int = 20, compound: str = "") -> dict:
        """List insights from local.db by grade, ordered by created_at DESC."""
        if not self._has_local_db():
            return {"grade": grade, "total": 0, "insights": []}
        sql = "SELECT * FROM insights WHERE grade = ? AND status = 'active'"
        params: list = [grade]
        if compound:
            sql += " AND tags LIKE ?"
            params.append(f"%{compound}%")
        count_sql = sql.replace("SELECT *", "SELECT COUNT(*)")
        total = self.local_conn.execute(count_sql, params).fetchone()[0]
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 100)))
        rows = self.local_conn.execute(sql, params).fetchall()
        return {"grade": grade, "total": total, "insights": [dict(r) for r in rows]}

    def resolve_short_id(self, prefix: str) -> str:
        """Resolve a short ID prefix to the full ULID.

        Raises ValueError if no match or ambiguous match.
        """
        if not self._has_local_db():
            raise ValueError(f"No insight found matching prefix '{prefix}'")
        rows = self.local_conn.execute(
            "SELECT id FROM insights WHERE id LIKE ? || '%'",
            (prefix,),
        ).fetchall()
        if len(rows) == 0:
            raise ValueError(f"No insight found matching prefix '{prefix}'")
        if len(rows) > 1:
            raise ValueError(
                f"Ambiguous prefix '{prefix}' matches {len(rows)} insights; use longer prefix"
            )
        return rows[0][0]

    def apply_citations(self, citations: list[dict]) -> dict[str, int]:
        """Update vote counters for cited insights in local.db.

        Parameters
        ----------
        citations : list[dict]
            Each dict has ``{"id": str, "vote": "up"|"down"}``.

        Returns
        -------
        dict
            ``{"applied_up": int, "applied_down": int, "skipped": int}``
        """
        applied_up = 0
        applied_down = 0
        skipped = 0
        if not self._has_local_db():
            return {"applied_up": 0, "applied_down": 0, "skipped": len(citations)}
        for cit in citations:
            cit_id = cit.get("id", "")
            vote = cit.get("vote", "")
            if vote not in ("up", "down"):
                skipped += 1
                continue
            col = "upvotes" if vote == "up" else "downvotes"
            cur = self.local_conn.execute(
                f"UPDATE insights SET {col} = {col} + 1 WHERE id = ?",  # noqa: S608
                (cit_id,),
            )
            if cur.rowcount > 0:
                if vote == "up":
                    applied_up += 1
                else:
                    applied_down += 1
            else:
                skipped += 1
        if applied_up or applied_down:
            self.local_conn.commit()
        return {"applied_up": applied_up, "applied_down": applied_down, "skipped": skipped}

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

        Searches both builtin and local databases, merges results with
        trust-weighted ranking: ``confidence_weight * bm25_rank * trust_weight``.
        """
        limit = max(1, min(limit, 50))

        kwargs = dict(
            engine=engine,
            workflow=workflow,
            system_type=system_type,
            method=method,
            grade_min=grade_min,
            confidence_min=confidence_min,
            limit=limit,
        )

        if query_text.strip():
            builtin_results: list[dict] = []
            if _builtin_enabled():
                builtin_results = self._fts_search(query_text, conn=self.conn, **kwargs)
                self._apply_trust_ranking(builtin_results)
            local_results: list[dict] = []
            if self._has_local_db():
                local_results = self._fts_search(
                    query_text, conn=self.local_conn, **kwargs,
                )
                self._apply_trust_ranking(local_results)
            results = _merge_with_reserved_slots(local_results, builtin_results, limit)
        else:
            builtin_results = []
            if _builtin_enabled():
                builtin_results = self._scope_search(conn=self.conn, **kwargs)
            local_results = []
            if self._has_local_db():
                local_results = self._scope_search(conn=self.local_conn, **kwargs)
            _sort_scope = lambda r: (
                _GRADE_ORDER.get(r.get("grade", ""), 0),
                _CONFIDENCE_WEIGHT.get(r.get("confidence", "medium"), 2.0),
            )
            builtin_results.sort(key=_sort_scope, reverse=True)
            local_results.sort(key=_sort_scope, reverse=True)
            results = _merge_with_reserved_slots(local_results, builtin_results, limit)

        # Annotate entries under review
        for r in results:
            if r.get("contradiction_count", 0) >= _CONTRADICTION_THRESHOLD:
                r["content"] = "[UNDER REVIEW] " + r["content"]

        return results

    # -- nudge helpers --------------------------------------------------------

    def _count_pending(self, grade: str) -> tuple[int, str | None]:
        """Count insights of `grade` since last higher-grade synthesis.

        Returns (count, last_higher_timestamp_or_None).
        """
        higher = {"finding": "pattern", "pattern": "principle"}
        higher_grade = higher.get(grade)
        if not higher_grade:
            return 0, None
        if not self._has_local_db():
            return 0, None
        row = self.local_conn.execute(
            "SELECT MAX(created_at) FROM insights WHERE grade = ? AND status = 'active'",
            (higher_grade,),
        ).fetchone()
        last_higher = row[0] if row and row[0] else None
        count = self.local_conn.execute(
            "SELECT COUNT(*) FROM insights WHERE grade = ? AND status = 'active'"
            " AND created_at > COALESCE(?, '1970-01-01')",
            (grade, last_higher),
        ).fetchone()[0]
        return count, last_higher

    def _pending_compounds(self, grade: str) -> str:
        """Extract unique tags from pending insights of a given grade.

        Returns a comma-separated string of tag values, or "multiple compounds"
        if no tags are found.
        """
        higher = {"finding": "pattern", "pattern": "principle"}
        higher_grade = higher.get(grade)
        if not higher_grade or not self._has_local_db():
            return "multiple compounds"
        row = self.local_conn.execute(
            "SELECT MAX(created_at) FROM insights WHERE grade = ? AND status = 'active'",
            (higher_grade,),
        ).fetchone()
        last_higher = row[0] if row and row[0] else None
        rows = self.local_conn.execute(
            "SELECT tags FROM insights WHERE grade = ? AND status = 'active'"
            " AND created_at > COALESCE(?, '1970-01-01')",
            (grade, last_higher),
        ).fetchall()
        compounds: set[str] = set()
        for r in rows:
            tags_json = r[0]
            if tags_json:
                try:
                    tags = json.loads(tags_json)
                    compounds.update(
                        t.strip() for t in tags if isinstance(t, str) and t.strip()
                    )
                except (json.JSONDecodeError, TypeError):
                    pass
        return ", ".join(sorted(compounds)) if compounds else "multiple compounds"

    def _maybe_nudge(self, tone: str = "strong") -> list[str]:
        """Return synthesis nudge messages if thresholds are met.

        Both L3→L4 (finding→pattern) and L4→L5 (pattern→principle) can fire
        simultaneously. L5 nudge listed first (higher priority).

        Args:
            tone: "soft" for search context, "strong" for record response.
        """
        p = float(os.environ.get("QMS_NUDGE_PROBABILITY", "1.0"))
        if random.random() >= p:
            return []

        nudges: list[str] = []
        # L4→L5: patterns → principles
        pending_patterns, _ = self._count_pending("pattern")
        if pending_patterns >= 3:
            if tone == "soft":
                nudges.append(
                    f"\u2139\ufe0f {pending_patterns} patterns pending synthesis. "
                    "Consider reviewing with list_insights(grade='pattern') "
                    "when your current task is complete."
                )
            else:
                nudges.append(
                    f"\U0001f4ca Principle synthesis checkpoint: you have {pending_patterns} patterns "
                    "pending. Consider whether a common physical or chemical mechanism unifies "
                    "them, or whether they suggest a general guideline for computational practice. "
                    "Use list_insights(grade='pattern') to review, then "
                    "record_insight(grade='principle', references=[...]). It's okay to skip "
                    "if no unifying mechanism is apparent yet."
                )
        # L3→L4: findings → patterns
        pending_findings, _ = self._count_pending("finding")
        if pending_findings >= 8:
            if tone == "soft":
                nudges.append(
                    f"\u2139\ufe0f {pending_findings} findings pending synthesis. "
                    "Consider reviewing with list_insights(grade='finding') "
                    "when your current task is complete."
                )
            else:
                compounds_str = self._pending_compounds("finding")
                nudges.append(
                    f"\U0001f4ca Knowledge synthesis checkpoint: {pending_findings} new findings "
                    f"since last pattern synthesis, covering {compounds_str}. "
                    "Look for systematic trends \u2014 how do computed properties vary across "
                    "related compounds? What physical or chemical factors might explain "
                    "the variation? Use list_insights(grade='finding') to review, then "
                    "record_insight(grade='pattern', references=[...]). It's okay to skip "
                    "if no clear trend is apparent yet."
                )
        return nudges

    def list_pending(self, grade: str, limit: int = 20, compound: str = "") -> dict:
        """List insights of `grade` since last higher-grade synthesis."""
        if not self._has_local_db():
            return {"grade": grade, "total_pending": 0, "since": None, "insights": []}
        higher = {"finding": "pattern", "pattern": "principle"}
        higher_grade = higher.get(grade)
        # Get timestamp of last higher-grade synthesis
        last_higher = None
        if higher_grade:
            row = self.local_conn.execute(
                "SELECT MAX(created_at) FROM insights WHERE grade = ? AND status = 'active'",
                (higher_grade,),
            ).fetchone()
            last_higher = row[0] if row and row[0] else None
        sql = "SELECT * FROM insights WHERE grade = ? AND status = 'active'"
        params: list = [grade]
        if last_higher:
            sql += " AND created_at > ?"
            params.append(last_higher)
        if compound:
            sql += " AND tags LIKE ?"
            params.append(f"%{compound}%")
        count_sql = sql.replace("SELECT *", "SELECT COUNT(*)")
        total = self.local_conn.execute(count_sql, params).fetchone()[0]
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 100)))
        rows = self.local_conn.execute(sql, params).fetchall()
        return {"grade": grade, "total_pending": total, "since": last_higher, "insights": [dict(r) for r in rows]}

    # -- internal helpers -----------------------------------------------------

    def _detect_contradictions(
        self,
        new_id: str,
        scope_engine: str,
        scope_workflow: str,
        scope_system_type: str,
        scope_method: str,
    ) -> list[dict]:
        """Check both DBs for contradiction candidates and increment counts.

        Only scope fields where BOTH the new entry AND the existing entry are
        non-wildcard participate in matching.
        """
        new_scopes = {
            "scope_engine": scope_engine,
            "scope_workflow": scope_workflow,
            "scope_system_type": scope_system_type,
            "scope_method": scope_method,
        }

        # Only non-wildcard fields from the new entry participate.
        non_wildcard = {k: v for k, v in new_scopes.items() if v != "*"}
        if not non_wildcard:
            return []  # All wildcards — nothing to contradict

        contradictions: list[dict] = []

        for db_conn, db_name in self._active_dbs():
            # Build query: find active entries where the matching scope fields
            # are also non-wildcard AND equal to the new entry's values.
            where_parts = ["status = 'active'", "id != ?"]
            params: list = [new_id]

            for field, value in non_wildcard.items():
                where_parts.append(f"({field} = ? AND {field} != '*')")
                params.append(value)

            sql = f"SELECT id, contradiction_count, content FROM insights WHERE {' AND '.join(where_parts)}"
            rows = db_conn.execute(sql, params).fetchall()

            for row in rows:
                entry_id = row[0]
                old_count = row[1]
                new_count = old_count + 1

                update_sql = "UPDATE insights SET contradiction_count = ?"
                update_params: list = [new_count]

                if new_count >= _CONTRADICTION_THRESHOLD:
                    update_sql += ", status = 'under_review'"

                update_sql += " WHERE id = ?"
                update_params.append(entry_id)

                db_conn.execute(update_sql, update_params)
                db_conn.commit()

                contradictions.append({
                    "id": entry_id,
                    "db": db_name,
                    "new_contradiction_count": new_count,
                    "flagged_for_review": new_count >= _CONTRADICTION_THRESHOLD,
                    "content_preview": row[2][:100] if row[2] else "",
                })

        return contradictions

    def _active_dbs(self) -> list[tuple[sqlite3.Connection, str]]:
        """Return list of (conn, name) for all active databases."""
        dbs = [(self.conn, "builtin")]
        if self._has_local_db():
            dbs.append((self.local_conn, "local"))
        return dbs

    def _fts_search(
        self,
        query_text: str,
        *,
        conn: sqlite3.Connection,
        engine: str,
        workflow: str,
        system_type: str,
        method: str,
        grade_min: str,
        confidence_min: str,
        limit: int,
    ) -> list[dict]:
        """FTS5-based search with scope filters on a single connection."""
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

        rows = conn.execute(sql, params).fetchall()
        results = [dict(r) for r in rows]

        # Attach raw rank for trust-weight re-ranking
        for r in results:
            r["_raw_rank"] = abs(r.get("rank", 0))

        return results

    def _scope_search(
        self,
        *,
        conn: sqlite3.Connection,
        engine: str,
        workflow: str,
        system_type: str,
        method: str,
        grade_min: str,
        confidence_min: str,
        limit: int,
    ) -> list[dict]:
        """Non-FTS search using only scope filters on a single connection."""
        sql = "SELECT i.* FROM insights i WHERE i.status = 'active'"
        params: list = []

        sql, params = self._add_scope_filters(
            sql, params, engine, workflow, system_type, method,
            grade_min, confidence_min,
        )

        sql += " ORDER BY i.grade DESC, i.confidence DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _apply_trust_ranking(results: list[dict]) -> None:
        """Re-rank FTS results using trust-weighted scoring, in-place."""
        for r in results:
            cw = _CONFIDENCE_WEIGHT.get(r.get("confidence", "medium"), 2.0)
            raw_rank = r.pop("_raw_rank", abs(r.get("rank", 0)))
            tw = TRUST_WEIGHTS.get(r.get("source_type", "local"), _DEFAULT_TRUST)
            r["_score"] = cw * raw_rank * tw

        results.sort(
            key=lambda r: (r["_score"], _GRADE_ORDER.get(r.get("grade", ""), 0)),
            reverse=True,
        )

        # Clean up internal keys
        for r in results:
            r.pop("_score", None)
            r.pop("rank", None)
            r.pop("_raw_rank", None)

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
        # workflow is intentionally NOT used as a hard filter.
        # Insights are general knowledge — a bands session should find relax
        # insights about the same compound.  BM25 ranking handles relevance.
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
