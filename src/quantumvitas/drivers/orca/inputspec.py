"""ORCA engine input specification for the universal writer.

Single combined file: {basename}.inp containing keywords + geometry block.
Dynamic filename resolved via get_input_spec(basename=...).
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    SSOTMappingSpec,
)


def _write_orca_text(fragment: dict[str, Any]) -> str:
    """Write ORCA input text from combined params + structure.

    Generates keyword-line + geometry block format.
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    lines: list[str] = []

    # Keyword line
    method = params.get("method", "HF")
    basis = params.get("basis", "def2-SVP")
    keywords = params.get("keywords", [])
    extra_kw = " ".join(keywords) if keywords else ""
    lines.append(f"! {method} {basis} {extra_kw}".rstrip())

    # Additional blocks (%pal, %maxcore, etc.)
    nprocs = params.get("nprocs")
    if nprocs and nprocs > 1:
        lines.append(f"%pal nprocs {nprocs} end")

    maxcore = params.get("maxcore")
    if maxcore:
        lines.append(f"%maxcore {maxcore}")

    # Extra blocks (e.g., %scf, %tddft)
    extra_blocks = params.get("blocks", {})
    for block_name, block_params in extra_blocks.items():
        lines.append(f"%{block_name}")
        for k, v in block_params.items():
            lines.append(f"  {k} {v}")
        lines.append("end")

    lines.append("")

    # Geometry block
    charge = params.get("charge", 0)
    multiplicity = params.get("multiplicity", 1)
    lines.append(f"* xyz {charge} {multiplicity}")

    species = structure.get("species", [])
    frac_coords = structure.get("frac_coords", [])
    lattice = structure.get("lattice", [])

    # Convert fractional to Cartesian
    for sym, fc in zip(species, frac_coords):
        if lattice:
            x = fc[0] * lattice[0][0] + fc[1] * lattice[1][0] + fc[2] * lattice[2][0]
            y = fc[0] * lattice[0][1] + fc[1] * lattice[1][1] + fc[2] * lattice[2][1]
            z = fc[0] * lattice[0][2] + fc[1] * lattice[1][2] + fc[2] * lattice[2][2]
        else:
            x, y, z = fc[0], fc[1], fc[2]
        lines.append(f"  {sym:2s}  {x:14.8f}  {y:14.8f}  {z:14.8f}")

    lines.append("*")
    lines.append("")

    return "\n".join(lines) + "\n"


def get_orca_input_spec(**context: Any) -> EngineInputSpec:
    """Return the ORCA EngineInputSpec.

    Args:
        **context: May contain basename for dynamic filename.
    """
    basename = context.get("basename", "orca_calc")
    filename = f"{basename}.inp"

    return EngineInputSpec(
        engine_family="orca",
        syntax_family="keyword-block",
        input_files=(
            InputFileSpec(
                filename=filename,
                content_role="combined",
                description="ORCA input file (keywords + geometry)",
                custom_writer=_write_orca_text,
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=(filename,),
            params_in=(filename,),
        ),
    )
