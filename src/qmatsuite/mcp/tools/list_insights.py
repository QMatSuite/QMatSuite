"""list_insights tool — list recorded insights by grade for synthesis review."""

from __future__ import annotations

import json

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_response, make_error


@mcp.tool
def list_insights(
    grade: str,
    limit: int = 20,
    compound: str = "",
    mode: str = "pending",
    status: str = "",
) -> dict:
    """List insights by grade for review or synthesis.

    Default mode 'pending': shows findings not yet synthesized into a
    higher-grade insight. Use when responding to a synthesis nudge.

    Mode 'recent': shows most recent entries regardless of synthesis
    status. Use to review the bigger picture or revisit older knowledge.

    Args:
        grade: Required. One of 'finding', 'pattern', 'principle'.
        limit: Max results (default 20, max 100).
        compound: Optional compound filter (matches tags).
        mode: 'pending' (default) or 'recent'.
        status: Optional comma-separated status filter (e.g. 'under_review'
            or 'confirmed,under_review'). If empty, returns all non-deprecated.
    """
    allowed = {"finding", "pattern", "principle"}
    if grade not in allowed:
        return make_error(
            error_type="VALIDATION_ERROR",
            message=f"Invalid grade {grade!r}; must be one of {sorted(allowed)}.",
            context_hint="Use grade='finding' to review findings before synthesis.",
        )

    if mode not in ("pending", "recent"):
        return make_error(
            error_type="VALIDATION_ERROR",
            message=f"Invalid mode {mode!r}. Must be 'pending' or 'recent'.",
            context_hint="Use mode='pending' for unsynthesized insights, or mode='recent' for all.",
        )

    # Parse status filter
    statuses = None
    if status and status.strip():
        statuses = [s.strip() for s in status.split(",") if s.strip()]

    from qmatsuite.mcp.knowledge import get_knowledge_store

    store = get_knowledge_store()

    if mode == "recent":
        data = store.list_by_grade(grade, limit=limit, compound=compound, statuses=statuses)
        # Enrich with parsed metadata
        items = []
        for r in data["insights"]:
            meta = json.loads(r["metadata"]) if r.get("metadata") else {}
            item = {
                "id": r["id"],
                "grade": r["grade"],
                "content": r["content"],
                "tags": json.loads(r["tags"]) if r.get("tags") else [],
                "created_at": r["created_at"],
                "status": r.get("status", "confirmed"),
                "contradiction_count": r.get("contradiction_count", 0),
                "upvotes": r.get("upvotes", 0),
                "downvotes": r.get("downvotes", 0),
                "metadata": meta,
                "source_calculation": meta.get("source_calculation"),
            }
            items.append(item)

        hint = f"Found {data['total']} {grade}(s)."
        if grade == "finding":
            hint += " Synthesize recurring themes into a pattern with record_insight(grade='pattern', references=[...])."
        elif grade == "pattern":
            hint += " Synthesize patterns into a principle with record_insight(grade='principle', references=[...])."

        return make_response(
            {
                "grade": grade,
                "mode": mode,
                "total": data["total"],
                "insights": items,
            },
            context_hint=hint,
        )
    else:
        # pending mode (default)
        data = store.list_pending(grade, limit=limit, compound=compound, statuses=statuses)
        items = []
        for r in data["insights"]:
            meta = json.loads(r["metadata"]) if r.get("metadata") else {}
            item = {
                "id": r["id"],
                "grade": r["grade"],
                "content": r["content"],
                "tags": json.loads(r["tags"]) if r.get("tags") else [],
                "created_at": r["created_at"],
                "status": r.get("status", "confirmed"),
                "contradiction_count": r.get("contradiction_count", 0),
                "upvotes": r.get("upvotes", 0),
                "downvotes": r.get("downvotes", 0),
                "metadata": meta,
                "source_calculation": meta.get("source_calculation"),
            }
            items.append(item)

        # R6: pending count header
        total_pending = data["total_pending"]
        since = data.get("since")
        higher_name = {"finding": "pattern", "pattern": "principle"}.get(grade, "higher-grade")
        if since:
            hint = (
                f"Showing {len(items)} of {total_pending} pending {grade}(s) "
                f"(since last {higher_name} synthesis at {since})"
            )
        else:
            hint = (
                f"Showing {len(items)} of {total_pending} {grade}(s) "
                f"(no {higher_name} synthesis yet)"
            )

        if grade == "finding":
            hint += " Synthesize recurring themes into a pattern with record_insight(grade='pattern', references=[...])."
        elif grade == "pattern":
            hint += " Synthesize patterns into a principle with record_insight(grade='principle', references=[...])."

        return make_response(
            {
                "grade": grade,
                "mode": mode,
                "total_pending": total_pending,
                "since": since,
                "insights": items,
            },
            context_hint=hint,
        )
