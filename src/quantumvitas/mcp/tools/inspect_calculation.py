"""inspect_calculation tool — read back calculation state."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def inspect_calculation(calc_ulid: str, step: int = -1, dry_run: bool = False) -> dict:
    """Inspect a calculation's current configuration.

    With the default ``step=-1`` an overview of all steps is returned.
    Pass a zero-based step index to get the full parameter detail for that
    specific step.

    When ``dry_run=True`` (requires ``step >= 0``), materializes the input
    files to a temporary directory and returns their content, plus runs
    the engine's preflight checker if available.

    Args:
        calc_ulid: ULID of the target calculation.
        step: Step index to inspect in detail (-1 = overview only).
        dry_run: If True, materialize input files and return content.
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- overview ---
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception as exc:
        return make_error(
            "not_found",
            f"Calculation '{calc_ulid}' not found: {exc}",
        )

    steps_raw = detail.get("steps", [])

    # Build step summaries
    steps_out: list[dict] = []
    for idx, s in enumerate(steps_raw):
        entry: dict = {
            "step_index": idx,
            "step_type_gen": s.get("step_type_gen"),
            "step_type_spec": s.get("step_type_spec"),
            "step_ulid": s.get("step_ulid") or s.get("ulid", ""),
            "status": s.get("status", "pending"),
        }
        steps_out.append(entry)

    engine = detail.get("engine_family", "")

    payload: dict = {
        "calc_ulid": detail.get("calc_ulid") or detail.get("ulid", calc_ulid),
        "name": detail.get("name", ""),
        "engine": engine,
        "structure": detail.get("structure_name") or detail.get("structure"),
        "n_steps": detail.get("n_steps", len(steps_out)),
        "steps": steps_out,
    }

    # --- resource status (best-effort) ---
    try:
        from quantumvitas.mcp.tools._resource_utils import check_resource_status

        payload["resource_status"] = check_resource_status(calc_ulid, svc)
    except Exception:
        pass

    # --- optional step detail ---
    if step >= 0:
        if step >= len(steps_raw):
            return make_error(
                "invalid_step_index",
                f"Step index {step} out of range (calculation has {len(steps_raw)} step(s)).",
            )
        step_ulid = steps_out[step]["step_ulid"]
        step_params: dict = {}
        try:
            step_detail = svc.calculation.get_step_detail(calc_ulid, step_ulid)
            step_params = step_detail.get("parameters", {})
            payload["step_detail"] = {
                "step_index": step,
                "step_ulid": step_ulid,
                "parameters": step_params,
                "cards": step_detail.get("cards", {}),
            }
        except Exception as exc:
            payload["step_detail_error"] = str(exc)

        step_type_gen = steps_out[step].get("step_type_gen", "")
        step_cards = step_detail.get("cards", {}) if "step_detail" in payload else {}

        # --- preflight ---
        _run_preflight(
            payload, engine, step_params, detail, steps_out, step, step_type_gen, svc,
            step_cards=step_cards,
        )

        # --- dry_run materialization ---
        if dry_run:
            _run_dry_run(
                payload, engine, step_type_gen, step_params, detail, svc,
                step_cards=step_cards,
            )

    hint = (
        f"Use set_parameters(calc_ulid='{calc_ulid}') to adjust, "
        f"or run_calculation(calc_ulid='{calc_ulid}') to execute."
    )
    if step >= 0:
        hint += (
            f" Use inspect_calculation(calc_ulid='{calc_ulid}', step={step}, dry_run=True) "
            "to preview input files and run preflight checks."
        )
    return make_response(payload, context_hint=hint)


def _run_preflight(
    payload: dict,
    engine: str,
    step_params: dict,
    detail: dict,
    steps_out: list[dict],
    step_index: int,
    step_type_gen: str,
    svc: object,
    *,
    step_cards: dict | None = None,
) -> None:
    """Run the engine's preflight checker (best-effort, never fails the tool)."""
    try:
        import quantumvitas.drivers  # noqa: F401 — trigger registration
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver(engine)
        checker = driver.get_preflight_checker()
        if checker is None:
            return

        # Build structure_info
        structure_info = _build_structure_info(detail, svc)

        # Merge cards into a copy of step_params so preflight can see K_POINTS
        merged_params = dict(step_params)
        _merge_cards_into_params(merged_params, step_cards or {}, structure_info)

        # Build workflow_context
        gen_steps = [s.get("step_type_gen", "") for s in steps_out]
        workflow_context = {
            "gen_steps": gen_steps,
            "current_step_index": step_index,
            "current_step_gen": step_type_gen,
            "other_steps_params": {},
        }

        issues = checker.check(merged_params, structure_info, workflow_context)
        if issues:
            payload["preflight_issues"] = [
                {
                    "code": iss.code,
                    "severity": iss.severity,
                    "message": iss.message,
                    "parameter": iss.parameter,
                    "suggestion": iss.suggestion,
                }
                for iss in issues
            ]
    except Exception:
        pass  # Best-effort: never cause tool failure


