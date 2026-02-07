"""xTB writer helpers.

Includes:
- XYZ file writing helpers used by execution handler
- command builder for xTB CLI invocations
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence


def write_xyz_file(
    symbols: Sequence[str],
    positions: Sequence[Sequence[float]],
    output_path: Path,
    comment: str = "",
) -> Path:
    """Write a standard XYZ file.

    Args:
        symbols: Element symbols (e.g., ["O", "H", "H"])
        positions: Cartesian coordinates in Angstrom, shape (n_atoms, 3)
        output_path: Path to write the file
        comment: Comment line (line 2 of XYZ file)

    Returns:
        Path to written file
    """
    n_atoms = len(symbols)
    lines = [str(n_atoms), comment]
    for sym, pos in zip(symbols, positions):
        lines.append(f"{sym:>2s}  {pos[0]:16.10f}  {pos[1]:16.10f}  {pos[2]:16.10f}")
    output_path.write_text("\n".join(lines) + "\n")
    return output_path


def write_xyz_from_pymatgen(
    structure: Any,
    output_path: Path,
    comment: str = "",
) -> Path:
    """Write XYZ file from a pymatgen Structure or Molecule.

    Args:
        structure: pymatgen Structure or Molecule object
        output_path: Path to write the file
        comment: Comment line

    Returns:
        Path to written file
    """
    symbols = [str(site.specie) for site in structure]
    positions = [list(site.coords) for site in structure]
    return write_xyz_file(symbols, positions, output_path, comment)


def build_xtb_command(
    input_file: str = "input.xyz",
    runtype: str = "opt",
    gfn_level: int = 2,
    opt_level: str | None = None,
    charge: int = 0,
    uhf: int = 0,
    solvent: str | None = None,
    solvent_model: str = "alpb",
    xcontrol_file: str | None = None,
    json_output: bool = False,
    accuracy: float | None = None,
    max_iterations: int | None = None,
    extra_flags: list[str] | None = None,
) -> list[str]:
    """Build xTB command-line arguments.

    Args:
        input_file: Path to input XYZ file
        runtype: Calculation type: "sp", "opt", "grad", "hess", "ohess", "md"
        gfn_level: GFN parametrization level (0, 1, 2) or -1 for GFN-FF
        opt_level: Optimization level (crude/sloppy/loose/normal/tight/verytight/extreme)
        charge: Molecular charge
        uhf: Number of unpaired electrons
        solvent: Solvent name for implicit solvation
        solvent_model: "alpb" or "gbsa"
        xcontrol_file: Optional xcontrol input file path
        json_output: Whether to write xtbout.json
        accuracy: SCC accuracy (lower = better)
        max_iterations: Max SCF iterations
        extra_flags: Additional command-line flags

    Returns:
        List of command-line arguments (including "xtb" as first element)
    """
    cmd = ["xtb", input_file]

    # Method
    if gfn_level == -1:
        cmd.append("--gfnff")
    else:
        cmd.extend(["--gfn", str(gfn_level)])

    # Runtype
    if runtype == "sp":
        cmd.append("--sp")
    elif runtype == "opt":
        if opt_level:
            cmd.extend(["--opt", opt_level])
        else:
            cmd.append("--opt")
    elif runtype == "grad":
        cmd.append("--grad")
    elif runtype == "hess":
        cmd.append("--hess")
    elif runtype == "ohess":
        if opt_level:
            cmd.extend(["--ohess", opt_level])
        else:
            cmd.append("--ohess")
    elif runtype == "md":
        cmd.append("--md")

    # Charge and spin
    if charge != 0:
        cmd.extend(["-c", str(charge)])
    if uhf != 0:
        cmd.extend(["-u", str(uhf)])

    # Solvation
    if solvent:
        cmd.extend([f"--{solvent_model}", solvent])

    # xcontrol
    if xcontrol_file:
        cmd.extend(["-I", xcontrol_file])

    # JSON output
    if json_output:
        cmd.append("--json")

    # Accuracy
    if accuracy is not None:
        cmd.extend(["-a", str(accuracy)])

    # Max iterations
    if max_iterations is not None:
        cmd.extend(["--iterations", str(max_iterations)])

    # Extra flags
    if extra_flags:
        cmd.extend(extra_flags)

    return cmd
