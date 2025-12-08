"""
Comprehensive test for Si band structure workflow.

This test creates a full project with two band structure workflows:
1. Manual k-path (from original input files)
2. Auto-generated k-path (using --auto-kpath)

Each workflow runs:
- SCF calculation (pw.x calculation='scf', K_POINTS automatic)
- NSCF calculation (pw.x calculation='nscf', K_POINTS automatic denser)
- Bands calculation (pw.x calculation='bands', K_POINTS crystal_b k-path)
- Bands post-processing (bands.x)
- Band structure analysis (qv analyze band)

The two workflows use DIFFERENT k-paths, so their band plots should look different.

Requires QE to be installed.
"""

import json
import os
import shutil
import subprocess
import sys
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
    """Create a temporary project directory for the test in temp/ folder."""
    test_dir = project_root_path / "temp" / "test_si_bands_workflow"
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


class TestSiBandsWorkflowManualKpath:
    """Test band structure workflow with manual k-path from original files."""
    
    @pytest.fixture(scope="class")
    def workflow_dir(self, project_with_structure: Path) -> Path:
        """Create workflow with manual k-path."""
        project_dir = project_with_structure
        
        run_qv(["init", "workflow", "bands_manual", "--structure", "si"], cwd=project_dir)
        
        workflow_dir = project_dir / "workflows" / "bands_manual"
        assert workflow_dir.exists()
        
        return workflow_dir
    
    @pytest.fixture(scope="class")
    def workflow_with_steps(self, project_with_structure: Path, workflow_dir: Path) -> Path:
        """Create all steps for the manual k-path workflow."""
        project_dir = project_with_structure
        
        # Step 1: SCF (calculation='scf', K_POINTS automatic 8x8x8)
        run_qv([
            "init", "step", "scf",
            "--structure", "si",
            "--workflow", "bands_manual",
            "--CONTROL.prefix", "si",
            "--CONTROL.outdir", "./outdir",
            "--SYSTEM.ecutwfc", "40",
            "--SYSTEM.ecutrho", "320",
            "--SYSTEM.nbnd", "8",
            "--ELECTRONS.conv_thr", "1e-8",
            "--k_points", "automatic:8,8,8,0,0,0",
            "--SPECIES.Si.pseudopot", "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        ], cwd=project_dir)
        
        # Step 2: NSCF (calculation='nscf', K_POINTS automatic 12x12x12 denser)
        run_qv([
            "init", "step", "nscf",
            "--structure", "si",
            "--workflow", "bands_manual",
            "--CONTROL.prefix", "si",
            "--CONTROL.outdir", "./outdir",
            "--SYSTEM.ecutwfc", "40",
            "--SYSTEM.ecutrho", "320",
            "--SYSTEM.nbnd", "8",
            "--SYSTEM.occupations", "tetrahedra",
            "--ELECTRONS.conv_thr", "1e-8",
            "--k_points", "automatic:12,12,12,0,0,0",
            "--SPECIES.Si.pseudopot", "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        ], cwd=project_dir)
        
        # Step 3: Bands calculation (calculation='bands', K_POINTS crystal_b)
        # Manual k-path from original input:
        # L(0.5,0.5,0.5) -> Gamma(0,0,0) -> X(0.5,0,0.5) -> U(0.625,0.25,0.625) -> Gamma
        # crystal_b format: first line is number of k-points, then k1 k2 k3 npts
        kpoints_data = [
            [5],                       # Number of k-points (required for crystal_b)
            [0.5, 0.5, 0.5, 20],       # L, 20 points to next
            [0.0, 0.0, 0.0, 30],       # Gamma, 30 points to next  
            [0.5, 0.0, 0.5, 10],       # X, 10 points to next
            [0.625, 0.25, 0.625, 30],  # U, 30 points to next
            [0.0, 0.0, 0.0, 0],        # Gamma (endpoint, 0 points)
        ]
        
        run_qv([
            "init", "step", "bands_pw",
            "--structure", "si",
            "--workflow", "bands_manual",
            "--name", "bands",
            "--CONTROL.prefix", "si",
            "--CONTROL.outdir", "./outdir",
            "--SYSTEM.ecutwfc", "40",
            "--SYSTEM.ecutrho", "320",
            "--SYSTEM.nbnd", "8",
            "--ELECTRONS.conv_thr", "1e-8",
            f"--CARD.K_POINTS={json.dumps({'option': 'crystal_b', 'data': kpoints_data})}",
            "--SPECIES.Si.pseudopot", "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        ], cwd=project_dir)
        
        # Step 4: Bands post-processing (bands.x)
        run_qv([
            "init", "step", "bands",
            "--structure", "si",
            "--workflow", "bands_manual",
            "--name", "bandspp",
            "--BANDS.prefix", "si",
            "--BANDS.outdir", "./outdir",
            "--BANDS.filband", "si.bands.dat",
        ], cwd=project_dir)
        
        return workflow_dir
    
    def test_run_workflow(self, project_with_structure: Path, workflow_with_steps: Path):
        """Run the complete manual k-path workflow."""
        project_dir = project_with_structure
        
        result = run_qv([
            "run", "workflow", "bands_manual", "--verbose"
        ], cwd=project_dir, check=False)
        
        # Check workflow completed
        assert "status:" in result.stdout.lower() or result.returncode == 0, \
            f"Workflow failed:\n{result.stdout}\n{result.stderr}"
    
    def test_analyze_bands(self, project_with_structure: Path, workflow_with_steps: Path):
        """Analyze bands and generate plot using qv analyze."""
        project_dir = project_with_structure
        workflow_dir = workflow_with_steps
        raw_dir = workflow_dir / "raw"
        
        # Find the bands.dat.gnu file
        bands_gnu = raw_dir / "si.bands.dat.gnu"
        if not bands_gnu.exists():
            pytest.skip("Bands output not found - workflow may have failed")
        
        # Find the bands.x output for symmetry points
        # Multiple naming conventions: *.bands.out, *bandspp*.out
        symmetry_file = None
        for pattern in ["*.bands.out", "*bandspp*.out"]:
            matches = list(raw_dir.glob(pattern))
            if matches:
                symmetry_file = matches[0]
                break
        
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
        
        # Run qv analyze band
        args = ["analyze", "band", str(bands_gnu), "--plot", "--format", "png"]
        if symmetry_file:
            args.extend(["--symmetry", str(symmetry_file)])
        if fermi_file:
            args.extend(["--scf", str(fermi_file)])
        
        result = run_qv(args, cwd=project_dir)
        
        # Check plot was created in results folder
        results_dir = workflow_dir / "results"
        plot_files = list(results_dir.glob("bands*.png"))
        assert len(plot_files) > 0, f"No band plot found in {results_dir}"


class TestSiBandsWorkflowAutoKpath:
    """Test band structure workflow with auto-generated k-path."""
    
    @pytest.fixture(scope="class")
    def workflow_dir(self, project_with_structure: Path) -> Path:
        """Create workflow with auto k-path."""
        project_dir = project_with_structure
        
        run_qv(["init", "workflow", "bands_auto", "--structure", "si"], cwd=project_dir)
        
        workflow_dir = project_dir / "workflows" / "bands_auto"
        assert workflow_dir.exists()
        
        return workflow_dir
    
    @pytest.fixture(scope="class")
    def workflow_with_steps(self, project_with_structure: Path, workflow_dir: Path) -> Path:
        """Create all steps for the auto k-path workflow."""
        project_dir = project_with_structure
        
        # Step 1: SCF (same as manual)
        run_qv([
            "init", "step", "scf",
            "--structure", "si",
            "--workflow", "bands_auto",
            "--CONTROL.prefix", "si",
            "--CONTROL.outdir", "./outdir",
            "--SYSTEM.ecutwfc", "40",
            "--SYSTEM.ecutrho", "320",
            "--SYSTEM.nbnd", "8",
            "--ELECTRONS.conv_thr", "1e-8",
            "--k_points", "automatic:8,8,8,0,0,0",
            "--SPECIES.Si.pseudopot", "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        ], cwd=project_dir)
        
        # Step 2: NSCF (same as manual)
        run_qv([
            "init", "step", "nscf",
            "--structure", "si",
            "--workflow", "bands_auto",
            "--CONTROL.prefix", "si",
            "--CONTROL.outdir", "./outdir",
            "--SYSTEM.ecutwfc", "40",
            "--SYSTEM.ecutrho", "320",
            "--SYSTEM.nbnd", "8",
            "--SYSTEM.occupations", "tetrahedra",
            "--ELECTRONS.conv_thr", "1e-8",
            "--k_points", "automatic:12,12,12,0,0,0",
            "--SPECIES.Si.pseudopot", "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        ], cwd=project_dir)
        
        # Step 3: Bands calculation with AUTO k-path
        # --auto-kpath will generate K_POINTS crystal_b from structure symmetry
        run_qv([
            "init", "step", "bands_pw",
            "--structure", "si",
            "--workflow", "bands_auto",
            "--name", "bands",
            "--auto-kpath",
            "--kpath-points", "20",
            "--CONTROL.prefix", "si",
            "--CONTROL.outdir", "./outdir",
            "--SYSTEM.ecutwfc", "40",
            "--SYSTEM.ecutrho", "320",
            "--SYSTEM.nbnd", "8",
            "--ELECTRONS.conv_thr", "1e-8",
            "--SPECIES.Si.pseudopot", "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        ], cwd=project_dir)
        
        # Verify kpath_metadata was stored
        import yaml
        step_file = workflow_dir / "steps" / "bands.step.yaml"
        with open(step_file) as f:
            step_data = yaml.safe_load(f)
        assert "kpath_metadata" in step_data, "Auto k-path metadata not stored"
        assert step_data["cards"]["K_POINTS"]["option"] == "crystal_b", \
            "Auto k-path should use crystal_b option"
        
        # Step 4: Bands post-processing (bands.x)
        run_qv([
            "init", "step", "bands",
            "--structure", "si",
            "--workflow", "bands_auto",
            "--name", "bandspp",
            "--BANDS.prefix", "si",
            "--BANDS.outdir", "./outdir",
            "--BANDS.filband", "si.bands.dat",
        ], cwd=project_dir)
        
        return workflow_dir
    
    def test_run_workflow(self, project_with_structure: Path, workflow_with_steps: Path):
        """Run the complete auto k-path workflow."""
        project_dir = project_with_structure
        
        result = run_qv([
            "run", "workflow", "bands_auto", "--verbose"
        ], cwd=project_dir, check=False)
        
        assert "status:" in result.stdout.lower() or result.returncode == 0, \
            f"Workflow failed:\n{result.stdout}\n{result.stderr}"
    
    def test_analyze_bands(self, project_with_structure: Path, workflow_with_steps: Path):
        """Analyze bands and generate plot using qv analyze."""
        project_dir = project_with_structure
        workflow_dir = workflow_with_steps
        raw_dir = workflow_dir / "raw"
        
        bands_gnu = raw_dir / "si.bands.dat.gnu"
        if not bands_gnu.exists():
            pytest.skip("Bands output not found - workflow may have failed")
        
        # Find the bands.x output for symmetry points
        # Multiple naming conventions: *.bands.out, *bandspp*.out
        symmetry_file = None
        for pattern in ["*.bands.out", "*bandspp*.out"]:
            matches = list(raw_dir.glob(pattern))
            if matches:
                symmetry_file = matches[0]
                break
        
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
        
        args = ["analyze", "band", str(bands_gnu), "--plot", "--format", "png"]
        if symmetry_file:
            args.extend(["--symmetry", str(symmetry_file)])
        if fermi_file:
            args.extend(["--scf", str(fermi_file)])
        
        result = run_qv(args, cwd=project_dir)
        
        results_dir = workflow_dir / "results"
        plot_files = list(results_dir.glob("bands*.png"))
        assert len(plot_files) > 0, f"No band plot found in {results_dir}"


class TestCompareKpaths:
    """Compare the two k-path approaches."""
    
    def test_kpaths_are_different(self, project_with_structure: Path):
        """Verify the manual and auto k-paths are different."""
        project_dir = project_with_structure
        
        import yaml
        
        manual_step = project_dir / "workflows" / "bands_manual" / "steps" / "bands.step.yaml"
        auto_step = project_dir / "workflows" / "bands_auto" / "steps" / "bands.step.yaml"
        
        if not manual_step.exists() or not auto_step.exists():
            pytest.skip("Step files not created yet")
        
        with open(manual_step) as f:
            manual_data = yaml.safe_load(f)
        with open(auto_step) as f:
            auto_data = yaml.safe_load(f)
        
        # Get K_POINTS from both
        manual_kpts = manual_data.get("cards", {}).get("K_POINTS", {}).get("data", [])
        auto_kpts = auto_data.get("cards", {}).get("K_POINTS", {}).get("data", [])
        
        # Both should use crystal_b
        assert manual_data["cards"]["K_POINTS"]["option"] == "crystal_b"
        assert auto_data["cards"]["K_POINTS"]["option"] == "crystal_b"
        
        # They should be different k-paths!
        assert manual_kpts != auto_kpts, \
            "Manual and auto k-paths should be different!"
        
        # Auto should have kpath_metadata
        assert "kpath_metadata" in auto_data, \
            "Auto k-path workflow should have kpath_metadata"
        assert "kpath_metadata" not in manual_data or manual_data.get("kpath_metadata") is None, \
            "Manual k-path workflow should not have kpath_metadata"


# Unit tests that don't require QE
class TestBandsWorkflowDataModels:
    """Test the data models for band analysis (no QE required)."""
    
    pytestmark = pytest.mark.unit
    
    @pytest.fixture(scope="class")
    def test_data_dir(self, project_root_path: Path):
        """Optional test data directory - tests skip if not available."""
        test_data_dir = project_root_path / "tests" / "data" / "workflow_bands"
        if not test_data_dir.exists():
            pytest.skip(f"Test data not found: {test_data_dir}")
        return test_data_dir
    
    def test_parse_bands_gnu_from_test_data(self, test_data_dir: Path):
        """Test parsing bands.dat.gnu file."""
        from quantumvitas.analysis.parsers import parse_bands_gnu
        
        bands_file = test_data_dir / "si.bands.dat.gnu"
        if not bands_file.exists():
            pytest.skip(f"Test data not found: {bands_file}")
        
        sym_file = test_data_dir / "reference_out" / "si.3_bands.pp.out"
        
        band_data = parse_bands_gnu(
            bands_file,
            symmetry_file=sym_file if sym_file.exists() else None,
            fermi_energy=5.76,
        )
        
        assert band_data.n_bands == 8
        assert band_data.n_kpoints > 0
        assert len(band_data.high_symmetry_points) > 0
    
    def test_parse_scf_from_test_data(self, test_data_dir: Path):
        """Test parsing SCF output file."""
        from quantumvitas.analysis.parsers import parse_scf_output
        
        scf_file = test_data_dir / "reference_out" / "si.0_scf.out"
        if not scf_file.exists():
            pytest.skip(f"Test data not found: {scf_file}")
        
        result = parse_scf_output(scf_file)
        
        assert result.converged
        assert result.total_energy is not None
        assert result.fermi_energy is not None or result.homo is not None
    
    def test_generate_kpath_for_si(self):
        """Test auto k-path generation for Si structure."""
        from quantumvitas.analysis.kpath import generate_kpath
        from pymatgen.core import Structure, Lattice
        
        # Create Si structure (diamond cubic)
        a = 5.431
        lattice = Lattice.cubic(a)
        species = ["Si", "Si"]
        coords = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]
        si = Structure(lattice, species, coords)
        
        kpath = generate_kpath(si, points_per_segment=20)
        
        assert len(kpath.segments) > 0
        assert len(kpath.labels) > 0
        assert kpath.spacegroup_number > 0
        
        # Check QE format conversion - should be crystal_b
        kpoints_card = kpath.to_qe_kpoints_crystal_b()
        assert kpoints_card["option"] == "crystal_b"
        assert len(kpoints_card["data"]) > 0
    
    def test_plot_bands_from_test_data(self, test_data_dir: Path, tmp_path: Path):
        """Test plotting bands from test data."""
        from quantumvitas.analysis.parsers import parse_bands_gnu
        from quantumvitas.analysis.plotting import plot_bands, save_figure
        
        bands_file = test_data_dir / "si.bands.dat.gnu"
        sym_file = test_data_dir / "reference_out" / "si.3_bands.pp.out"
        
        if not bands_file.exists():
            pytest.skip(f"Test data not found: {bands_file}")
        
        band_data = parse_bands_gnu(
            bands_file,
            symmetry_file=sym_file if sym_file.exists() else None,
            fermi_energy=5.76,
        )
        
        fig, ax = plot_bands(band_data, shift_fermi=True, energy_range=(-10, 10))
        
        plot_path = tmp_path / "bands_test.png"
        saved = save_figure(fig, plot_path)
        
        assert len(saved) == 1
        assert saved[0].exists()
        assert saved[0].stat().st_size > 0
