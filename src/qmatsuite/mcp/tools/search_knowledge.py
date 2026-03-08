"""search_knowledge tool — FTS5 search over curated DFT knowledge."""

from __future__ import annotations

import json

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_response


@mcp.tool
def search_knowledge(
    query: str = "",
    engine: str = "",
    workflow: str = "",
    system_type: str = "",
    method: str = "",
    grade_min: str = "",
    confidence_min: str = "",
    limit: int = 15,
) -> dict:
    """Search the QMatSuite knowledge base for DFT best practices and error recovery.

    Uses BM25 full-text search over curated insights covering convergence,
    smearing, error recovery, workflow guidance, and method-specific tips.
    Searches both builtin and agent-recorded (local) knowledge.

    Args:
        query: Free-text search query (e.g. 'SCF not converging',
            'smearing metals', 'band structure workflow').
        engine: Optional engine filter (e.g. 'vasp', 'qe', 'abinit').
        workflow: Optional workflow filter (e.g. 'scf', 'relax', 'bands', 'dos').
        system_type: Optional system type filter (e.g. 'metal', 'semiconductor',
            'magnetic').
        method: Optional method filter (e.g. 'dft', 'dft+u', 'hse', 'gw').
        grade_min: Minimum grade filter ('bookkeeping', 'observation',
            'finding', 'principle').
        confidence_min: Minimum confidence filter ('low', 'medium', 'high').
        limit: Maximum number of results (default 15, max 80).
    """
    from qmatsuite.mcp.knowledge import get_knowledge_store

    store = get_knowledge_store()
    results = store.search(
        query,
        engine=engine,
        workflow=workflow,
        system_type=system_type,
        method=method,
        grade_min=grade_min,
        confidence_min=confidence_min,
        limit=limit,
    )

    # Truncate content in list view to 300 chars.
    items = []
    for r in results:
        meta = json.loads(r["metadata"]) if r.get("metadata") else {}
        item = {
            "id": r["id"],
            "grade": r["grade"],
            "scope_engine": r["scope_engine"],
            "scope_workflow": r["scope_workflow"],
            "scope_system_type": r["scope_system_type"],
            "scope_method": r["scope_method"],
            "content": r["content"][:300] + ("..." if len(r["content"]) > 300 else ""),
            "confidence": r["confidence"],
            "tags": json.loads(r["tags"]) if r.get("tags") else [],
            "source_type": r["source_type"],
            "status": r.get("status", "confirmed"),
            "upvotes": r.get("upvotes", 0),
            "downvotes": r.get("downvotes", 0),
            "contradiction_count": r.get("contradiction_count", 0),
            "metadata": meta,
            "source_calculation": meta.get("source_calculation"),
        }
        items.append(item)

    if items:
        hint = (
            f"Found {len(items)} insight(s). "
            "Use these insights to inform your parameter choices with set_parameters or apply_preset."
        )
    else:
        hint = "No matching knowledge found. Try broader search terms or remove filters."

    return make_response(
        {
            "query": query or "(all)",
            "filters": {
                "engine": engine or None,
                "workflow": workflow or None,
                "system_type": system_type or None,
                "method": method or None,
                "grade_min": grade_min or None,
                "confidence_min": confidence_min or None,
            },
            "results": items,
            "total_results": len(items),
        },
        context_hint=hint,
    )
