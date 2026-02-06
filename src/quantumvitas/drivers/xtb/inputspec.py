"""xTB engine input specification for the universal writer.

Single structure file: input.xyz. Command-line parameters stay in handler.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    SSOTMappingSpec,
)


def _write_xyz_text(structure: dict[str, Any] | None) -> str:
    """Write XYZ text from a StructureDoc dict.

    Pure function, stdlib only. Converts fractional coords to Cartesian
    using lattice, then writes standard XYZ format.
    """
    if not structure:
        return ""

    species = structure.get("species", [])
    lattice = structure.get("lattice", [])
    frac_coords = structure.get("frac_coords", [])
    comment = structure.get("comment", "")

    n_atoms = len(species)
    lines: list[str] = [str(n_atoms), comment]

    for sym, fc in zip(species, frac_coords):
        # Fractional to Cartesian: cart = frac @ lattice
        x = fc[0] * lattice[0][0] + fc[1] * lattice[1][0] + fc[2] * lattice[2][0]
        y = fc[0] * lattice[0][1] + fc[1] * lattice[1][1] + fc[2] * lattice[2][1]
        z = fc[0] * lattice[0][2] + fc[1] * lattice[1][2] + fc[2] * lattice[2][2]
        lines.append(f"{sym:>2s}  {x:16.10f}  {y:16.10f}  {z:16.10f}")

    return "\n".join(lines) + "\n"


def get_xtb_input_spec(**context: Any) -> EngineInputSpec:
    """Return the xTB EngineInputSpec."""
    return EngineInputSpec(
        engine_family="xtb",
        syntax_family="dollar-flag",
        input_files=(
            InputFileSpec(
                filename="input.xyz",
                content_role="structure",
                description="XYZ coordinate file",
                custom_writer=_write_xyz_text,
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("input.xyz",),
        ),
    )
