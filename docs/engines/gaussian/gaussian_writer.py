"""Gaussian input file writer.

Generates Gaussian input files (.gjf) for various calculation types.
This is an exploration utility for understanding Gaussian input structure.

Input file format:
    %Link0 commands (mem, nproc, chk, etc.)
    #route line (method/basis + keywords)

    Title

    charge multiplicity
    atom1 x1 y1 z1
    atom2 x2 y2 z2
    ...

    (blank line at end)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class GaussianParams:
    """Common parameters for all Gaussian calculations."""
    # Link0 commands
    mem: str = "500MB"  # Memory allocation (e.g., "500MB", "2GB")
    nproc: int = 1  # Number of processors
    chk: str | None = None  # Checkpoint file name

    # Method and basis
    method: str = "HF"  # e.g., HF, B3LYP, MP2, CCSD, etc.
    basis: str = "STO-3G"  # e.g., STO-3G, 6-31G*, cc-pVDZ

    # Job type
    job_type: Literal["sp", "opt", "freq", "opt+freq", "force", "td"] = "sp"

    # TDDFT-specific
    td_nstates: int = 3  # Number of excited states for TDDFT

    # Optimization-specific
    opt_tight: bool = False  # Use tight convergence
    opt_calcfc: bool = False  # Calculate force constants at start

    # Additional keywords
    extra_keywords: list[str] = field(default_factory=list)

    # Print level
    verbose: bool = True  # Use #p (verbose) instead of #


@dataclass
class Atom:
    """Single atom with coordinates."""
    element: str
    x: float
    y: float
    z: float


@dataclass
class Molecule:
    """Molecular structure."""
    atoms: list[Atom]
    charge: int = 0
    multiplicity: int = 1
    title: str = "Gaussian calculation"


def write_link0_section(params: GaussianParams) -> str:
    """Generate Link0 commands section."""
    lines = []

    lines.append(f"%mem={params.mem}")
    lines.append(f"%nproc={params.nproc}")

    if params.chk:
        lines.append(f"%chk={params.chk}")

    return "\n".join(lines)


def write_route_section(params: GaussianParams) -> str:
    """Generate route section (#p line)."""
    # Start with print level
    route = "#p " if params.verbose else "#"

    # Method/basis
    route += f"{params.method}/{params.basis}"

    # Job type keywords
    if params.job_type == "sp":
        pass  # Single point is default
    elif params.job_type == "opt":
        opt_kw = "Opt"
        if params.opt_tight:
            opt_kw += "=Tight"
        if params.opt_calcfc:
            opt_kw = opt_kw.replace("Opt", "Opt=") + ",CalcFC" if "=" in opt_kw else "Opt=CalcFC"
        route += f" {opt_kw}"
    elif params.job_type == "freq":
        route += " Freq"
    elif params.job_type == "opt+freq":
        route += " Opt Freq"
    elif params.job_type == "force":
        route += " Force"
    elif params.job_type == "td":
        route += f" TD=(NStates={params.td_nstates})"

    # Extra keywords
    for kw in params.extra_keywords:
        route += f" {kw}"

    return route


def write_molecule_section(mol: Molecule) -> str:
    """Generate molecule specification section."""
    lines = []

    # Charge and multiplicity
    lines.append(f"{mol.charge} {mol.multiplicity}")

    # Atom coordinates
    for atom in mol.atoms:
        lines.append(f"{atom.element:2s}  {atom.x:12.6f}  {atom.y:12.6f}  {atom.z:12.6f}")

    return "\n".join(lines)


def write_gaussian_input(
    mol: Molecule,
    params: GaussianParams,
    output_path: Path | str,
) -> Path:
    """Write a complete Gaussian input file.

    Args:
        mol: Molecular structure
        params: Calculation parameters
        output_path: Path for output .gjf file

    Returns:
        Path to written file
    """
    output_path = Path(output_path)

    sections = [
        write_link0_section(params),
        write_route_section(params),
        "",  # Blank line
        mol.title,
        "",  # Blank line
        write_molecule_section(mol),
        "",  # Blank line at end (required by Gaussian)
    ]

    content = "\n".join(sections)
    output_path.write_text(content)

    return output_path


# ============================================================
# Convenience functions for common calculation types
# ============================================================

def write_sp_input(
    mol: Molecule,
    method: str,
    basis: str,
    output_path: Path | str,
    mem: str = "500MB",
    nproc: int = 1,
) -> Path:
    """Write a single-point energy input file."""
    params = GaussianParams(
        mem=mem,
        nproc=nproc,
        chk=Path(output_path).stem + ".chk",
        method=method,
        basis=basis,
        job_type="sp",
    )
    return write_gaussian_input(mol, params, output_path)


def write_opt_input(
    mol: Molecule,
    method: str,
    basis: str,
    output_path: Path | str,
    mem: str = "500MB",
    nproc: int = 1,
    tight: bool = False,
) -> Path:
    """Write a geometry optimization input file."""
    params = GaussianParams(
        mem=mem,
        nproc=nproc,
        chk=Path(output_path).stem + ".chk",
        method=method,
        basis=basis,
        job_type="opt",
        opt_tight=tight,
    )
    return write_gaussian_input(mol, params, output_path)


def write_freq_input(
    mol: Molecule,
    method: str,
    basis: str,
    output_path: Path | str,
    mem: str = "500MB",
    nproc: int = 1,
) -> Path:
    """Write a frequency calculation input file."""
    params = GaussianParams(
        mem=mem,
        nproc=nproc,
        chk=Path(output_path).stem + ".chk",
        method=method,
        basis=basis,
        job_type="freq",
    )
    return write_gaussian_input(mol, params, output_path)


def write_opt_freq_input(
    mol: Molecule,
    method: str,
    basis: str,
    output_path: Path | str,
    mem: str = "500MB",
    nproc: int = 1,
) -> Path:
    """Write an optimization + frequency input file."""
    params = GaussianParams(
        mem=mem,
        nproc=nproc,
        chk=Path(output_path).stem + ".chk",
        method=method,
        basis=basis,
        job_type="opt+freq",
    )
    return write_gaussian_input(mol, params, output_path)


def write_tddft_input(
    mol: Molecule,
    method: str,
    basis: str,
    output_path: Path | str,
    nstates: int = 3,
    mem: str = "500MB",
    nproc: int = 1,
) -> Path:
    """Write a TDDFT excited states input file."""
    params = GaussianParams(
        mem=mem,
        nproc=nproc,
        chk=Path(output_path).stem + ".chk",
        method=method,
        basis=basis,
        job_type="td",
        td_nstates=nstates,
    )
    return write_gaussian_input(mol, params, output_path)


# ============================================================
# Example molecules for testing
# ============================================================

def water_molecule() -> Molecule:
    """Return a water molecule."""
    return Molecule(
        atoms=[
            Atom("O", 0.000000, 0.000000, 0.117499),
            Atom("H", 0.000000, 0.756950, -0.469996),
            Atom("H", 0.000000, -0.756950, -0.469996),
        ],
        charge=0,
        multiplicity=1,
        title="Water molecule",
    )


def ethylene_molecule() -> Molecule:
    """Return an ethylene molecule."""
    return Molecule(
        atoms=[
            Atom("C", 0.000000, 0.000000, 0.665960),
            Atom("C", 0.000000, 0.000000, -0.665960),
            Atom("H", 0.000000, 0.922843, 1.237532),
            Atom("H", 0.000000, -0.922843, 1.237532),
            Atom("H", 0.000000, 0.922843, -1.237532),
            Atom("H", 0.000000, -0.922843, -1.237532),
        ],
        charge=0,
        multiplicity=1,
        title="Ethylene molecule",
    )


def formaldehyde_molecule() -> Molecule:
    """Return a formaldehyde molecule."""
    return Molecule(
        atoms=[
            Atom("C", 0.000000, 0.000000, 0.000000),
            Atom("O", 0.000000, 0.000000, 1.203000),
            Atom("H", 0.000000, 0.935300, -0.580000),
            Atom("H", 0.000000, -0.935300, -0.580000),
        ],
        charge=0,
        multiplicity=1,
        title="Formaldehyde molecule",
    )


if __name__ == "__main__":
    # Generate example input files
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Single point
        sp_path = write_sp_input(
            water_molecule(), "HF", "STO-3G",
            tmpdir / "water_sp.gjf"
        )
        print(f"=== {sp_path.name} ===")
        print(sp_path.read_text())

        # Optimization
        opt_path = write_opt_input(
            water_molecule(), "B3LYP", "6-31G*",
            tmpdir / "water_opt.gjf"
        )
        print(f"=== {opt_path.name} ===")
        print(opt_path.read_text())

        # TDDFT
        td_path = write_tddft_input(
            formaldehyde_molecule(), "B3LYP", "STO-3G",
            tmpdir / "formaldehyde_td.gjf", nstates=3
        )
        print(f"=== {td_path.name} ===")
        print(td_path.read_text())
