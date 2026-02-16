"""
Test for Si band structure calculation with manual k-path.

This test creates a project with a manual k-path band structure calculation:
- SCF calculation (pw.x calculation='scf', K_POINTS automatic)
- NSCF calculation (pw.x calculation='nscf', K_POINTS automatic denser)
- Bands calculation (pw.x calculation='bands', K_POINTS crystal_b k-path)
- Bands post-processing (bands.x)
- Band structure analysis (qv analyze band)

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


# QE input content for Si structure (shared between fixtures)
QE_INPUT_CONTENT = """&control
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


@pytest.fixture(scope="module")
def test_project_dir(project_root_path: Path) -> Path:
    """Create a temporary project directory for MANUAL k-path calculation tests."""
    run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    test_dir = project_root_path / ".tmp" / "test_si_bands_calculation_manual" / run_id
    test_dir.mkdir(parents=True, exist_ok=False)
    return test_dir


@pytest.fixture(scope="module")
def project_with_structure(test_project_dir: Path, project_root_path: Path) -> Path:
    """Initialize project and import Si structure for MANUAL calculation tests."""
    # Create QE input file in test_project_dir
    scf_in = test_project_dir / "si.0_scf.in"
    scf_in.write_text(QE_INPUT_CONTENT)
    
    # Initialize MANUAL project
    run_qv(["init", "project", "--name", "si_bands_manual"], cwd=test_project_dir)
    
    project_dir = test_project_dir / "si_bands_manual"
    assert project_dir.exists(), f"Project not created at {project_dir}"
    
    # Copy only the Si pseudopotential (not all pseudopotentials)
    pseudo_src = project_root_path / "resources" / "pseudo"
    pseudo_dst = project_dir / "pseudo"
    pseudo_dst.mkdir(parents=True, exist_ok=True)
    
    # Only copy Si pseudopotential(s)
    si_pseudos = list(pseudo_src.glob("Si*.UPF")) + list(pseudo_src.glob("si*.UPF"))
    for pp_file in si_pseudos:
        shutil.copy2(pp_file, pseudo_dst / pp_file.name)
    
    # Import structure from SCF input
    run_qv(["import-structure", str(scf_in), "--name", "si"], cwd=project_dir)
    
    return project_dir


class TestSiBandsCalculationManualKpath:
    """Test band structure calculation with manual k-path from original files."""
    
    @pytest.fixture(scope="class")
    def calculation_dir(self, project_with_structure: Path) -> Path:
        """Create calculation with manual k-path."""
        project_dir = project_with_structure
        
        run_qv(["init", "calculation", "bands_manual", "--structure", "si", "--engine-family", "qe"], cwd=project_dir)
        
        calculation_dir = project_dir / "calculations" / "bands_manual"
        assert calculation_dir.exists()
        
        return calculation_dir
    
    @pytest.fixture(scope="class")
    def calculation_with_steps(self, project_with_structure: Path, calculation_dir: Path) -> Path:
        """Create all steps for the manual k-path calculation."""
        project_dir = project_with_structure
        
        # Step 1: SCF (calculation='scf', K_POINTS automatic 8x8x8)
        run_qv([
            "init", "step", "scf",
            "--structure", "si",
            "--calculation", "bands_manual",
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
            "--calculation", "bands_manual",
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
        # crystal_b format: list of [kx, ky, kz, npts] segments; generator adds count line
        kpoints_data = [
            [0.5, 0.5, 0.5, 20],       # L, 20 points to next
            [0.0, 0.0, 0.0, 30],       # Gamma, 30 points to next  
            [0.5, 0.0, 0.5, 10],       # X, 10 points to next
            [0.625, 0.25, 0.625, 30],  # U, 30 points to next
            [0.0, 0.0, 0.0, 0],        # Gamma (endpoint, 0 points)
        ]
        
        run_qv([
            "init", "step", "bandspw",
            "--structure", "si",
            "--calculation", "bands_manual",
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
            "--calculation", "bands_manual",
            "--name", "bandspp",
            "--BANDS.prefix", "si",
            "--BANDS.outdir", "./outdir",
            "--BANDS.filband", "si.bands.dat",
        ], cwd=project_dir)
        
        # Configure species_map using official CLI command (required for project runs)
        # The SCF input file was created in project_with_structure fixture at test_project_dir / "si.0_scf.in"
        # Since project_dir = test_project_dir / "si_bands_manual", the input is at project_dir.parent / "si.0_scf.in"
        scf_in = project_dir.parent / "si.0_scf.in"
        run_qv([
            "configure", "species", "--from-input", str(scf_in),
            "--calc", "bands_manual",
        ], cwd=project_dir)
        
        return calculation_dir
    
    def test_run_calculation_and_analyze(
        self,
        project_with_structure: Path,
        calculation_with_steps: Path,
    ) -> None:
        """Run the complete manual k-path calculation and analyze bands (end-to-end test)."""
        project_dir = project_with_structure
        calculation_dir = calculation_with_steps
        raw_dir = calculation_dir / "raw"
        
        # Run the calculation once
        result = run_qv(
            ["run", "calculation", "bands_manual", "--verbose"],
            cwd=project_dir,
            check=False,
        )
        
        # Check if calculation completed successfully
        if result.returncode != 0 or "status:" not in result.stdout.lower():
            pytest.fail(
                "Manual k-path calculation failed:\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )
        
        # Verify the bands output exists; if not, fail with diagnostics
        bands_gnu = raw_dir / "si.bands.dat.gnu"
        if not bands_gnu.exists():
            raw_files = sorted(p.name for p in raw_dir.glob("*")) if raw_dir.exists() else []
            crash_files = sorted(p.name for p in raw_dir.glob("CRASH*")) if raw_dir.exists() else []
            pytest.fail(
                "Bands output not found after running manual k-path calculation:\n"
                f"Expected: {bands_gnu}\n"
                f"Files in raw/: {raw_files}\n"
                f"CRASH files: {crash_files}"
            )
        
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
        
        result = run_qv(args, cwd=project_dir, check=False)
        
        # Check if analyze command failed
        if result.returncode != 0:
            pytest.fail(
                "qv analyze band failed for manual k-path:\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )
        
        # Verify plot was created in results folder
        results_dir = calculation_dir / "results"
        plot_files = list(results_dir.glob("bands*.png"))
        assert plot_files, f"No band plot found in {results_dir}"


# Unit tests that don't require QE
class TestBandsCalculationDataModels:
    """Test the data models for band analysis (no QE required)."""
    
    pytestmark = pytest.mark.unit
    
    @pytest.fixture(scope="class")
    def test_data_dir(self, project_root_path: Path):
        """Optional test data directory - tests skip if not available."""
        test_data_dir = project_root_path / "tests" / "data" / "calculation_bands"
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
