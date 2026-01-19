#!/usr/bin/env python3
"""Fake VASP executable for testing without real VASP binary.

This script generates minimal valid VASP output files for testing.
It can be used as a drop-in replacement for vasp_std by setting:
    export QMATS_VASP_STD_BIN=/path/to/tests/fixtures/fake_vasp.py

Usage:
    fake_vasp.py [working_dir]

If working_dir is not provided, uses current working directory.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional


def detect_step_type(working_dir: Path) -> str:
    """Detect VASP step type from INCAR."""
    incar_path = working_dir / "INCAR"
    if not incar_path.exists():
        return "scf"  # Default
    
    incar_content = incar_path.read_text()
    
    # Check for DOS calculation first (ISMEAR=-5 is specific to DOS)
    if "ISMEAR" in incar_content:
        # Extract ISMEAR value
        for line in incar_content.split("\n"):
            if "ISMEAR" in line and "=" in line:
                value_part = line.split("=")[1].strip().split()[0]
                if value_part == "-5":
                    return "dos"
    
    # Check for bands calculation (ICHARG=11)
    if "ICHARG" in incar_content:
        for line in incar_content.split("\n"):
            if "ICHARG" in line and "=" in line:
                value_part = line.split("=")[1].strip().split()[0]
                if value_part == "11":
                    return "bands"
    
    # Default to SCF
    return "scf"


def generate_oszicar_scf(working_dir: Path) -> str:
    """Generate minimal OSZICAR for SCF calculation."""
    return """       N       E                     dE             d eps       ncg     rms          rms(c)
DAV:   1    -0.100000000000E+02   -0.10000E+02   -0.10000E-02   100   0.100E+01
DAV:   2    -0.100100000000E+02   -0.10000E-01   -0.10000E-02   100   0.100E+00
   1 F= -.10010000E+02 E0= -.10010000E+02  d E =-.100100E-02
"""


def generate_outcar_scf(working_dir: Path) -> str:
    """Generate minimal OUTCAR for SCF calculation."""
    return """ vasp.6.5.0 16Dec24 (build Jan 18 2026 23:14:59) complex                         
 executed on             LinuxGNU date 2026.01.18  23:26:08
 running    1 mpi-ranks, on    1 nodes

--------------------------------------------------------------------------------------------------------

 FREE ENERGIE OF THE ION-ELECTRON SYSTEM (eV)
 ---------------------------------------------------
  free  energy   TOTEN  =       -10.010000 eV

  energy  without entropy=       -10.010000  energy(sigma->0) =       -10.010000

                  Total CPU time used (sec):        1.234
                            User time (sec):        1.000
                          System time (sec):        0.234
                         Elapsed time (sec):        1.234

 POSITION                                       TOTAL-FORCE (eV/Angst)
 -----------------------------------------------------------------------------------
      0.00000      0.00000      0.00000         0.000000     -0.000000     -0.000000
 -----------------------------------------------------------------------------------
    total drift:                               -0.000000     -0.000000      0.000000
"""


def generate_eigenval(working_dir: Path) -> str:
    """Generate minimal EIGENVAL for bands calculation."""
    return """    1    1    1
  1   1   1
    1
  0.0000000E+00  0.0000000E+00  0.0000000E+00  1.0000000E+00
   1      -5.0000
   2       0.0000
   3       2.5000
"""


def generate_doscar(working_dir: Path) -> str:
    """Generate minimal DOSCAR for DOS calculation."""
    return """  Si
   1   1   1
  10.0000  -10.0000  100  0.0000  1.0000
  -10.0000   0.0000   0.0000
   -5.0000   1.0000   0.5000
    0.0000   2.0000   1.0000
    5.0000   1.0000   0.5000
   10.0000   0.0000   0.0000
"""


def fake_vasp_scf(working_dir: Path) -> int:
    """Generate fake VASP SCF outputs."""
    # Write OSZICAR
    (working_dir / "OSZICAR").write_text(generate_oszicar_scf(working_dir))
    
    # Write OUTCAR
    (working_dir / "OUTCAR").write_text(generate_outcar_scf(working_dir))
    
    # Copy POSCAR to CONTCAR (no relaxation)
    poscar = working_dir / "POSCAR"
    if poscar.exists():
        (working_dir / "CONTCAR").write_text(poscar.read_text())
    
    # Create fake CHGCAR (for bands/dos workflow testing)
    (working_dir / "CHGCAR").write_text("FAKE CHGCAR for testing\n")
    
    # Create fake WAVECAR (optional, for wavefunction restart)
    (working_dir / "WAVECAR").write_text("FAKE WAVECAR for testing\n")
    
    return 0


def fake_vasp_bands(working_dir: Path) -> int:
    """Generate fake VASP bands outputs."""
    # Generate SCF outputs first
    fake_vasp_scf(working_dir)
    
    # Write EIGENVAL
    (working_dir / "EIGENVAL").write_text(generate_eigenval(working_dir))
    
    return 0


def fake_vasp_dos(working_dir: Path) -> int:
    """Generate fake VASP DOS outputs."""
    # Generate SCF outputs first
    fake_vasp_scf(working_dir)
    
    # Write DOSCAR
    (working_dir / "DOSCAR").write_text(generate_doscar(working_dir))
    
    return 0


def main() -> int:
    """Main entry point for fake VASP."""
    # Get working directory from command line or use current directory
    if len(sys.argv) > 1:
        working_dir = Path(sys.argv[1])
    else:
        working_dir = Path.cwd()
    
    working_dir = working_dir.resolve()
    
    if not working_dir.exists():
        print(f"Error: Working directory does not exist: {working_dir}", file=sys.stderr)
        return 1
    
    # Detect step type
    step_type = detect_step_type(working_dir)
    
    # Generate appropriate outputs
    if step_type == "bands":
        return fake_vasp_bands(working_dir)
    elif step_type == "dos":
        return fake_vasp_dos(working_dir)
    else:
        return fake_vasp_scf(working_dir)


if __name__ == "__main__":
    sys.exit(main())

