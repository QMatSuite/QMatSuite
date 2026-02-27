"""record_intent tool — record agent intent in the provenance journal."""

from __future__ import annotations

import json

import ulid

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_response, make_error


def _parse_tags(tags_str: str) -> list[str]:
    """Parse comma-separated or JSON array tags string."""
    if not tags_str:
        return []
    tags_str = tags_str.strip()
    if tags_str.startswith("["):
        try:
            parsed = json.loads(tags_str)
            if isinstance(parsed, list):
                return [str(t).strip() for t in parsed if str(t).strip()]
        except json.JSONDecodeError:
            pass
    return [t.strip() for t in tags_str.split(",") if t.strip()]


@mcp.tool
def record_intent(
    intent: str,
    calc_ulid: str = "",
    tags: str = "",
) -> dict:
    """Record an agent's intent in the provenance journal.

    This is a lightweight journal-only write — no knowledge database interaction.
    Use this to declare what you plan to do before doing it, creating an audit
    trail of agent reasoning.

    Args:
        intent: Description of what the agent intends to do.
        calc_ulid: Optional link to a target calculation ULID.
        tags: Comma-separated or JSON array of tags.
    """
    if not intent or not intent.strip():
        return make_error(
            error_type="VALIDATION_ERROR",
            message="Intent must be non-empty.",
            context_hint="Describe what you plan to do in the 'intent' parameter.",
        )

    parsed_tags = _parse_tags(tags)

    intent_id = None
    try:
        from qmatsuite.core.journal import get_journal, JournalEntry

        target = calc_ulid or str(ulid.new())
        entry = JournalEntry.create(
            target_ulid=target,
            doc_type="unknown",
            before={},
            after={
                "type": "intent",
                "intent": intent,
                "tags": parsed_tags,
                "calc_ulid": calc_ulid,
            },
            summary=f"Agent intent: {intent[:80]}",
        )
        get_journal().record_change(entry)
        intent_id = entry.ulid
    except Exception:
        return make_error(
            error_type="JOURNAL_ERROR",
            message="Failed to write intent to journal.",
            context_hint="Check journal configuration.",
        )

    return make_response(
        {
            "intent_id": intent_id,
            "intent": intent[:200],
            "calc_ulid": calc_ulid or None,
            "tags": parsed_tags,
        },
        context_hint=f"Intent recorded. Proceed with the planned action.",
    )
