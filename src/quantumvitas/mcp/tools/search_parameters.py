"""search_parameters tool — BM25 search across engine parameter tags."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_response


@mcp.tool
def search_parameters(
    query: str,
    engine: str = "",
    category: str = "",
    max_results: int = 5,
) -> dict:
    """Search for parameters/tags across all engines using free-text query.

    Uses BM25 ranking over ~1000 parameter documents from 11 engines.
    Optionally filter by engine or category.

    Args:
        query: Free-text search query (e.g. 'energy cutoff', 'smearing',
            'convergence threshold').
        engine: Optional engine filter (e.g. 'vasp', 'qe').
        category: Optional category filter (e.g. 'electronic', 'ionic').
        max_results: Maximum number of results to return (default 5, max 20).
    """
    from quantumvitas.mcp.search_index import get_search_index

    max_results = max(1, min(max_results, 20))
    index = get_search_index()
    hits = index.search(query, engine=engine, category=category, max_results=max_results)

    results_out: list[dict] = []
    for doc, score in hits:
        entry: dict = {
            "engine": doc.engine,
            "tag_name": doc.tag_name,
            "type": doc.type,
            "default": doc.default,
            "category": doc.category,
            "description": doc.description[:200] if doc.description else "",
            "relevance_score": round(score, 3),
        }
        if doc.section:
            entry["section"] = doc.section
        results_out.append(entry)

    return make_response(
        {
            "query": query,
            "engine_filter": engine or None,
            "category_filter": category or None,
            "results": results_out,
            "total_results": len(results_out),
        },
        context_hint=(
            "Use these parameters with set_parameters(calc_ulid, params=...) to configure a calculation. "
            "For QE, nest parameters under their namelist section "
            "(e.g. {\"ELECTRONS\": {\"diago_full_acc\": true}}). "
            "The 'section' field indicates the correct nesting for engines that require it. "
            "For ORCA, 'keyword_line' means the ! line, 'block:scf' means the %scf block."
        ),
    )
