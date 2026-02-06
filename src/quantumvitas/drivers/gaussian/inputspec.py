"""Gaussian engine input specification for the universal writer.

Single combined file: input.gjf containing parameters + geometry.
"""

from __future__ import annotations

from typing import Any

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)


def _write_gaussian_text(fragment: dict[str, Any]) -> str:
    """Write Gaussian .gjf text from combined params + structure.

    Pure-function writer. Generates a minimal Gaussian input file
    from SSOT data without requiring pymatgen at write time.

    Args:
        fragment: {"params": {...}, "structure": {...}} where structure
            has lattice/species/frac_coords (or cart_coords).
    """
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}

    method = params.get("method", "HF")
    basis = params.get("basis", "STO-3G")
    charge = params.get("charge", 0)
    multiplicity = params.get("multiplicity", 1)
    mem = params.get("mem", "500MB")
    nproc = params.get("nproc", 1)
    gen_type = params.get("gen_type", "scf")
    title = params.get("title", "Gaussian calculation")
    td_nstates = params.get("td_nstates", 3)
    opt_tight = params.get("opt_tight", False)
    chk_name = params.get("chk_name", "calc.chk")

    lines: list[str] = []

    # Link0 commands
    lines.append(f"%mem={mem}")
    lines.append(f"%nproc={nproc}")
    lines.append(f"%chk={chk_name}")

    # Route line
    route = f"#p {method}/{basis}"
    if gen_type == "relax":
        route += " Opt=Tight" if opt_tight else " Opt"
    elif gen_type == "freq":
        route += " Freq"
    elif gen_type == "td":
        route += f" TD=(NStates={td_nstates})"

    lines.append(route)
    lines.append("")
    lines.append(title)
    lines.append("")
    lines.append(f"{charge} {multiplicity}")

    # Coordinates: use Cartesian from structure
    species = structure.get("species", [])
    lattice = structure.get("lattice", [])
    frac_coords = structure.get("frac_coords", [])
    cart_coords = structure.get("cart_coords", [])

    if cart_coords:
        for sym, pos in zip(species, cart_coords):
            lines.append(f"{sym:2s}  {pos[0]:12.6f}  {pos[1]:12.6f}  {pos[2]:12.6f}")
    elif frac_coords and lattice:
        # Convert fractional to Cartesian
        for sym, fc in zip(species, frac_coords):
            x = sum(fc[j] * lattice[j][i] for j in range(3) for i in [0]) if False else (
                fc[0] * lattice[0][0] + fc[1] * lattice[1][0] + fc[2] * lattice[2][0]
            )
            y = fc[0] * lattice[0][1] + fc[1] * lattice[1][1] + fc[2] * lattice[2][1]
            z = fc[0] * lattice[0][2] + fc[1] * lattice[1][2] + fc[2] * lattice[2][2]
            lines.append(f"{sym:2s}  {x:12.6f}  {y:12.6f}  {z:12.6f}")

    lines.append("")  # Required trailing blank line
    return "\n".join(lines) + "\n"


def get_gaussian_input_spec(**context: Any) -> EngineInputSpec:
    """Return the Gaussian EngineInputSpec."""
    return EngineInputSpec(
        engine_family="gaussian",
        syntax_family="keyword-block",
        input_files=(
            InputFileSpec(
                filename="input.gjf",
                content_role="combined",
                description="Gaussian input file (route + geometry)",
                custom_writer=_write_gaussian_text,
            ),
        ),
        resource_refs=(
            ResourceRefSpec(
                name="checkpoint",
                description="Checkpoint file (.chk) for restart",
                staging_policy="copy",
            ),
        ),
        ssot_mapping=SSOTMappingSpec(
            structure_in=("input.gjf",),
            params_in=("input.gjf",),
        ),
    )
