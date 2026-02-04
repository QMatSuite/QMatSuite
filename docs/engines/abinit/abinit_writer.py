"""
ABINIT Input File Writer

This module provides utilities for generating ABINIT input files.

ABINIT input format:
- One variable per line: `varname value` or `varname value1 value2 ...`
- Comments start with `#`
- Case insensitive
- Arrays can span multiple lines
- Multi-dataset mode: varname1, varname2, etc. for dataset-specific values
- Multi-dataset common: just varname (applies to all datasets)

Key variables:
- Structure: acell, rprim, natom, ntypat, typat, znucl, xred/xcart
- Basis: ecut, ecutsm (for cell optimization)
- K-points: ngkpt, shiftk, nshiftk, kptopt (or explicit kpt, wtk)
- SCF: nstep, toldfe/tolvrs/tolwfr, iscf, diemac
- Relaxation: ionmov, optcell, ntime, tolmxf
- Multi-dataset: ndtset, jdtset, getden, getwfk

Reference: https://docs.abinit.org/variables/basic/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import textwrap


@dataclass
class AbinitStructure:
    """Crystal structure in ABINIT format."""

    acell: Tuple[float, float, float]  # Lattice scaling (Bohr)
    rprim: List[List[float]]  # 3x3 primitive vectors (dimensionless)
    natom: int
    ntypat: int
    typat: List[int]  # Atom type indices (1-based)
    znucl: List[float]  # Nuclear charges per type
    xred: Optional[List[List[float]]] = None  # Reduced coordinates
    xcart: Optional[List[List[float]]] = None  # Cartesian coordinates (Bohr)

    def to_input_string(self) -> str:
        """Generate ABINIT input string for structure."""
        lines = []

        # Cell
        lines.append(f"acell {self.acell[0]:14.8f} {self.acell[1]:14.8f} {self.acell[2]:14.8f}")
        lines.append("rprim")
        for row in self.rprim:
            lines.append(f"  {row[0]:14.10f} {row[1]:14.10f} {row[2]:14.10f}")

        # Atoms
        lines.append(f"natom {self.natom}")
        lines.append(f"ntypat {self.ntypat}")
        lines.append(f"typat {' '.join(str(t) for t in self.typat)}")
        lines.append(f"znucl {' '.join(f'{z:.5f}' for z in self.znucl)}")

        # Positions
        if self.xred is not None:
            lines.append("xred")
            for pos in self.xred:
                lines.append(f"  {pos[0]:14.10f} {pos[1]:14.10f} {pos[2]:14.10f}")
        elif self.xcart is not None:
            lines.append("xcart")
            for pos in self.xcart:
                lines.append(f"  {pos[0]:14.10f} {pos[1]:14.10f} {pos[2]:14.10f}")

        return "\n".join(lines)


@dataclass
class SCFParams:
    """SCF calculation parameters."""

    ecut: float  # Planewave cutoff (Hartree)
    ngkpt: Tuple[int, int, int] = (4, 4, 4)  # K-point grid
    shiftk: Optional[List[List[float]]] = None  # K-point shifts
    nstep: int = 50  # Max SCF iterations
    toldfe: Optional[float] = 1.0e-8  # Energy convergence (Ha)
    tolvrs: Optional[float] = None  # Potential residual convergence
    tolwfr: Optional[float] = None  # Wavefunction convergence
    diemac: float = 12.0  # Dielectric constant for mixing
    iscf: int = 7  # SCF algorithm (7=Pulay)
    nband: Optional[int] = None  # Number of bands
    occopt: int = 1  # Occupation scheme
    chksymbreak: int = 0  # Don't check symmetry breaking (safer)

    def to_input_string(self) -> str:
        """Generate ABINIT input string for SCF params."""
        lines = []

        lines.append(f"ecut {self.ecut}")
        lines.append(f"ngkpt {self.ngkpt[0]} {self.ngkpt[1]} {self.ngkpt[2]}")

        if self.shiftk is not None:
            lines.append(f"nshiftk {len(self.shiftk)}")
            lines.append("shiftk")
            for shift in self.shiftk:
                lines.append(f"  {shift[0]} {shift[1]} {shift[2]}")
        else:
            lines.append("nshiftk 1")
            lines.append("shiftk 0.0 0.0 0.0")

        lines.append(f"nstep {self.nstep}")
        lines.append(f"diemac {self.diemac}")
        lines.append(f"iscf {self.iscf}")
        lines.append(f"occopt {self.occopt}")
        lines.append(f"chksymbreak {self.chksymbreak}")

        # Convergence criterion (exactly one should be set)
        if self.toldfe is not None:
            lines.append(f"toldfe {self.toldfe:.1e}")
        elif self.tolvrs is not None:
            lines.append(f"tolvrs {self.tolvrs:.1e}")
        elif self.tolwfr is not None:
            lines.append(f"tolwfr {self.tolwfr:.1e}")

        if self.nband is not None:
            lines.append(f"nband {self.nband}")

        return "\n".join(lines)


@dataclass
class RelaxParams:
    """Structural relaxation parameters."""

    ionmov: int = 2  # BFGS by default
    optcell: int = 0  # 0=fixed cell, 1=volume, 2=full
    ntime: int = 50  # Max ionic steps
    tolmxf: float = 5.0e-5  # Force tolerance (Ha/Bohr)
    ecutsm: Optional[float] = None  # Smearing for cell optimization
    dilatmx: float = 1.05  # Max cell expansion
    toldff: Optional[float] = 5.0e-5  # Use force convergence

    def to_input_string(self) -> str:
        """Generate ABINIT input string for relaxation."""
        lines = []

        lines.append(f"ionmov {self.ionmov}")
        lines.append(f"optcell {self.optcell}")
        lines.append(f"ntime {self.ntime}")
        lines.append(f"tolmxf {self.tolmxf:.1e}")
        lines.append(f"dilatmx {self.dilatmx}")

        if self.ecutsm is not None:
            lines.append(f"ecutsm {self.ecutsm}")

        if self.toldff is not None:
            lines.append(f"toldff {self.toldff:.1e}")

        return "\n".join(lines)


@dataclass
class NSCFParams:
    """Non-self-consistent (bands/DOS) parameters."""

    iscf: int = -2  # NSCF flag
    nband: int = 8  # Number of bands
    tolwfr: float = 1.0e-12  # Wavefunction tolerance
    getden: Optional[int] = None  # Dataset to get density from

    # For band structure
    kptopt: Optional[int] = None  # -N for line mode
    kptbounds: Optional[List[List[float]]] = None  # High-symmetry points
    ndivk: Optional[List[int]] = None  # Divisions per segment

    def to_input_string(self, dataset_suffix: str = "") -> str:
        """Generate ABINIT input string for NSCF."""
        lines = []

        lines.append(f"iscf{dataset_suffix} {self.iscf}")
        lines.append(f"nband{dataset_suffix} {self.nband}")
        lines.append(f"tolwfr{dataset_suffix} {self.tolwfr:.1e}")

        if self.getden is not None:
            lines.append(f"getden{dataset_suffix} {self.getden}")

        if self.kptopt is not None and self.kptbounds is not None:
            lines.append(f"kptopt{dataset_suffix} {self.kptopt}")
            lines.append(f"ndivk{dataset_suffix} {' '.join(str(n) for n in self.ndivk)}")
            lines.append(f"kptbounds{dataset_suffix}")
            for kpt in self.kptbounds:
                lines.append(f"  {kpt[0]} {kpt[1]} {kpt[2]}")

        return "\n".join(lines)


def write_scf_input(
    structure: AbinitStructure,
    scf_params: SCFParams,
    pseudos: List[str],
    pp_dirpath: str,
    output_path: Path,
    comment: str = "ABINIT SCF calculation",
    extra_vars: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write an ABINIT SCF input file.

    Args:
        structure: Crystal structure
        scf_params: SCF parameters
        pseudos: List of pseudopotential filenames
        pp_dirpath: Path to pseudopotential directory
        output_path: Where to write the input file
        comment: Comment at top of file
        extra_vars: Additional variables to include
    """
    lines = [f"# {comment}", ""]

    # Structure
    lines.append("# Structure")
    lines.append(structure.to_input_string())
    lines.append("")

    # SCF parameters
    lines.append("# SCF parameters")
    lines.append(scf_params.to_input_string())
    lines.append("")

    # Output control
    lines.append("# Output control")
    lines.append("prtwf 0")
    lines.append("prtden 0")
    lines.append("")

    # Extra variables
    if extra_vars:
        lines.append("# Additional variables")
        for key, val in extra_vars.items():
            if isinstance(val, (list, tuple)):
                lines.append(f"{key} {' '.join(str(v) for v in val)}")
            else:
                lines.append(f"{key} {val}")
        lines.append("")

    # Pseudopotentials
    lines.append("# Pseudopotentials")
    lines.append(f'pp_dirpath "{pp_dirpath}"')
    lines.append(f'pseudos "{", ".join(pseudos)}"')

    output_path.write_text("\n".join(lines))


