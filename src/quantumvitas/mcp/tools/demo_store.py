"""Demo store tools — browse, preview, and load demo calculations."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


def _build_engine_map() -> dict[str, str]:
    """Build a mapping from demo_id to engine family by reading YAML meta."""
    import yaml
    from quantumvitas.core.resources import get_resources_dir

    demo_dir = get_resources_dir() / "demo_projects"
    if not demo_dir.exists():
        return {}

    result: dict[str, str] = {}
    for path in demo_dir.glob("*.yml"):
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            meta = data.get("meta", {})
            engine = meta.get("required_engine", "")
            if not engine:
                # Fallback: read from first calculation's engine_family
                calcs = data.get("calculations", [])
                if calcs:
                    engine = calcs[0].get("engine_family", "")
            result[path.stem] = engine.lower()
        except Exception:
            continue
    return result


@mcp.tool
def search_demos(
    engine: str = "",
    tag: str = "",
    difficulty: str = "",
    query: str = "",
) -> dict:
    """Search the catalog of pre-built demo calculations.

    Returns demos matching the given filters. All filters are optional and
    combined with AND logic. With no filters, returns the full catalog.

    Args:
        engine: Filter by engine family (e.g. 'qe', 'vasp', 'orca').
        tag: Filter by tag (e.g. 'bands', 'scf', 'tutorial').
        difficulty: Filter by difficulty level ('beginner', 'intermediate', 'advanced').
        query: Free-text search across title and description.
    """
    from quantumvitas.api import QVService
    from quantumvitas.demo_store.ref_packs import list_all_ref_packs, list_ref_pack_types

    try:
        demos = QVService.list_demo_projects()
    except Exception as exc:
        return make_error("catalog_error", f"Failed to load demo catalog: {exc}")

    # Build engine lookup from YAML meta.required_engine
    engine_map = _build_engine_map()

    # Enrichment: ref pack info
    ref_pack_slugs = set(list_all_ref_packs())

    # Filter
    query_lower = query.lower()
    filtered = []
    for d in demos:
        demo_id = d.get("ulid", "")
        if engine:
            demo_engine = engine_map.get(demo_id, "")
            if demo_engine != engine.lower():
                continue
        if tag:
            demo_tags = [t.lower() for t in d.get("tags", [])]
            if tag.lower() not in demo_tags:
                continue
        if difficulty:
            if (d.get("difficulty") or "").lower() != difficulty.lower():
                continue
        if query_lower:
            title = (d.get("title") or "").lower()
            desc = (d.get("description") or "").lower()
            name = (d.get("name") or "").lower()
            if query_lower not in title and query_lower not in desc and query_lower not in name:
                continue

        d["engine"] = engine_map.get(demo_id, "")
        has_ref = demo_id in ref_pack_slugs
        d["has_ref_pack"] = has_ref
        d["ref_pack_types"] = list_ref_pack_types(demo_id) if has_ref else []
        filtered.append(d)

    if filtered:
        hint = (
            "Use get_demo_results(demo_id=...) to preview pre-computed results, "
            "or load_demo(demo_id=...) to load a demo into your project."
        )
    else:
        hint = (
            "No demos matched. Try broader filters, or use "
            "create_calculation(...) to start from scratch."
        )
    return make_response(
        {"demos": filtered, "total": len(filtered)},
        context_hint=hint,
    )


@mcp.tool
def get_demo_results(demo_id: str, object_type: str = "") -> dict:
    """Preview pre-computed results for a demo calculation.

    Without object_type, lists available result types and manifest metadata.
    With object_type, returns the full pre-computed analysis data.

    Args:
        demo_id: Demo identifier (e.g. 'qe_si_scf', 'vasp_si_relax').
        object_type: Analysis type to load (e.g. 'bands', 'dos', 'convergence').
                     Empty string lists available types.
    """
    from quantumvitas.demo_store.ref_packs import (
        list_ref_pack_types,
        load_ref_pack,
        load_ref_pack_manifest,
    )

    if not object_type:
        # List available types + manifest
        types = list_ref_pack_types(demo_id)
        manifest = load_ref_pack_manifest(demo_id)
        if manifest is None:
            return make_error(
                "no_ref_pack",
                f"No pre-computed results available for demo '{demo_id}'.",
                suggestions=["Use search_demos() to find demos with ref packs."],
            )
        return make_response(
            {
                "demo_id": demo_id,
                "available_types": types,
                "manifest": manifest,
            },
            context_hint=(
                f"Use get_demo_results(demo_id='{demo_id}', object_type=...) "
                "to load a specific result type."
            ),
        )

    # Load specific result
    data = load_ref_pack(demo_id, object_type)
    if data is None:
        available = list_ref_pack_types(demo_id)
        if not available:
            return make_error(
                "no_ref_pack",
                f"No pre-computed results available for demo '{demo_id}'.",
            )
        return make_error(
            "type_not_found",
            f"Result type '{object_type}' not available for demo '{demo_id}'.",
            suggestions=available,
        )

    return make_response(
        {"demo_id": demo_id, "object_type": object_type, "data": data},
    )


@mcp.tool
def load_demo(demo_id: str, name: str = "") -> dict:
    """Load a demo calculation into the current project.

    Imports the demo's structure and creates a calculation with the demo's
    engine, workflow steps, and parameters. Works within the current project
    — no project context switching.

    Args:
        demo_id: Demo identifier (e.g. 'qe_si_scf', 'vasp_si_relax').
        name: Optional name for the calculation (defaults to demo title).
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    try:
        import quantumvitas.drivers  # noqa: F401 — trigger registration
        result = svc.load_demo_as_calculation(demo_id, name=name or None)
    except FileNotFoundError as exc:
        return make_error("demo_not_found", str(exc))
    except ValueError as exc:
        return make_error("invalid_demo", str(exc))
    except Exception as exc:
        return make_error("load_failed", f"Failed to load demo: {exc}")

    calc_ulid = result["calc_ulid"]
    return make_response(
        result,
        context_hint=(
            f"Demo loaded. Use inspect_calculation(calc_ulid='{calc_ulid}') "
            f"to review, or run_calculation(calc_ulid='{calc_ulid}') to execute."
        ),
    )
