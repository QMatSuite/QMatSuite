"""
Test for Si band structure calculation with auto-generated k-path.

This test creates a project with an auto k-path band structure calculation:
- SCF calculation (pw.x calculation='scf', K_POINTS automatic)
- NSCF calculation (pw.x calculation='nscf', K_POINTS automatic denser)
- Bands calculation (pw.x calculation='bands', K_POINTS crystal_b auto-generated)
- Bands post-processing (bands.x)
- Band structure analysis (qv analyze band)

Requires QE to be installed and pymatgen for auto k-path generation.
"""

import os
import shutil
import subprocess
import sys
import yaml
from pathlib import Path

import pytest

# Check for pymatgen (required for auto k-path tests)
try:
    import pymatgen  # noqa: F401
    HAS_PYMATGEN = True
except ImportError:
    HAS_PYMATGEN = False

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
    """Create a temporary project directory for AUTO k-path calculation tests."""
    test_dir = project_root_path / ".tmp" / "test_si_bands_calculation_auto"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture(scope="module")
def project_with_structure(test_project_dir: Path, project_root_path: Path) -> Path:
    """Initialize project and import Si structure for AUTO calculation tests."""
    # Create QE input file in test_project_dir
    scf_in = test_project_dir / "si.0_scf.in"
    scf_in.write_text(QE_INPUT_CONTENT)
    
    # Initialize AUTO project
    run_qv(["init", "project", "--name", "si_bands_auto"], cwd=test_project_dir)
    
    project_dir = test_project_dir / "si_bands_auto"
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


