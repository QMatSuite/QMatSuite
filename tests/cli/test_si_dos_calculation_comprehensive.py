"""
Comprehensive test for Si DOS calculation.

This test creates a full project with a DOS calculation:
- SCF calculation (pw.x calculation='scf', K_POINTS automatic)
- NSCF calculation (pw.x calculation='nscf', K_POINTS automatic denser)
- DOS calculation (dos.x)
- DOS analysis (qv analyze dos)

Requires QE to be installed.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

# Mark all tests as requiring QE
pytestmark = pytest.mark.qe_core


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
    """Create a temporary project directory for the test in .tmp/ folder."""
    run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    test_dir = project_root_path / ".tmp" / "test_si_dos_calculation" / run_id
    test_dir.mkdir(parents=True, exist_ok=False)
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
    ecutwfc = 50
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
    run_qv(["init", "project", "--name", "si_dos_test"], cwd=test_project_dir)
    
    project_dir = test_project_dir / "si_dos_test"
    assert project_dir.exists(), f"Project not created at {project_dir}"
    
    # Copy only the Si pseudopotential (not all pseudopotentials)
    pseudo_src = project_root_path / "resources" / "pseudo"
    pseudo_dst = project_dir / "pseudo"
    pseudo_dst.mkdir(parents=True, exist_ok=True)
    
    # Only copy Si pseudopotential(s)
    si_pseudos = list(pseudo_src.glob("Si*.UPF")) + list(pseudo_src.glob("si*.UPF"))
    for pp_file in si_pseudos:
        shutil.copy2(pp_file, pseudo_dst / pp_file.name)
    
    # Import structure from SCF input (same as bands test)
    run_qv(["import-structure", str(scf_in), "--name", "si"], cwd=project_dir)
    
    return project_dir


class TestSiDosCalculation:
    """Test DOS calculation: SCF -> NSCF -> DOS -> Analysis."""
    
    @pytest.fixture(scope="class")
    def calculation_dir(self, project_with_structure: Path) -> Path:
        """Create calculation."""
        project_dir = project_with_structure
        
        run_qv(["init", "calculation", "si_dos", "--structure", "si", "--engine-family", "qe"], cwd=project_dir)
        
        calculation_dir = project_dir / "calculations" / "si_dos"
        assert calculation_dir.exists()
        
        return calculation_dir
    
    @pytest.fixture(scope="class")
    def calculation_with_steps(self, project_with_structure: Path, calculation_dir: Path) -> Path:
        """Create all steps for the DOS calculation."""
        project_dir = project_with_structure
        
        # Step 1: SCF (calculation='scf', K_POINTS automatic 8x8x8)
        run_qv([
            "init", "step", "scf",
            "--structure", "si",
            "--calculation", "si_dos",
            "--CONTROL.calculation", "scf",
            "--CONTROL.outdir", "./outdir",
            "--CONTROL.prefix", "si",
            "--CONTROL.restart_mode", "from_scratch",
            "--ELECTRONS.conv_thr", "1e-08",
            "--SYSTEM.ecutwfc", "50",
            f'--CARD.K_POINTS={json.dumps({"option": "automatic", "data": [["8", "8", "8", "0", "0", "0"]]})}',
            "--SPECIES.Si.mass", "28.0855",
            "--SPECIES.Si.pseudopot", "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        ], cwd=project_dir)
        
        # Step 2: NSCF (calculation='nscf', K_POINTS automatic 12x12x12 denser)
        run_qv([
            "init", "step", "nscf",
            "--structure", "si",
            "--calculation", "si_dos",
            "--CONTROL.calculation", "nscf",
            "--CONTROL.outdir", "./outdir",
            "--CONTROL.prefix", "si",
            "--CONTROL.restart_mode", "from_scratch",
            "--ELECTRONS.conv_thr", "1e-08",
            "--SYSTEM.ecutwfc", "50",
            "--SYSTEM.occupations", "tetrahedra",
            f'--CARD.K_POINTS={json.dumps({"option": "automatic", "data": [["12", "12", "12", "0", "0", "0"]]})}',
            "--SPECIES.Si.mass", "28.0855",
            "--SPECIES.Si.pseudopot", "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        ], cwd=project_dir)
        
        # Step 3: DOS calculation (dos.x)
        run_qv([
            "init", "step", "dos",
            "--structure", "si",
            "--calculation", "si_dos",
            "--DOS.emax", "16.0",
            "--DOS.emin", "-9.0",
            "--DOS.fildos", "si.dos.dat",
            "--DOS.outdir", "./outdir/",
            "--DOS.prefix", "si",
        ], cwd=project_dir)
        
        # Configure species_map using official CLI command (required for project runs)
        # Use the SCF input file created in project_with_structure fixture
        scf_in = project_dir.parent.parent / "si.0_scf.in"  # test_project_dir / si.0_scf.in
        if not scf_in.exists():
            # Fallback: create input file in project root if not in expected location
            scf_in = project_dir.parent / "si.0_scf.in"
        run_qv([
            "configure", "species", "--from-input", str(scf_in),
            "--calc", "si_dos",
        ], cwd=project_dir)
        
        return calculation_dir
    
    def test_run_calculation_and_analyze(
        self,
        project_with_structure: Path,
        calculation_with_steps: Path,
    ) -> None:
        """Run the complete DOS calculation and analyze DOS (end-to-end test)."""
        project_dir = project_with_structure
        calculation_dir = calculation_with_steps
        raw_dir = calculation_dir / "raw"
        
        # Run the calculation once
        result = run_qv(
            ["run", "calculation", "si_dos", "--verbose"],
            cwd=project_dir,
            check=False,
        )
        
        # Check if calculation completed successfully
        if result.returncode != 0 or "status:" not in result.stdout.lower():
            pytest.fail(
                "DOS calculation failed:\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )
        
        # Verify the DOS output exists; if not, fail with diagnostics
        dos_file = raw_dir / "si.dos.dat"
        if not dos_file.exists():
            raw_files = sorted(p.name for p in raw_dir.glob("*")) if raw_dir.exists() else []
            crash_files = sorted(p.name for p in raw_dir.glob("CRASH*")) if raw_dir.exists() else []
            pytest.fail(
                "DOS output not found after running calculation:\n"
                f"Expected: {dos_file}\n"
                f"Files in raw/: {raw_files}\n"
                f"CRASH files: {crash_files}"
            )
        
        # Find NSCF output for Fermi energy (preferred over SCF for accuracy)
        fermi_file = None
        nscf_out = list(raw_dir.glob("*nscf*.out"))
        if nscf_out:
            fermi_file = nscf_out[0]
        else:
            # Fall back to SCF output
            scf_out = list(raw_dir.glob("*scf*.out"))
            if scf_out:
                fermi_file = scf_out[0]
        
        # Run qv analyze dos
        args = ["analyze", "dos", str(dos_file), "--plot", "--format", "png"]
        if fermi_file:
            args.extend(["--scf", str(fermi_file)])
        
        result = run_qv(args, cwd=project_dir, check=False)
        
        # Check if analyze command failed
        if result.returncode != 0:
            pytest.fail(
                "qv analyze dos failed:\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )
        
        # Check plot was created in results folder
        results_dir = calculation_dir / "results"
        plot_files = list(results_dir.glob("dos*.png"))
        assert len(plot_files) > 0, f"No DOS plot found in {results_dir}"
        
        # Verify plot file exists and has content
        plot_file = plot_files[0]
        assert plot_file.exists(), f"Plot file {plot_file} does not exist"
        assert plot_file.stat().st_size > 0, f"Plot file {plot_file} is empty"
        
        # Check that the analysis output contains expected information
        assert (
            "n_points" in result.stdout
            or "fermi_energy" in result.stdout.lower()
        ), f"Analysis output should contain summary info:\n{result.stdout}"