def write_relax_input(
    structure: AbinitStructure,
    scf_params: SCFParams,
    relax_params: RelaxParams,
    pseudos: List[str],
    pp_dirpath: str,
    output_path: Path,
    comment: str = "ABINIT relaxation calculation",
) -> None:
    """Write an ABINIT relaxation input file."""
    lines = [f"# {comment}", ""]

    # Structure
    lines.append("# Structure")
    lines.append(structure.to_input_string())
    lines.append("")

    # SCF parameters (modified for relax - use toldff instead of toldfe)
    lines.append("# SCF parameters")
    # Override convergence for relaxation
    modified_scf = SCFParams(
        ecut=scf_params.ecut,
        ngkpt=scf_params.ngkpt,
        shiftk=scf_params.shiftk,
        nstep=scf_params.nstep,
        toldfe=None,  # Don't use energy convergence for relax
        toldff=relax_params.toldff,  # Use force convergence
        diemac=scf_params.diemac,
        iscf=scf_params.iscf,
        nband=scf_params.nband,
        occopt=scf_params.occopt,
        chksymbreak=scf_params.chksymbreak,
    )
    # Write SCF params but substitute convergence
    for line in modified_scf.to_input_string().split("\n"):
        if not line.startswith("tol"):
            lines.append(line)
    lines.append("")

    # Relaxation parameters
    lines.append("# Relaxation parameters")
    lines.append(relax_params.to_input_string())
    lines.append("")

    # Output control
    lines.append("# Output control")
    lines.append("prtwf 0")
    lines.append("prtden 0")
    lines.append("")

    # Pseudopotentials
    lines.append("# Pseudopotentials")
    lines.append(f'pp_dirpath "{pp_dirpath}"')
    lines.append(f'pseudos "{", ".join(pseudos)}"')

    output_path.write_text("\n".join(lines))


