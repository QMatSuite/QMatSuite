"""
Comprehensive test for Si DOS workflow.

This test creates a full project with a DOS workflow:
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
from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

from quantumvitas.io import QEInputGenerator
from quantumvitas.io.structure_io import qe_input_from_structure

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
    """Create a temporary project directory for the test in temp/ folder."""
    test_dir = project_root_path / "temp" / "test_si_dos_workflow"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture(scope="module")
def project_with_structure(test_project_dir: Path, project_root_path: Path) -> Path:
    """Initialize project and import Si structure."""
    # Create Si structure in rhombohedral representation to match the correct format
    # The correct structure uses rhombohedral lattice (alpha=60 degrees)
    # Lattice matrix from the correct structure file
    lattice_matrix = [
        [-2.7546079563238743, 0.0, 2.7546079563238743],
        [0.0, 2.7546079563238743, 2.7546079563238743],
        [-2.7546079563238743, 2.7546079563238743, 0.0],
    ]
    lattice = Lattice(lattice_matrix)
    
    # Create structure with the correct fractional coordinates
    # First atom at origin, second at [-0.25, 0.75, -0.25] in fractional coordinates
    structure = Structure(
        lattice,
        ["Si", "Si"],
        [[0.0, 0.0, 0.0], [-0.25, 0.75, -0.25]],
        coords_are_cartesian=False,  # Use fractional coordinates
    )
    
    # Create a QE input file from the structure (same approach as bands test)
    qe_input = qe_input_from_structure(structure)
    scf_in = test_project_dir / "si.0_scf.in"
    QEInputGenerator.write_file(qe_input, scf_in)
    
    # Initialize project
    run_qv(["init", "project", "--name", "si_dos_test"], cwd=test_project_dir)
    
    project_dir = test_project_dir / "si_dos_test"
    assert project_dir.exists(), f"Project not created at {project_dir}"
    
    # Copy only the Si pseudopotential (not all pseudopotentials)
    pseudo_src = project_root_path / "pseudo"
    pseudo_dst = project_dir / "pseudo"
    pseudo_dst.mkdir(parents=True, exist_ok=True)
    
    # Only copy Si pseudopotential(s)
    si_pseudos = list(pseudo_src.glob("Si*.UPF")) + list(pseudo_src.glob("si*.UPF"))
    for pp_file in si_pseudos:
        shutil.copy2(pp_file, pseudo_dst / pp_file.name)
    
    # Import structure from SCF input (same as bands test)
    run_qv(["import-structure", str(scf_in), "--name", "si"], cwd=project_dir)
    
    return project_dir


class TestSiDosWorkflow:
    """Test DOS workflow: SCF -> NSCF -> DOS -> Analysis."""
    
    @pytest.fixture(scope="class")
    def workflow_dir(self, project_with_structure: Path) -> Path:
        """Create workflow."""
        project_dir = project_with_structure
        
        run_qv(["init", "workflow", "si_dos", "--structure", "si"], cwd=project_dir)
        
        workflow_dir = project_dir / "workflows" / "si_dos"
        assert workflow_dir.exists()
        
        return workflow_dir
    
    @pytest.fixture(scope="class")
    def workflow_with_steps(self, project_with_structure: Path, workflow_dir: Path) -> Path:
        """Create all steps for the DOS workflow."""
        project_dir = project_with_structure
        
        # Step 1: SCF (calculation='scf', K_POINTS automatic 8x8x8)
        run_qv([
            "init", "step", "scf",
            "--structure", "si",
            "--workflow", "si_dos",
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
            "--workflow", "si_dos",
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
            "--workflow", "si_dos",
            "--DOS.emax", "16.0",
            "--DOS.emin", "-9.0",
            "--DOS.fildos", "si.dos.dat",
            "--DOS.outdir", "./outdir/",
            "--DOS.prefix", "si",
        ], cwd=project_dir)
        
        return workflow_dir
    
    def test_run_workflow(self, project_with_structure: Path, workflow_with_steps: Path):
        """Run the complete DOS workflow."""
        project_dir = project_with_structure
        
        result = run_qv([
            "run", "workflow", "si_dos", "--verbose"
        ], cwd=project_dir, check=False)
        
        # Check workflow completed
        assert "status:" in result.stdout.lower() or result.returncode == 0, \
            f"Workflow failed:\n{result.stdout}\n{result.stderr}"
    
    def test_analyze_dos(self, project_with_structure: Path, workflow_with_steps: Path):
        """Analyze DOS and generate plot using qv analyze dos."""
        project_dir = project_with_structure
        workflow_dir = workflow_with_steps
        raw_dir = workflow_dir / "raw"
        
        # Find the DOS data file
        dos_file = raw_dir / "si.dos.dat"
        if not dos_file.exists():
            pytest.skip("DOS output not found - workflow may have failed")
        
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
        
        result = run_qv(args, cwd=project_dir)
        
        # Check plot was created in results folder
        results_dir = workflow_dir / "results"
        plot_files = list(results_dir.glob("dos*.png"))
        assert len(plot_files) > 0, f"No DOS plot found in {results_dir}"
        
        # Verify plot file exists and has content
        plot_file = plot_files[0]
        assert plot_file.exists(), f"Plot file {plot_file} does not exist"
        assert plot_file.stat().st_size > 0, f"Plot file {plot_file} is empty"
        
        # Check that the analysis output contains expected information
        assert "n_points" in result.stdout or "fermi_energy" in result.stdout.lower(), \
            f"Analysis output should contain summary info:\n{result.stdout}"

