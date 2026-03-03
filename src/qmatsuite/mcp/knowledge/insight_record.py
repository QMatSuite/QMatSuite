"""InsightRecord — data model for agent-recorded insights.

This is the schema-only definition used by ``record_insight`` (Phase 3).
No write implementation here; the dataclass is used for validation and
structured handoff to the knowledge store.

Per AGENT_INTEGRATION_DESIGN.md Section 5.4:
- ``content`` is the distilled conclusion — short, enters knowledge base.
- ``reasoning`` is the detailed thought process — stays in provenance only.
- ``search_knowledge`` indexes ``content`` only, not ``reasoning``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InsightRecord:
    """A structured insight ready for recording into the knowledge store.

    Attributes:
        content: Distilled conclusion (enters knowledge base if grade >= finding).
        reasoning: Thought process / evidence chain (provenance only, not indexed).
        grade: Quality tier — bookkeeping | observation | finding | pattern | principle.
        scope: Scope dimensions, e.g. ``{"engine": "qe", "workflow": "scf"}``.
        run_refs: Associated calculation ULIDs that produced this insight.
        tags: Freeform tag list for FTS indexing.
        intent_id: Links back to the intent this insight addresses.
        created_by: Origin — "agent", "user", or "system".
    """

    content: str
    reasoning: str | None = None
    grade: str = "observation"
    scope: dict = field(default_factory=dict)
    run_refs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    intent_id: str | None = None
    created_by: str = "agent"
    source_calculation: str | None = None
    references: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
