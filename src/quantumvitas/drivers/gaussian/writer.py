"""Gaussian input file writer.

Generates Gaussian .gjf input files from pymatgen structures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from pymatgen.core import Molecule, Structure


def write_gaussian_input(
    structure: Union[Molecule, Structure],
    output_path: Path,
    gen_type: str,
    method: str = "HF",
    basis: str = "STO-3G",
    charge: int = 0,
    multiplicity: int = 1,
    mem: str = "500MB",
    nproc: int = 1,
    td_nstates: int = 3,
    opt_tight: bool = False,
    title: str = "Gaussian calculation",
) -> Path:
    """
    Write a Gaussian input file (.gjf) from a pymatgen structure.

    Args:
        structure: Pymatgen Molecule or Structure
        output_path: Path to write the .gjf file
        gen_type: Step type gen (scf, hf, relax, freq, mp2, td)
        method: Computational method (HF, B3LYP, MP2, etc.)
        basis: Basis set (STO-3G, 6-31G*, cc-pVDZ, etc.)
        charge: Molecular charge
        multiplicity: Spin multiplicity
        mem: Memory allocation (e.g., "500MB", "2GB")
        nproc: Number of processors
        td_nstates: Number of TDDFT states (for td step type)
        opt_tight: Use tight optimization convergence
        title: Job title

    Returns:
        Path to the written file
    """
    output_path = Path(output_path)
    lines = []

    # Link0 commands
    lines.append(f"%mem={mem}")
    lines.append(f"%nproc={nproc}")
    chk_name = output_path.stem + ".chk"
    lines.append(f"%chk={chk_name}")

    # Route line
    route = "#p "
    route += f"{method}/{basis}"

    # Add keywords based on step type
    if gen_type == "relax":
        opt_kw = "Opt"
        if opt_tight:
            opt_kw = "Opt=Tight"
        route += f" {opt_kw}"
    elif gen_type == "freq":
        route += " Freq"
    elif gen_type == "td":
        route += f" TD=(NStates={td_nstates})"
    # scf, hf, mp2 are implicit in method choice

    lines.append(route)
    lines.append("")  # Blank line

    # Title
    lines.append(title)
    lines.append("")  # Blank line

    # Charge and multiplicity
    lines.append(f"{charge} {multiplicity}")

    # Atom coordinates
    if isinstance(structure, Molecule):
        for site in structure:
            symbol = site.specie.symbol
            x, y, z = site.coords
            lines.append(f"{symbol:2s}  {x:12.6f}  {y:12.6f}  {z:12.6f}")
    else:
        # Structure (periodic) - use Cartesian coordinates
        for site in structure:
            symbol = site.specie.symbol
            x, y, z = site.coords
            lines.append(f"{symbol:2s}  {x:12.6f}  {y:12.6f}  {z:12.6f}")

    lines.append("")  # Required blank line at end

    content = "\n".join(lines) + "\n"  # Ensure file ends with newline
    output_path.write_text(content)

    return output_path
