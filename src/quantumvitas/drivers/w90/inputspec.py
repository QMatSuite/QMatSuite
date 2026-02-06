"""Wannier90 engine input specification for the universal writer.

Single combined file: wannier90.win containing parameters + structure.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def _write_win_text(fragment: dict[str, Any]) -> str:
    """Write Wannier90 .win text from combined params + structure.

    Generates flat-keyval format with begin/end blocks.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    lines: list[str] = []

    # Scalar parameters
    skip_keys = {"projections", "kpoints", "kpoint_path"}
    for key, val in sorted(params.items()):
        if key in skip_keys:
            continue
        if isinstance(val, bool):
            val_str = ".true." if val else ".false."
        elif isinstance(val, (list, tuple)):
            continue  # Handle blocks separately
        else:
            val_str = str(val)
        lines.append(f"{key} = {val_str}")
    lines.append("")

    # Unit cell
    lattice = structure.get("lattice", [])
    if lattice:
        lines.append("begin unit_cell_cart")
        lines.append("ang")
        for vec in lattice:
            lines.append(f"  {vec[0]:.10f}  {vec[1]:.10f}  {vec[2]:.10f}")
        lines.append("end unit_cell_cart")
        lines.append("")

    # Atomic positions
    species = structure.get("species", [])
    frac_coords = structure.get("frac_coords", [])
    if species and frac_coords:
        lines.append("begin atoms_frac")
        for sym, fc in zip(species, frac_coords):
            lines.append(f"  {sym}  {fc[0]:.10f}  {fc[1]:.10f}  {fc[2]:.10f}")
        lines.append("end atoms_frac")
        lines.append("")

    # Projections block
    projections = params.get("projections", [])
    if projections:
        lines.append("begin projections")
        for proj in projections:
            lines.append(f"  {proj}")
        lines.append("end projections")
        lines.append("")

    # K-point mesh
    kpoints = params.get("kpoints", {})
    if isinstance(kpoints, dict) and kpoints:
        mesh = kpoints.get("mesh", kpoints.get("grid", [4, 4, 4]))
        lines.append(f"mp_grid = {mesh[0]} {mesh[1]} {mesh[2]}")
        lines.append("")

    return "\n".join(lines) + "\n"


def get_w90_input_spec(**context: Any) -> EngineInputSpec:
    """Return the Wannier90 EngineInputSpec."""
    return EngineInputSpec(
        engine_family="w90",
        syntax_family="flat-keyval",
        input_files=(
            InputFileSpec(
                filename="wannier90.win",
                content_role="combined",
                description="Wannier90 input file",
                custom_writer=_write_win_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="amn_mmn_eig",
                description="Wannier90 prerequisites (.amn, .mmn, .eig from DFT)",
                staging_policy="symlink",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("wannier90.win",),
            kpoints_in=("wannier90.win",),
            params_in=("wannier90.win",),
        ),
    )
