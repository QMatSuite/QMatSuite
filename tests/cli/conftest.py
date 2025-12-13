"""Shared fixtures and helpers for CLI tests."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def run_qv(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run qv CLI command."""
    cmd = [sys.executable, "-m", "quantumvitas.cli.main"] + args
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, "MPLCONFIGDIR": "/tmp/mpl"},
    )
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result


@pytest.fixture(scope="module")
def test_project_dir(project_root_path: Path) -> Path:
    """Create a temporary project directory for the test in temp/ folder."""
    test_dir = project_root_path / "temp" / "test_si_bands_calculation"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture(scope="module")
def project_with_structure(test_project_dir: Path, project_root_path: Path) -> Path:
    """Initialize project and import Si structure."""
    # Create a QE input file inline (hardcoded in the test)
    # Based on the format from instructions: ibrav=2 (fcc), celldm(1), ATOMIC_POSITIONS (alat)
    qe_input_content = """&control
    calculation = 'scf'
    restart_mode = 'from_scratch'
    prefix = 'si'
    outdir = './outdir'
/
&system
    ibrav = 2
    celldm(1) = 10.410909236
    nat = 2
    ntyp = 1
    ecutwfc = 40
    ecutrho = 320
    nbnd = 8
/
&electrons
    conv_thr = 1e-8
/
ATOMIC_SPECIES
 Si  28.0855  Si.pbe-n-rrkjus_psl.1.0.0.UPF

ATOMIC_POSITIONS (alat)
 Si 0.00 0.00 0.00
 Si 0.25 0.25 0.25

K_POINTS (automatic)
  8 8 8 0 0 0
"""
    
    # Save the QE input file temporarily
    scf_in = test_project_dir / "si.0_scf.in"
    scf_in.write_text(qe_input_content)
    
    # Initialize project
    run_qv(["init", "project", "--name", "si_bands_test"], cwd=test_project_dir)
    
    project_dir = test_project_dir / "si_bands_test"
    assert project_dir.exists(), f"Project not created at {project_dir}"
    
    # Copy only the Si pseudopotential (not all pseudopotentials)
    pseudo_src = project_root_path / "pseudo"
    pseudo_dst = project_dir / "pseudo"
    pseudo_dst.mkdir(parents=True, exist_ok=True)
    
    # Only copy Si pseudopotential(s)
    si_pseudos = list(pseudo_src.glob("Si*.UPF")) + list(pseudo_src.glob("si*.UPF"))
    for pp_file in si_pseudos:
        shutil.copy2(pp_file, pseudo_dst / pp_file.name)
    
    # Import structure from SCF input
    run_qv(["import-structure", str(scf_in), "--name", "si"], cwd=project_dir)
    
    return project_dir
