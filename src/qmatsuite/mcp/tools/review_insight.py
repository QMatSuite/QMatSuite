"""review_insight tool — review, confirm, or deprecate knowledge entries."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_response, make_error

_VALID_VERDICTS = {"confirmed", "deprecated"}


@mcp.tool
def review_insight(
    insight_id: str,
    verdict: str,
    reasoning: str,
    superseded_by: str = "",
) -> dict:
    """Review an insight: confirm it as validated or deprecate it.

    The sole mechanism for explicit status changes. Used during knowledge
    review sessions to audit agent-recorded findings.

    Args:
        insight_id: Full ULID of the insight to review (must be in local.db).
        verdict: 'confirmed' (validated) or 'deprecated' (rejected/outdated).
        reasoning: Required. Why this verdict was given.
        superseded_by: Optional ULID of a replacement insight. When given
            with verdict='deprecated', the old insight is deprecated and the
            replacement is auto-confirmed.
    """
    # --- Validation (all checks before any writes) ---

    if verdict not in _VALID_VERDICTS:
        return make_error(
            error_type="VALIDATION_ERROR",
            message=f"Invalid verdict {verdict!r}; must be one of {sorted(_VALID_VERDICTS)}.",
            context_hint="Use verdict='confirmed' to validate or verdict='deprecated' to reject.",
        )

    if not reasoning or not reasoning.strip():
        return make_error(
            error_type="VALIDATION_ERROR",
            message="Reasoning must be non-empty.",
            context_hint="Explain why this verdict is appropriate.",
        )

    from qmatsuite.mcp.knowledge import get_knowledge_store

    store = get_knowledge_store()

    # Resolve short ID prefix to full ULID
    try:
        insight_id = store.resolve_short_id(insight_id)
    except ValueError:
        pass  # keep original, will fail on lookup below

    # Check existence in local.db
    if not store._has_local_db():
        return make_error(
            error_type="NOT_FOUND",
            message=f"Insight {insight_id} not found (no local.db).",
            context_hint="Only agent-recorded insights in local.db can be reviewed.",
        )

    local_row = store.local_conn.execute(
        "SELECT id FROM insights WHERE id = ?", (insight_id,)
    ).fetchone()
    if local_row is None:
        # Check if it's a builtin entry
        builtin_row = store.conn.execute(
            "SELECT id FROM insights WHERE id = ?", (insight_id,)
        ).fetchone()
        if builtin_row is not None:
            return make_error(
                error_type="VALIDATION_ERROR",
                message="Cannot review curated knowledge (builtin.db).",
                context_hint="Only agent-recorded insights in local.db can be reviewed.",
            )
        return make_error(
            error_type="NOT_FOUND",
            message=f"Insight {insight_id} not found.",
            context_hint="Use list_insights() to find valid insight IDs.",
        )

    # Resolve superseded_by short ID if given
    if superseded_by:
        try:
            superseded_by = store.resolve_short_id(superseded_by)
        except ValueError:
            pass  # keep original, update_status will validate

        # Validate superseded_by exists in local.db before any writes
        sup_row = store.local_conn.execute(
            "SELECT id FROM insights WHERE id = ?", (superseded_by,)
        ).fetchone()
        if sup_row is None:
            return make_error(
                error_type="NOT_FOUND",
                message=f"Superseding insight {superseded_by} not found in local.db.",
                context_hint="Record the replacement insight first, then deprecate the old one.",
            )

    # --- Execute ---
    try:
        result = store.update_status(
            insight_id=insight_id,
            verdict=verdict,
            reasoning=reasoning,
            superseded_by=superseded_by,
        )
    except ValueError as exc:
        return make_error(
            error_type="VALIDATION_ERROR",
            message=str(exc),
            context_hint="Use list_insights(status='under_review') to see reviewable insights.",
        )

    hint = "Use list_insights(status='under_review') to see remaining unreviewed insights."
    if verdict == "deprecated" and superseded_by:
        hint = (
            f"Deprecated {insight_id[:10]}... and confirmed replacement "
            f"{superseded_by[:10]}... . " + hint
        )

    return make_response(result, context_hint=hint)