@pytest.mark.skipif(not HAS_PYMATGEN, reason="pymatgen required for auto-kpath tests")
class TestSiBandsCalculationAutoKpath:
    """Test band structure calculation with auto-generated k-path."""
    
    @pytest.fixture(scope="class")
    def calculation_dir(self, project_with_structure: Path) -> Path:
        """Create calculation with auto k-path."""
        project_dir = project_with_structure
        
        run_qv(["init", "calculation", "bands_auto", "--structure", "si", "--engine-family", "qe"], cwd=project_dir)
        
        calculation_dir = project_dir / "calculations" / "bands_auto"
        assert calculation_dir.exists()
        
        return calculation_dir
    
    @pytest.fixture(scope="class")
    def calculation_with_steps(self, project_with_structure: Path, calculation_dir: Path) -> Path:
        """Create all steps for the auto k-path calculation."""
        project_dir = project_with_structure
        
        # Step 1: SCF (same as manual)
        run_qv([
            "init", "step", "scf",
            "--structure", "si",
            "--calculation", "bands_auto",
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
            "--calculation", "bands_auto",
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
            "init", "step", "bandspw",
            "--structure", "si",
            "--calculation", "bands_auto",
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
        step_file = calculation_dir / "steps" / "bands.step.yaml"
        with open(step_file) as f:
            step_data = yaml.safe_load(f)
        assert "kpath_metadata" in step_data, "Auto k-path metadata not stored"
        assert step_data["cards"]["K_POINTS"]["option"] == "crystal_b", \
            "Auto k-path should use crystal_b option"
        
        # Step 4: Bands post-processing (bands.x)
        run_qv([
            "init", "step", "bands",
            "--structure", "si",
            "--calculation", "bands_auto",
            "--name", "bandspp",
            "--BANDS.prefix", "si",
            "--BANDS.outdir", "./outdir",
            "--BANDS.filband", "si.bands.dat",
        ], cwd=project_dir)
        
        # Configure species_map using official CLI command (required for project runs)
        # The SCF input file was created in project_with_structure fixture at test_project_dir / "si.0_scf.in"
        # Since project_dir = test_project_dir / "si_bands_auto", the input is at project_dir.parent / "si.0_scf.in"
        scf_in = project_dir.parent / "si.0_scf.in"
        run_qv([
            "configure", "species", "--from-input", str(scf_in),
            "--calc", "bands_auto",
        ], cwd=project_dir)
        
        return calculation_dir
    
    def test_run_calculation_and_analyze_auto(
        self,
        project_with_structure: Path,
        calculation_with_steps: Path,
    ) -> None:
        """Run the complete auto k-path calculation and analyze bands (end-to-end test)."""
        project_dir = project_with_structure
        calculation_dir = calculation_with_steps
        raw_dir = calculation_dir / "raw"
        
        # Run the calculation once
        result = run_qv(
            ["run", "calculation", "bands_auto", "--verbose"],
            cwd=project_dir,
            check=False,
        )
        
        # Check if calculation completed successfully
        if result.returncode != 0 or "status:" not in result.stdout.lower():
            pytest.fail(
                "Auto k-path calculation failed:\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )
        
        # Verify the bands output exists; if not, fail with diagnostics
        bands_gnu = raw_dir / "si.bands.dat.gnu"
        if not bands_gnu.exists():
            # Try alternative naming patterns
            alternative_patterns = [
                "si.bands.dat.gnu",
                "*bands*.gnu",
                "*.bands.dat.gnu",
                "*.gnu",
            ]
            found_bands_file = None
            for pattern in alternative_patterns:
                matches = list(raw_dir.glob(pattern))
                # Filter to .gnu files (bands post-processing output)
                gnu_matches = [m for m in matches if m.suffix == ".gnu" or "gnu" in m.name]
                if gnu_matches:
                    found_bands_file = gnu_matches[0]
                    bands_gnu = found_bands_file
                    break
            
            if not bands_gnu.exists():
                raw_files = sorted(p.name for p in raw_dir.glob("*")) if raw_dir.exists() else []
                # Check if bands.x step ran but failed
                bands_in_files = list(raw_dir.glob("*bands*.in")) if raw_dir.exists() else []
                bands_out_files = list(raw_dir.glob("*bands*.out")) if raw_dir.exists() else []
                crash_files = sorted(p.name for p in raw_dir.glob("CRASH*")) if raw_dir.exists() else []
                error_msg = (
                    f"Bands output (.gnu file) not found after running auto k-path calculation.\n"
                    f"Expected: {raw_dir / 'si.bands.dat.gnu'}\n"
                    f"Files in raw/: {raw_files}\n"
                )
                if bands_in_files:
                    error_msg += f"Bands.x input files found: {[f.name for f in bands_in_files]}\n"
                if bands_out_files:
                    error_msg += f"Bands.x output files found: {[f.name for f in bands_out_files]}\n"
                if crash_files:
                    error_msg += f"CRASH files found (bands.x may have failed): {[f.name for f in crash_files]}\n"
                error_msg += "Calculation may have failed at bands.x step or output has different name."
                pytest.fail(error_msg)
        
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
                "qv analyze band failed for auto k-path:\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )
        
        # Verify plot was created in results folder
        results_dir = calculation_dir / "results"
        plot_files = list(results_dir.glob("bands*.png"))
        assert plot_files, f"No band plot found in {results_dir}"
    
    def test_auto_kpath_step_config(self, calculation_with_steps: Path):
        """Verify auto k-path step configuration (no QE execution)."""
        step_file = calculation_with_steps / "steps" / "bands.step.yaml"
        assert step_file.exists(), f"Step file not found: {step_file}"
        
        with open(step_file) as f:
            step_data = yaml.safe_load(f)
        
        # Verify K_POINTS configuration
        assert "cards" in step_data
        assert "K_POINTS" in step_data["cards"]
        kpoints = step_data["cards"]["K_POINTS"]
        
        assert kpoints["option"] == "crystal_b", \
            "Auto k-path should use crystal_b option"
        
        # Verify data format: normalized list of [kx, ky, kz, npts] (no count line)
        assert "data" in kpoints
        data = kpoints["data"]
        assert isinstance(data, list) and len(data) > 0, \
            "K_POINTS data should be a non-empty list"
        
        # Verify each row has 4 elements [kx, ky, kz, npts]
        for row in data:
            assert isinstance(row, list) and len(row) == 4, \
                f"Each K_POINTS row should be [kx, ky, kz, npts], got: {row}"
        
        # Verify kpath_metadata exists
        assert "kpath_metadata" in step_data, \
            "Auto k-path step should have kpath_metadata"
        kpath_meta = step_data["kpath_metadata"]
        assert "lattice_type" in kpath_meta
        assert "spacegroup_symbol" in kpath_meta
        assert "spacegroup_number" in kpath_meta
        assert "labels" in kpath_meta
        assert "segments" in kpath_meta
