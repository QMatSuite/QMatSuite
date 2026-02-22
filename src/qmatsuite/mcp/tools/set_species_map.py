"""set_species_map tool — set pseudopotential mapping for a calculation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


def _pseudo_file_exists(svc: Any, pseudo_name: str) -> bool:
    """Best-effort check if a pseudo file exists in project/internal/store dirs."""
    # 1. Project pseudo/ dir
    project_pseudo = Path(svc.project_root) / "pseudo" / pseudo_name
    if project_pseudo.is_file():
        return True

    # 2. Internal resources
    try:
        import importlib.resources as pkg_resources

        ref = pkg_resources.files("qmatsuite") / "resources" / "pseudo" / pseudo_name
        # Check if the resource exists
        if ref.is_file():
            return True
    except Exception:
        pass

    # 3. SSSP store (if configured)
    try:
        from qmatsuite.core.pseudo_config import load_pseudo_config

        config = load_pseudo_config()
        if config.store_dir:
            # Walk store subdirectories
            store = Path(config.store_dir)
            if store.is_dir():
                for subdir in store.iterdir():
                    if subdir.is_dir():
                        candidate = subdir / pseudo_name
                        if candidate.is_file():
                            return True
    except Exception:
        pass

    return False


@mcp.tool
def set_species_map(
    calc_ulid: str,
    species_map: dict,
) -> dict:
    """Set the species-to-pseudopotential mapping for a calculation.

    Required before running QE, ABINIT, Siesta, or VASP calculations.

    Example species_map::

        {"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}}

    Args:
        calc_ulid: Calculation ULID returned by create_calculation.
        species_map: Mapping of element symbol to pseudopotential config.
            Each entry MUST have at least a ``pseudopot`` key.
    """
    # --- validate species_map ---
    if not species_map:
        return make_error(
            "invalid_species_map",
            "species_map must be a non-empty dict.",
            context_hint="Provide a mapping like {\"Si\": {\"pseudopot\": \"Si.UPF\"}}.",
        )

    for element, cfg in species_map.items():
        if not isinstance(cfg, dict) or "pseudopot" not in cfg:
            return make_error(
                "invalid_species_map",
                f"Entry for '{element}' must be a dict with a 'pseudopot' key. Got: {cfg}",
                context_hint="Each species entry needs at least {\"pseudopot\": \"filename\"}.",
            )

    # --- get service ---
    from qmatsuite.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- update species_map ---
    try:
        result = svc.calculation.update_species_map(calc_ulid, species_map)
    except Exception as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            return make_error(
                "calc_not_found",
                f"Calculation '{calc_ulid}' not found: {msg}",
            )
        return make_error("update_failed", f"Failed to set species_map: {msg}")

    old_map = result.get("old_species_map", {}) if isinstance(result, dict) else {}

    # Best-effort file existence check
    warnings: list[str] = []
    try:
        for elem, cfg in species_map.items():
            pseudo_name = cfg.get("pseudopot", "")
            if pseudo_name and not _pseudo_file_exists(svc, pseudo_name):
                warnings.append(
                    f"'{pseudo_name}' for {elem}: not found in project/internal/store. "
                    "It may need to be downloaded or placed in the project pseudo/ dir."
                )
    except Exception:
        pass  # Best-effort: never block the tool

    payload: dict = {
        "calc_ulid": calc_ulid,
        "species_map": species_map,
        "old_species_map": old_map,
    }
    if warnings:
        payload["warnings"] = warnings

    return make_response(
        payload,
        context_hint=(
            f"Species map set. Use inspect_calculation(calc_ulid='{calc_ulid}') "
            "to review, then run_calculation() or apply_preset() to continue."
        ),
        warnings=warnings if warnings else None,
    )
