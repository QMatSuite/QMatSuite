"""search_knowledge tool — FTS5 search over curated DFT knowledge."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_response

# Module-level singleton (lazy-initialized).
_store = None


def _get_store():
    global _store
    if _store is None:
        from quantumvitas.mcp.knowledge.store import KnowledgeStore
        from quantumvitas.mcp.knowledge.build_builtin import build_builtin_db

        store = KnowledgeStore()
        if store.count() == 0:
            store.close()
            build_builtin_db()
            store = KnowledgeStore()
        _store = store
    return _store


@mcp.tool
def search_knowledge(
    query: str = "",
    engine: str = "",
    workflow: str = "",
    system_type: str = "",
    method: str = "",
    grade_min: str = "",
    confidence_min: str = "",
    limit: int = 10,
) -> dict:
    """Search the QMatSuite knowledge base for DFT best practices and error recovery.

    Uses BM25 full-text search over curated insights covering convergence,
    smearing, error recovery, workflow guidance, and method-specific tips.

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
        limit: Maximum number of results (default 10, max 50).
    """
    store = _get_store()
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
        item = {
            "id": r["id"],
            "grade": r["grade"],
            "scope_engine": r["scope_engine"],
            "scope_workflow": r["scope_workflow"],
            "scope_system_type": r["scope_system_type"],
            "scope_method": r["scope_method"],
            "content": r["content"][:300] + ("..." if len(r["content"]) > 300 else ""),
            "confidence": r["confidence"],
            "tags": r["tags"],
            "source_type": r["source_type"],
        }
        items.append(item)

    if items:
        hint = f"Found {len(items)} insight(s). Use get_by_id for full content."
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
