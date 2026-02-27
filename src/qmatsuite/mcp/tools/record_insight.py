"""record_insight tool — record agent-authored insights into the knowledge base."""

from __future__ import annotations

import json

import ulid

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_response, make_error

_VALID_GRADES = {"bookkeeping", "observation", "finding", "principle"}


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
def record_insight(
    content: str,
    grade: str = "observation",
    reasoning: str = "",
    scope_engine: str = "*",
    scope_workflow: str = "*",
    scope_system_type: str = "*",
    scope_method: str = "*",
    tags: str = "",
    calc_ulid: str = "",
) -> dict:
    """Record an agent-authored insight into the QMatSuite knowledge base.

    All grades are recorded in the provenance journal. Findings and principles
    are additionally promoted into the searchable knowledge database.

    Args:
        content: Distilled conclusion (short, enters knowledge base if promoted).
        grade: Quality tier — bookkeeping, observation, finding, or principle.
        reasoning: Detailed thought process (provenance only, not indexed).
        scope_engine: Engine scope (e.g. 'qe', 'vasp') or '*' for all.
        scope_workflow: Workflow scope (e.g. 'scf', 'relax') or '*' for all.
        scope_system_type: System type scope (e.g. 'metal') or '*' for all.
        scope_method: Method scope (e.g. 'dft+u', 'hse') or '*' for all.
        tags: Comma-separated or JSON array of tags for FTS indexing.
        calc_ulid: Optional link to a source calculation ULID.
    """
    # Validate inputs
    if not content or not content.strip():
        return make_error(
            error_type="VALIDATION_ERROR",
            message="Content must be non-empty.",
            context_hint="Provide a concise insight in the 'content' parameter.",
        )

    if grade not in _VALID_GRADES:
        return make_error(
            error_type="VALIDATION_ERROR",
            message=f"Invalid grade {grade!r}; must be one of {sorted(_VALID_GRADES)}.",
            context_hint="Use grade='observation' for preliminary insights, 'finding' for verified conclusions.",
        )

    parsed_tags = _parse_tags(tags)

    # Write to journal (ALL grades)
    journal_recorded = False
    journal_entry_ulid = None
    try:
        from qmatsuite.core.journal import get_journal, JournalEntry

        target = calc_ulid or str(ulid.new())
        entry = JournalEntry.create(
            target_ulid=target,
            doc_type="unknown",
            before={},
            after={
                "type": "insight",
                "content": content,
                "grade": grade,
                "reasoning": reasoning,
                "scope_engine": scope_engine,
                "scope_workflow": scope_workflow,
                "scope_system_type": scope_system_type,
                "scope_method": scope_method,
                "tags": parsed_tags,
            },
            summary=f"Agent insight: {content[:80]}",
        )
        get_journal().record_change(entry)
        journal_recorded = True
        journal_entry_ulid = entry.ulid
    except Exception:
        pass  # Journal failure is non-fatal

    # Grade >= finding: promote to knowledge DB
    promoted = False
    insight_id = None
    contradictions: list[dict] = []

    if grade in ("finding", "principle"):
        try:
            from qmatsuite.mcp.knowledge import get_knowledge_store
            from qmatsuite.mcp.knowledge.insight_record import InsightRecord

            record = InsightRecord(
                content=content,
                reasoning=reasoning,
                grade=grade,
                scope={
                    "engine": scope_engine,
                    "workflow": scope_workflow,
                    "system_type": scope_system_type,
                    "method": scope_method,
                },
                run_refs=[calc_ulid] if calc_ulid else [],
                tags=parsed_tags,
                created_by="agent",
            )

            store = get_knowledge_store()
            result = store.add(record)
            promoted = result["promoted"]
            insight_id = result.get("insight_id")
            contradictions = result.get("contradictions", [])
        except Exception:
            pass  # Knowledge store failure is non-fatal

    # Build context hint
    if promoted:
        hint = "Insight recorded in knowledge base. Use search_knowledge() to verify it's findable."
        if contradictions:
            flagged = [c for c in contradictions if c.get("flagged_for_review")]
            if flagged:
                hint += f" WARNING: {len(flagged)} existing entry(s) flagged for review due to contradictions."
            else:
                hint += f" Note: {len(contradictions)} potential contradiction(s) detected."
    elif grade in ("finding", "principle"):
        hint = "Insight recorded in journal but knowledge store write failed."
    else:
        hint = (
            "Observation recorded in journal. "
            "Record more observations, then consolidate into a finding with "
            "record_insight(grade='finding')."
        )

    return make_response(
        {
            "insight_id": insight_id,
            "journal_entry_ulid": journal_entry_ulid,
            "promoted": promoted,
            "journal_recorded": journal_recorded,
            "grade": grade,
            "contradictions": contradictions,
        },
        context_hint=hint,
    )