def write_bands_input(
    structure: AbinitStructure,
    scf_params: SCFParams,
    nscf_params: NSCFParams,
    pseudos: List[str],
    pp_dirpath: str,
    output_path: Path,
    comment: str = "ABINIT SCF + bands calculation",
) -> None:
    """Write a multi-dataset SCF + NSCF bands input file."""
    lines = [f"# {comment}", ""]

    # Multi-dataset header
    lines.append("ndtset 2")
    lines.append("")

    # Common structure
    lines.append("# Structure (common)")
    lines.append(structure.to_input_string())
    lines.append("")

    # Common parameters
    lines.append("# Common parameters")
    lines.append(f"ecut {scf_params.ecut}")
    lines.append(f"diemac {scf_params.diemac}")
    lines.append(f"nstep {scf_params.nstep}")
    lines.append(f"chksymbreak {scf_params.chksymbreak}")
    lines.append("")

    # Dataset 1: SCF
    lines.append("# Dataset 1: SCF")
    lines.append(f"ngkpt1 {scf_params.ngkpt[0]} {scf_params.ngkpt[1]} {scf_params.ngkpt[2]}")
    lines.append("nshiftk1 1")
    lines.append("shiftk1 0.0 0.0 0.0")
    lines.append(f"toldfe1 {scf_params.toldfe:.1e}")
    lines.append("prtden1 1  # Write density for dataset 2")
    lines.append("")

    # Dataset 2: NSCF bands
    lines.append("# Dataset 2: NSCF bands")
    lines.append(nscf_params.to_input_string(dataset_suffix="2"))
    lines.append("")

    # Output control
    lines.append("# Output control")
    lines.append("prtwf 0")
    lines.append("")

    # Pseudopotentials
    lines.append("# Pseudopotentials")
    lines.append(f'pp_dirpath "{pp_dirpath}"')
    lines.append(f'pseudos "{", ".join(pseudos)}"')

    output_path.write_text("\n".join(lines))


# Convenience function for Si diamond structure
def create_si_diamond_structure(acell: float = 10.26311) -> AbinitStructure:
    """Create Si diamond structure."""
    return AbinitStructure(
        acell=(acell, acell, acell),
        rprim=[
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
            [0.5, 0.5, 0.0],
        ],
        natom=2,
        ntypat=1,
        typat=[1, 1],
        znucl=[14.0],
        xred=[
            [0.0, 0.0, 0.0],
            [0.25, 0.25, 0.25],
        ],
    )


if __name__ == "__main__":
    # Example usage
    si = create_si_diamond_structure()
    scf = SCFParams(ecut=10.0, ngkpt=(4, 4, 4))

    print("=== Si SCF Input ===")
    print(si.to_input_string())
    print()
    print(scf.to_input_string())
