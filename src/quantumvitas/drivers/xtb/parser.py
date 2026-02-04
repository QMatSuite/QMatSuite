"""xTB output parser.

Parses xTB calculation results from stdout and output files.
Adapted from engine_explorations/xtb/scripts/xtb_parser.py.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def parse_xtb_stdout(text: str) -> dict[str, Any]:
    """Parse xTB stdout for key results.

    Extracts:
    - total_energy_Eh: Total energy in Hartree
    - gradient_norm: Gradient norm in Eh/a0
    - homo_lumo_gap_eV: HOMO-LUMO gap in eV
    - converged: Whether optimization converged
    - opt_cycles: Number of optimization cycles
    - normal_termination: Whether run terminated normally
    """
    result: dict[str, Any] = {}

    m = re.search(
        r"\|\s*TOTAL ENERGY\s+([-\d.]+)\s+Eh\s*\|", text
    )
    if m:
        result["total_energy_Eh"] = float(m.group(1))

    m = re.search(
        r"\|\s*GRADIENT NORM\s+([-\d.]+)\s+Eh/", text
    )
    if m:
        result["gradient_norm"] = float(m.group(1))

    m = re.search(
        r"\|\s*HOMO-LUMO GAP\s+([-\d.]+)\s+eV\s*\|", text
    )
    if m:
        result["homo_lumo_gap_eV"] = float(m.group(1))

    m = re.search(
        r"GEOMETRY OPTIMIZATION CONVERGED AFTER\s+(\d+)\s+ITERATIONS", text
    )
    if m:
        result["converged"] = True
        result["opt_cycles"] = int(m.group(1))
    elif "FAILED TO CONVERGE" in text.upper():
        result["converged"] = False

    result["normal_termination"] = "normal termination of xtb" in text

    return result


def parse_xtbopt_xyz(path: Path) -> dict[str, Any]:
    """Parse xtbopt.xyz for optimized geometry.

    Returns dict with:
    - energy_Eh: Energy from comment line
    - gnorm: Gradient norm from comment line
    - atoms: list of {"element": str, "x": float, "y": float, "z": float}
    - n_atoms: number of atoms
    """
    text = path.read_text().strip()
    lines = text.split("\n")

    result: dict[str, Any] = {}

    if len(lines) < 3:
        raise ValueError(f"xtbopt.xyz too short ({len(lines)} lines)")

    n_atoms = int(lines[0].strip())
    result["n_atoms"] = n_atoms

    comment = lines[1]
    m = re.search(r"energy:\s+([-\d.]+)", comment)
    if m:
        result["energy_Eh"] = float(m.group(1))

    m = re.search(r"gnorm:\s+([-\d.]+)", comment)
    if m:
        result["gnorm"] = float(m.group(1))

    atoms = []
    for i in range(2, 2 + n_atoms):
        parts = lines[i].split()
        if len(parts) >= 4:
            atoms.append({
                "element": parts[0],
                "x": float(parts[1]),
                "y": float(parts[2]),
                "z": float(parts[3]),
            })
    result["atoms"] = atoms

    return result


def check_success(working_dir: Path) -> bool:
    """Check if xTB optimization succeeded via .xtboptok marker."""
    return (working_dir / ".xtboptok").exists()
