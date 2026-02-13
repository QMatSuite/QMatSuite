"""
Compiler: converts a demo snapshot dict into fine-grained AuthoringOps.

Each parameter leaf becomes its own SetField op. Default reconciliation
ensures QE defaults injected by AddStep are cleaned up when absent from
the demo. Non-QE engines have empty defaults, so no cleanup needed.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.demo_store.authoring_ops import (
    AddStep,
    AuthoringOp,
    ConfigureSpeciesMap,
    CreateCalculation,
    ImportStructure,
    InitProject,
    ReplaceMap,
    SetField,
    UnsetField,
)
from quantumvitas.demo_store.roundtrip import MANAGED_KEYS_BY_ENGINE


def compile_snapshot(snapshot: dict) -> list[AuthoringOp]:
    """
    Compile a demo snapshot dict into fine-grained AuthoringOps.

    Args:
        snapshot: Demo snapshot dict (as loaded from .yml file)

    Returns:
        List of AuthoringOps that reproduce the snapshot via QVService
    """
    from quantumvitas.core.resources import slugify

    ops: list[AuthoringOp] = []

    # 1. InitProject
    project = snapshot.get("project", {})
    project_meta = project.get("meta", {})
    project_name = project_meta.get("name", "demo")
    ops.append(InitProject(name=project_name))

    # 2. ImportStructure — track ulid→slug mapping for calc references
    ulid_to_slug: dict[str, str] = {}
    for struct in snapshot.get("structures", []):
        struct_meta = struct.get("meta", {})
        struct_name = struct_meta.get("name", "structure")
        struct_ulid = struct_meta.get("ulid", "")
        struct_data = struct.get("data", {})

        ops.append(ImportStructure(name=struct_name, structure_data=struct_data))
        if struct_ulid:
            # Use slugified name for selector (matches what import_file generates)
            ulid_to_slug[struct_ulid] = slugify(struct_name)

    # 3. Calculations
    for calc in snapshot.get("calculations", []):
        calc_meta = calc.get("meta", {})
        calc_name = calc_meta.get("name", "calculation")
        calc_slug = slugify(calc_name)  # Use slugify to match init_calculation
        engine_family = calc.get("engine_family", "qe")

        # Resolve structure reference
        structure_ulid = calc.get("structure_ulid", "")
        structure_selector = ulid_to_slug.get(structure_ulid, "")

        ops.append(CreateCalculation(
            name=calc_name,
            engine_family=engine_family,
            structure_selector=structure_selector,
        ))

        # 3b. Steps
        managed = MANAGED_KEYS_BY_ENGINE.get(engine_family, set())

        for step in calc.get("steps", []):
            step_meta = step.get("meta", {})
            step_name = step_meta.get("name", "step")
            step_slug = slugify(step_name)  # Use slugify to match add_step
            step_type_spec = step.get("step_type_spec", "")

            from quantumvitas.workflow.step_type_convert import gen_from
            step_type_gen = gen_from(step_type_spec)

            ops.append(AddStep(
                calc_selector=calc_slug,
                step_type_gen=step_type_gen,
                name=step_name,
            ))

            target = f"step:{calc_slug}/{step_slug}"

            # Reconcile defaults (unset keys injected by AddStep that are absent from demo)
            ops.extend(_reconcile_defaults(
                step_type_spec, engine_family, step, target, managed
            ))

            # Emit SetField for each parameter leaf (skip managed keys)
            demo_params = step.get("parameters", {})
            for pointer, value in _walk_leaves(demo_params, "/parameters"):
                # Skip managed keys
                parts = pointer.split("/")
                if _is_managed(parts, managed):
                    continue
                ops.append(SetField(target=target, pointer=pointer, value=value))

            # Emit ReplaceMap for each card
            for card_key, card_data in step.get("cards", {}).items():
                ops.append(ReplaceMap(
                    target=target,
                    pointer=f"/cards/{card_key}",
                    value=card_data,
                ))

            # Emit ReplaceMap for each species_overrides entry
            for species_key, species_data in step.get("species_overrides", {}).items():
                ops.append(ReplaceMap(
                    target=target,
                    pointer=f"/species_overrides/{species_key}",
                    value=species_data,
                ))

            # Emit SetField for input_name if present
            if "input_name" in step:
                ops.append(SetField(
                    target=target,
                    pointer="/input_name",
                    value=step["input_name"],
                ))

        # 3c. ConfigureSpeciesMap (strip pseudo file metadata)
        species_map = calc.get("species_map")
        if species_map:
            cleaned_map = {}
            for species, data in species_map.items():
                cleaned = {
                    k: v for k, v in data.items()
                    if k not in ("pseudo_sha256", "pseudo_sha_family", "pseudo_basename")
                }
                cleaned_map[species] = cleaned
            ops.append(ConfigureSpeciesMap(
                calc_selector=calc_slug,
                species_map=cleaned_map,
            ))

    return ops


def _reconcile_defaults(
    step_type_spec: str,
    engine: str,
    demo_step: dict,
    target: str,
    managed: set,
) -> list[AuthoringOp]:
    """
    Emit UnsetField ops to remove default keys that are absent from the demo step.

    After AddStep, QE steps get default parameters injected. If the demo doesn't
    have those keys, we must unset them to match. Non-QE steps have empty defaults.
    """
    from quantumvitas.calculation.step_defaults import get_default_step_params

    defaults = get_default_step_params(step_type_spec)
    default_params = defaults.get("parameters", {})
    default_cards = defaults.get("cards", {})
    demo_params = demo_step.get("parameters", {})
    demo_cards = demo_step.get("cards", {})

    ops: list[AuthoringOp] = []

    # Unset default parameter sections absent from demo
    for section_key in default_params:
        if section_key in managed:
            continue
        if section_key not in demo_params:
            ops.append(UnsetField(target=target, pointer=f"/parameters/{section_key}"))
        elif isinstance(default_params[section_key], dict):
            # Unset leaf keys within shared sections that are in defaults but not demo
            for leaf_key in default_params[section_key]:
                if leaf_key in managed:
                    continue
                if leaf_key not in demo_params.get(section_key, {}):
                    ops.append(UnsetField(
                        target=target,
                        pointer=f"/parameters/{section_key}/{leaf_key}",
                    ))

    # Unset default cards absent from demo
    for card_key in default_cards:
        if card_key not in demo_cards:
            ops.append(UnsetField(target=target, pointer=f"/cards/{card_key}"))

    # Unset default species_overrides absent from demo
    default_species = defaults.get("species_overrides", {})
    demo_species = demo_step.get("species_overrides", {})
    for species_key in default_species:
        if species_key not in demo_species:
            ops.append(UnsetField(
                target=target,
                pointer=f"/species_overrides/{species_key}",
            ))

    return ops


def _walk_leaves(d: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """
    Recursively yield (pointer, value) for each leaf in a nested dict.

    - dict → recurse deeper (not a leaf)
    - Everything else (scalar, list, None) → yield as leaf

    Examples:
        _walk_leaves({"CONTROL": {"calculation": "scf"}}, "/parameters")
        → [("/parameters/CONTROL/calculation", "scf")]

        _walk_leaves({"ENCUT": 240}, "/parameters")
        → [("/parameters/ENCUT", 240)]
    """
    if not isinstance(d, dict):
        return [(prefix, d)]

    result = []
    for key, value in d.items():
        child_path = f"{prefix}/{key}"
        if isinstance(value, dict) and value:
            # Non-empty dict → recurse deeper
            result.extend(_walk_leaves(value, child_path))
        elif isinstance(value, dict):
            # Empty dict → skip (cannot be set via yamldoc.set(), not meaningful content)
            pass
        else:
            result.append((child_path, value))
    return result


def _is_managed(pointer_parts: list[str], managed: set) -> bool:
    """Check if any part of the pointer path is a managed key."""
    # pointer_parts is like ["", "parameters", "CONTROL", "outdir"]
    # Check if any leaf or section key is managed
    for part in pointer_parts:
        if part in managed:
            return True
    return False
