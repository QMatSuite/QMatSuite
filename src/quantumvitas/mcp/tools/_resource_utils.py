"""Internal resource helpers shared by MCP tools.

Not an MCP tool itself — provides auto_resolve_species_map_internal()
and check_resource_status() for use by quick_run, create_calculation,
run_calculation, inspect_calculation, list_resources, and
resolve_species_map tools.
"""

from __future__ import annotations

from typing import Any

# Engines that require pseudopotentials / species_map.
PSEUDO_ENGINES = ("qe", "abinit", "siesta")


def auto_resolve_species_map_internal(
    calc_ulid: str,
    svc: Any,
    library: str = "sssp",
    flavor: str = "precision",
) -> dict | None:
    """Resolve species_map for a calculation.  Returns dict or None.

    The returned dict maps element -> {"pseudopot": filename}.
    Returns None when the engine doesn't use pseudopotentials, the
    calculation has no structure/elements, or resolution fails.
    """
    # 1. Get calc detail
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception:
        return None

    engine = detail.get("engine_family", "")
    if engine not in PSEUDO_ENGINES:
        return None

    elements = detail.get("structure_elements", [])
    if not elements:
        return None

    # 2. Resolve pseudopotentials via core APIs
    try:
        from quantumvitas.core.pseudo_config import (
            PseudoResolutionRequest,
            load_pseudo_config,
            resolve_project_pseudos,
        )

        config = load_pseudo_config()
        request = PseudoResolutionRequest(
            project_root=svc.project_root,
            elements=list(elements),
            library=library,
            flavor=flavor,
        )
        result = resolve_project_pseudos(config, request)

        if result.success and result.mapping:
            species_map = {
                elem: {"pseudopot": filename}
                for elem, filename in result.mapping.items()
            }
            return species_map
    except Exception:
        pass

    return None


def check_resource_status(calc_ulid: str, svc: Any) -> dict:
    """Check resource readiness for a calculation.

    Returns a status dict with:
      - species_map_set: bool
      - all_pseudos_resolved: bool
      - missing_elements: list[str]
      - suggestion: str
    """
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception:
        return {
            "species_map_set": False,
            "all_pseudos_resolved": False,
            "missing_elements": [],
            "suggestion": "Could not load calculation detail.",
        }

    engine = detail.get("engine_family", "")
    if engine not in PSEUDO_ENGINES:
        return {
            "species_map_set": True,
            "all_pseudos_resolved": True,
            "missing_elements": [],
            "suggestion": f"Engine '{engine}' does not require pseudopotentials.",
        }

    species_map = detail.get("species_map") or {}
    elements = detail.get("structure_elements", [])

    species_map_set = bool(species_map)
    mapped_elements = set(species_map.keys())
    missing = [e for e in elements if e not in mapped_elements]
    all_resolved = species_map_set and len(missing) == 0

    if all_resolved:
        suggestion = "All pseudopotentials resolved. Ready to run."
    elif not species_map_set:
        suggestion = (
            f"Call auto_resolve_species_map(calc_ulid='{calc_ulid}') to auto-resolve, "
            f"or set_species_map(calc_ulid='{calc_ulid}', ...) manually."
        )
    else:
        suggestion = (
            f"Missing pseudopotentials for: {', '.join(missing)}. "
            f"Update species_map to include all elements."
        )

    return {
        "species_map_set": species_map_set,
        "all_pseudos_resolved": all_resolved,
        "missing_elements": missing,
        "suggestion": suggestion,
    }