def _run_dry_run(
    payload: dict,
    engine: str,
    step_type_gen: str,
    step_params: dict,
    detail: dict,
    svc: object,
    *,
    step_cards: dict | None = None,
) -> None:
    """Materialize input files to a tmpdir and attach content to payload."""
    import tempfile
    from pathlib import Path

    try:
        import quantumvitas.drivers  # noqa: F401 — trigger registration
        from quantumvitas.core.driver_registry import DriverRegistry
        from quantumvitas.inputformat.writer import write_engine_inputs

        driver = DriverRegistry.get_driver(engine)
        spec = driver.get_input_spec(gen_type=step_type_gen)
        if spec is None:
            payload["dry_run_error"] = (
                f"Engine '{engine}' does not provide an input spec for gen_type='{step_type_gen}'."
            )
            return

        # Build StructureDoc from calculation's structure
        structure_doc = _build_structure_doc(detail, svc)

        # Merge cards into a copy of step_params so the writer sees K_POINTS, nat, ntyp
        merged_params = dict(step_params)
        structure_info = _build_structure_info(detail, svc)
        _merge_cards_into_params(merged_params, step_cards or {}, structure_info)

        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_engine_inputs(
                spec, Path(tmpdir), merged_params, structure_doc,
            )
            input_files: list[dict] = []
            for fpath in written:
                try:
                    content = fpath.read_text()
                except Exception:
                    content = "<binary or unreadable>"
                input_files.append({
                    "filename": fpath.name,
                    "content": content,
                })
            payload["input_files"] = input_files

    except Exception as exc:
        payload["dry_run_error"] = str(exc)


def _build_structure_info(detail: dict, svc: object) -> dict | None:
    """Build a lightweight structure_info dict for the preflight checker."""
    structure_ulid = detail.get("structure_ulid")
    if not structure_ulid:
        return None

    try:
        elements_raw = detail.get("structure_elements", [])
        atoms = svc.structure.get_atoms(structure_ulid)
        species = atoms.get("species", [])
        n_atoms = atoms.get("num_atoms", len(species))
        elements = set(elements_raw) if elements_raw else set(species)

        return {
            "species": species,
            "n_atoms": n_atoms,
            "elements": elements,
            "is_periodic": atoms.get("lattice") is not None,
        }
    except Exception:
        return None


def _build_structure_doc(detail: dict, svc: object) -> dict | None:
    """Build a StructureDoc dict (lattice, species, frac_coords) for materialization."""
    structure_ulid = detail.get("structure_ulid")
    if not structure_ulid:
        return None

    try:
        import numpy as np

        atoms = svc.structure.get_atoms(structure_ulid)
        lattice = atoms.get("lattice")
        species = atoms.get("species", [])
        positions = atoms.get("positions", [])  # Cartesian, Angstrom

        if lattice is None or not positions:
            return None

        # Convert Cartesian → fractional: frac = cart @ inv(lattice)
        lat_matrix = np.array(lattice)
        cart_coords = np.array(positions)
        inv_lat = np.linalg.inv(lat_matrix)
        frac_coords = cart_coords @ inv_lat

        return {
            "lattice": [list(row) for row in lat_matrix],
            "species": species,
            "frac_coords": [list(fc) for fc in frac_coords],
            "comment": detail.get("name", ""),
        }
    except Exception:
        return None


def _merge_cards_into_params(
    params: dict,
    cards: dict,
    structure_info: dict | None,
) -> None:
    """Merge QE cards (K_POINTS, etc.) and structure counts into *params* in-place.

    This bridges the gap between the step YAML representation (where cards and
    parameters are separate) and the inputformat writer (which expects a flat
    params dict with a ``kpoints`` key).

    Also injects ``nat`` and ``ntyp`` from *structure_info* into the SYSTEM
    namelist when they are missing — the actual run path does this in
    ``QEInputGenerator`` but dry_run bypasses that path.
    """
    # --- K_POINTS ---
    if "kpoints" not in params:
        kp = cards.get("K_POINTS", {})
        if kp:
            data = kp.get("data", [[4, 4, 4, 0, 0, 0]])
            row = data[0] if data else [4, 4, 4, 0, 0, 0]
            params["kpoints"] = {
                "mesh": list(row[:3]),
                "shift": list(row[3:6]) if len(row) >= 6 else [0, 0, 0],
            }

    # --- nat / ntyp from structure ---
    if structure_info is not None:
        system = params.get("SYSTEM", {})
        if "nat" not in system and "nat" not in params:
            n_atoms = structure_info.get("n_atoms")
            if n_atoms:
                params.setdefault("SYSTEM", {})["nat"] = n_atoms
        if "ntyp" not in system and "ntyp" not in params:
            elements = structure_info.get("elements")
            if elements:
                params.setdefault("SYSTEM", {})["ntyp"] = len(elements)
