"""
Replay engine: replays a list of AuthoringOps against QMSService to build a project.

All ops route through existing QMSService methods — no direct YAML writes.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from qmatsuite.demo_store.authoring_ops import (
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


def replay_ops(ops: list[AuthoringOp], target_dir: Path) -> Path:
    """
    Replay a list of AuthoringOps to create a project under target_dir.

    Args:
        ops: List of AuthoringOps (must start with InitProject)
        target_dir: Parent directory where the project will be created

    Returns:
        Path to the created project root

    Raises:
        ValueError: If ops is empty or doesn't start with InitProject
    """
    if not ops:
        raise ValueError("ops list must not be empty")
    if not isinstance(ops[0], InitProject):
        raise ValueError(f"First op must be InitProject, got {type(ops[0]).__name__}")

    from qmatsuite.api import QMSService

    project_root = None
    svc = None

    for op in ops:
        if isinstance(op, InitProject):
            project_root = QMSService.init_project(target_dir, name=op.name)
            svc = QMSService(project_root)

        elif isinstance(op, ImportStructure):
            _replay_import_structure(svc, op)

        elif isinstance(op, CreateCalculation):
            svc.project.init_calculation(
                name=op.name,
                engine_family=op.engine_family,
                structure_selector=op.structure_selector,
            )

        elif isinstance(op, AddStep):
            svc.calculation.add_step(
                calc_selector=op.calc_selector,
                step_type_gen=op.step_type_gen,
                name=op.name,
            )

        elif isinstance(op, SetField):
            calc_sel, step_sel = _parse_target(op.target)
            nested = _pointer_to_nested_dict(op.pointer, op.value)
            svc.calculation.update_step_params(calc_sel, step_sel, nested)

        elif isinstance(op, UnsetField):
            calc_sel, step_sel = _parse_target(op.target)
            nested = _pointer_to_nested_dict(op.pointer, None)
            svc.calculation.update_step_params(calc_sel, step_sel, nested)

        elif isinstance(op, ReplaceMap):
            calc_sel, step_sel = _parse_target(op.target)
            nested = _pointer_to_nested_dict(op.pointer, op.value)
            svc.calculation.update_step_params(calc_sel, step_sel, nested)

        elif isinstance(op, ConfigureSpeciesMap):
            svc.calculation.update_species_map(
                calc_selector=op.calc_selector,
                species_map=op.species_map,
            )

        else:
            raise ValueError(f"Unknown op type: {type(op).__name__}")

    return project_root


def _replay_import_structure(svc: Any, op: ImportStructure) -> None:
    """Import a structure by writing temp JSON and calling svc.structure.import_file()."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        json.dump(op.structure_data, tmp, indent=2)
        tmp_path = Path(tmp.name)

    try:
        svc.structure.import_file(tmp_path, name=op.name)
    finally:
        tmp_path.unlink(missing_ok=True)


def _parse_target(target: str) -> tuple[str, str]:
    """Parse 'step:<calc_slug>/<step_slug>' into (calc_selector, step_selector)."""
    if not target.startswith("step:"):
        raise ValueError(f"Invalid target format: {target!r}, expected 'step:<calc>/<step>'")
    rest = target[5:]  # strip "step:"
    parts = rest.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid target format: {target!r}, expected 'step:<calc>/<step>'")
    return parts[0], parts[1]


def _pointer_to_nested_dict(pointer: str, value: Any) -> dict:
    """
    Convert a JSON pointer and value into a nested dict.

    Example:
        _pointer_to_nested_dict("/parameters/CONTROL/calculation", "scf")
        → {"parameters": {"CONTROL": {"calculation": "scf"}}}

        _pointer_to_nested_dict("/parameters/CONTROL", None)
        → {"parameters": {"CONTROL": None}}
    """
    if not pointer.startswith("/"):
        raise ValueError(f"Pointer must start with '/': {pointer!r}")

    parts = [p for p in pointer.split("/") if p]
    if not parts:
        raise ValueError(f"Empty pointer: {pointer!r}")

    result: dict = {}
    current = result
    for part in parts[:-1]:
        current[part] = {}
        current = current[part]
    current[parts[-1]] = value
    return result
