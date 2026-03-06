"""record_insight tool — record agent-authored insights into the knowledge base."""

from __future__ import annotations

import json

import ulid

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_response, make_error

_VALID_GRADES = {"bookkeeping", "observation", "finding", "pattern", "principle"}


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
    source_calculation: str = "",
    references: str = "",
    citations: str = "",
) -> dict:
    """Record an agent-authored insight into the QMatSuite knowledge base.

    All grades are recorded in the provenance journal. Findings, patterns, and
    principles are additionally promoted into the searchable knowledge database.

    Args:
        content: Distilled conclusion (short, enters knowledge base if promoted).
        grade: Quality tier — bookkeeping, observation, finding, pattern, or principle.
        reasoning: Detailed thought process (provenance only, not indexed).
        scope_engine: Engine scope (e.g. 'qe', 'vasp') or '*' for all.
        scope_workflow: Workflow scope (e.g. 'scf', 'relax') or '*' for all.
        scope_system_type: System type scope (e.g. 'metal') or '*' for all.
        scope_method: Method scope (e.g. 'dft+u', 'hse') or '*' for all.
        tags: Comma-separated or JSON array of tags for FTS indexing.
        calc_ulid: Optional link to a source calculation ULID.
        source_calculation: Optional ULID of the calculation that produced this insight.
        references: Comma-separated or JSON array of insight IDs this entry builds upon.
            Required for 'pattern' and 'principle' grades.
        citations: Optional. Comma-separated pairs of "ULID:up" or "ULID:down" indicating
            which prior insights influenced this one and whether they were helpful.
            Example: "01AAA:up,01BBB:down". Invalid entries are warned but not rejected.
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
    parsed_references = _parse_tags(references)  # reuse comma/JSON parser

    # Resolve short ID prefixes to full ULIDs
    if parsed_references:
        try:
            from qmatsuite.mcp.knowledge import get_knowledge_store

            _store = get_knowledge_store()
            resolved_refs = []
            for ref_id in parsed_references:
                try:
                    resolved_refs.append(_store.resolve_short_id(ref_id))
                except ValueError:
                    resolved_refs.append(ref_id)  # keep original, will warn later
            parsed_references = resolved_refs
        except Exception:
            pass  # non-fatal

    # Enforce: pattern and principle require at least one reference
    if grade in ("pattern", "principle") and not parsed_references:
        grade_to_review = {"pattern": "finding", "principle": "pattern"}[grade]
        return make_error(
            error_type="VALIDATION_ERROR",
            message=f"grade '{grade}' requires at least one reference ID",
            context_hint=(
                f"Use list_insights(grade='{grade_to_review}') to review {grade_to_review}s, "
                "then pass their IDs as references."
            ),
        )

    # Validate referenced IDs (warn-only if not found)
    ref_warnings: list[str] = []
    if parsed_references:
        try:
            from qmatsuite.mcp.knowledge import get_knowledge_store

            _store = get_knowledge_store()
            for ref_id in parsed_references:
                if not _store.get_by_id(ref_id):
                    ref_warnings.append(f"Referenced insight {ref_id} not found in DB")
        except Exception:
            pass  # non-fatal

    # Parse citations
    parsed_citations: list[dict] = []
    citation_warnings: list[str] = []
    if citations and citations.strip():
        for pair in citations.split(","):
            pair = pair.strip()
            if not pair:
                continue
            parts = pair.rsplit(":", 1)
            if len(parts) == 2 and parts[1] in ("up", "down"):
                cit_id = parts[0]
                try:
                    from qmatsuite.mcp.knowledge import get_knowledge_store

                    cit_id = get_knowledge_store().resolve_short_id(cit_id)
                except (ValueError, Exception):
                    pass  # keep original, non-fatal
                parsed_citations.append({"id": cit_id, "vote": parts[1]})
            else:
                citation_warnings.append(f"Invalid citation format: {pair!r} (expected 'ULID:up' or 'ULID:down')")

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
                "references": parsed_references,
                "source_calculation": source_calculation,
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
    citation_result: dict = {}

    if grade in ("finding", "pattern", "principle"):
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
                source_calculation=source_calculation or None,
                references=parsed_references,
                citations=parsed_citations,
            )

            store = get_knowledge_store()
            result = store.add(record)
            promoted = result["promoted"]
            insight_id = result.get("insight_id")
            contradictions = result.get("contradictions", [])

            # Apply citation votes to cited insights
            if parsed_citations:
                citation_result = store.apply_citations(parsed_citations)
        except Exception:
            pass  # Knowledge store failure is non-fatal

    # Apply citations even for non-promoted grades (citations are independent)
    citation_summary = ""
    if parsed_citations and not promoted:
        try:
            from qmatsuite.mcp.knowledge import get_knowledge_store

            citation_result = get_knowledge_store().apply_citations(parsed_citations)
        except Exception:
            pass
    if parsed_citations:
        applied_up = citation_result.get("applied_up", 0)
        applied_down = citation_result.get("applied_down", 0)
        skipped = citation_result.get("skipped", 0)
        parts = []
        if applied_up or applied_down:
            parts.append(f"{applied_up} helpful, {applied_down} not")
        if skipped:
            parts.append(f"{skipped} skipped (builtin or unknown)")
        citation_summary = f"Cited {len(parsed_citations)} insight(s)"
        if parts:
            citation_summary += f" ({', '.join(parts)})"

    # Build context hint
    if promoted:
        hint = (
            "Insight recorded. If this session produced additional findings "
            "(methodology lessons, error workarounds, parameter guidance), "
            "record each as a separate insight."
        )
        if contradictions:
            flagged = [c for c in contradictions if c.get("flagged_for_review")]
            if flagged:
                hint += f" WARNING: {len(flagged)} existing entry(s) flagged for review due to contradictions."
            else:
                hint += f" Note: {len(contradictions)} potential contradiction(s) detected."
    elif grade in ("finding", "pattern", "principle"):
        hint = "Insight recorded in journal but knowledge store write failed."
    else:
        hint = (
            "Observation recorded in journal. "
            "Record more observations, then consolidate into a finding with "
            "record_insight(grade='finding'). After several findings, synthesize "
            "a pattern with record_insight(grade='pattern', references=[...])."
        )

    all_warnings = ref_warnings + citation_warnings
    data = {
        "insight_id": insight_id if insight_id else None,
        "journal_entry_ulid": journal_entry_ulid,
        "promoted": promoted,
        "journal_recorded": journal_recorded,
        "grade": grade,
        "contradictions": contradictions,
    }
    if citation_summary:
        data["citation_summary"] = citation_summary

    return make_response(
        data,
        context_hint=hint,
        warnings=all_warnings if all_warnings else None,
    )
