"""Real VASP integration tests.

These tests require:
- Real VASP binary at ./.qmatsuite/engines/vasp/vasp.6.5.0/bin/vasp_std
- Real POTCAR at ./.qmatsuite/engines/vasp/potpaw_PBE.64/

CI behavior: SKIP (CI=true)
Local behavior: FAIL with actionable error if resources missing
"""

import os
import pytest
from pathlib import Path


def is_ci() -> bool:
    """Check if running in CI environment."""
    return os.environ.get("CI", "").lower() in ("true", "1", "yes")


def check_real_vasp() -> tuple[bool, str]:
    """Check for real VASP binary. Returns (available, message)."""
    import subprocess
    try:
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        bin_path = resolve_vasp_bin("std")
        if not bin_path.exists():
            return False, f"VASP binary does not exist: {bin_path}"
        # Verify it's the real binary, not fake_vasp.py
        if bin_path.suffix == ".py":
            return False, f"Found fake_vasp.py, not real binary: {bin_path}"
        # Verify the binary is actually runnable (check dynamic libraries)
        try:
            # Running VASP with no input files will fail, but it should at least load
            # If dynamic libraries are missing, this will fail with non-zero exit
            result = subprocess.run(
                [str(bin_path)],
                capture_output=True,
                text=True,
                timeout=5,
                cwd="/tmp",  # Use /tmp to avoid creating files in current dir
            )
            # Check for dyld/dynamic linker errors in stderr
            if "Library not loaded" in result.stderr or "dyld" in result.stderr:
                return False, f"VASP binary has missing dynamic libraries: {result.stderr[:200]}"
        except subprocess.TimeoutExpired:
            # Timeout is OK - means VASP started (waiting for input)
            pass
        except OSError as e:
            return False, f"VASP binary not executable: {e}"
        return True, f"Found VASP at: {bin_path}"
    except RuntimeError as e:
        return False, str(e)


def check_real_potcar() -> tuple[bool, str]:
    """Check for real POTCAR directory. Returns (available, message)."""
    try:
        from quantumvitas.core.engines.vasp_resolver import get_potcar_dir
        potcar_dir = get_potcar_dir("PBE")
        si_potcar = potcar_dir / "Si" / "POTCAR"
        if not si_potcar.exists():
            return False, f"Si POTCAR does not exist: {si_potcar}"
        # Verify it's a real POTCAR (>1KB)
        size = si_potcar.stat().st_size
        if size < 1000:
            return False, f"Si POTCAR too small ({size} bytes), likely fake"
        return True, f"Found POTCAR at: {potcar_dir}"
    except RuntimeError as e:
        return False, str(e)


@pytest.fixture(scope="module")
def real_vasp_required():
    """Fixture: skip if VASP not available or not runnable."""
    if is_ci():
        pytest.skip("Real VASP tests skipped in CI environment")

    vasp_ok, vasp_msg = check_real_vasp()
    potcar_ok, potcar_msg = check_real_potcar()

    if not vasp_ok:
        # Skip (not fail) - VASP may have broken dependencies or not be installed
        pytest.skip(
            f"Real VASP binary not available: {vasp_msg}\n"
            f"To enable these tests:\n"
            f"  1. Install VASP at .qmatsuite/engines/vasp/vasp.X.X.X/bin/vasp_std, OR\n"
            f"  2. Set QMATS_VASP_STD_BIN environment variable\n"
            f"  3. Ensure all dynamic libraries are available (check brew/conda)"
        )

    if not potcar_ok:
        pytest.skip(
            f"Real POTCAR directory not available: {potcar_msg}\n"
            f"To enable these tests:\n"
            f"  Install VASP POTCARs at .qmatsuite/engines/vasp/potpaw_PBE.64/"
        )

    return {"vasp_msg": vasp_msg, "potcar_msg": potcar_msg}


pytestmark = [pytest.mark.integration, pytest.mark.vasp_real]


class TestRealVASPSmoke:
    """Smoke tests with real VASP binary.
    
    These tests verify that real VASP runs correctly and produces expected outputs.
    They are NOT run in CI (skipped when CI=true).
    """
    
    def test_real_vasp_available(self, real_vasp_required):
        """Verify real VASP is available (meta-test)."""
        assert real_vasp_required is not None
        print(f"VASP: {real_vasp_required['vasp_msg']}")
        print(f"POTCAR: {real_vasp_required['potcar_msg']}")
    
    def test_scf_smoke(self, real_vasp_required):
        """Run real SCF and verify basic outputs."""
        from pymatgen.core import Structure, Lattice
        from quantumvitas.engine.vasp_writer import write_poscar, write_incar, write_kpoints, write_potcar
        from quantumvitas.engine.vasp_parser import parse_oszicar
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        from quantumvitas.core.paths import get_qmatsuite_tmp_root
        import subprocess
        
        # Create minimal Si structure
        lattice = Lattice.cubic(5.43)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        # Setup working directory in .tmp (per user requirement)
        tmp_root = get_qmatsuite_tmp_root()
        work_dir = tmp_root / "vasp_real_smoke" / "scf"
        work_dir.mkdir(parents=True, exist_ok=True)
        
        # Write input files
        write_poscar(structure, work_dir / "POSCAR")
        write_incar({
            "SYSTEM": "Si2_SCF_smoke",
            "ENCUT": 300,
            "ISMEAR": 0,
            "SIGMA": 0.05,
            "IBRION": -1,
            "NSW": 0,
            "LWAVE": True,
            "LCHARG": True,
        }, work_dir / "INCAR")
        write_kpoints({"mode": "automatic", "mesh": [4, 4, 4], "shift": [0, 0, 0]}, work_dir / "KPOINTS")
        write_potcar(structure, {"Si": {}}, work_dir / "POTCAR", "PBE")
        
        # Run VASP
        vasp_bin = resolve_vasp_bin("std")
        result = subprocess.run(
            [str(vasp_bin)],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )
        
        # Verify outputs exist
        assert (work_dir / "OUTCAR").exists(), "OUTCAR not created"
        assert (work_dir / "OSZICAR").exists(), "OSZICAR not created"
        assert (work_dir / "CHGCAR").exists(), "CHGCAR not created"
        
        # Parse energy
        oszicar_data = parse_oszicar(work_dir / "OSZICAR")
        assert oszicar_data is not None, "Failed to parse OSZICAR"
        assert oszicar_data.get("final_energy") is not None, "No energy in parsed OSZICAR"
        
        # Print for evidence collection
        print(f"SCF Energy: {oszicar_data['final_energy']} eV")
        print(f"Exit code: {result.returncode}")
    
    def test_bands_smoke(self, real_vasp_required):
        """Run real Bands and verify EIGENVAL."""
        from pymatgen.core import Structure, Lattice
        from quantumvitas.engine.vasp_writer import write_poscar, write_incar, write_kpoints, write_potcar
        from quantumvitas.engine.vasp_parser import parse_eigenval
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        from quantumvitas.core.paths import get_qmatsuite_tmp_root
        import subprocess
        import shutil
        
        # Create minimal Si structure
        lattice = Lattice.cubic(5.43)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        tmp_root = get_qmatsuite_tmp_root()
        scf_dir = tmp_root / "vasp_real_smoke" / "scf"
        bands_dir = tmp_root / "vasp_real_smoke" / "bands"
        bands_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy CHGCAR from SCF (prerequisite)
        if not (scf_dir / "CHGCAR").exists():
            pytest.skip("SCF CHGCAR not found. Run test_scf_smoke first.")
        
        shutil.copy2(scf_dir / "CHGCAR", bands_dir / "CHGCAR")
        
        # Write input files
        write_poscar(structure, bands_dir / "POSCAR")
        write_incar({
            "SYSTEM": "Si2_bands_smoke",
            "ENCUT": 300,
            "ISMEAR": 0,
            "SIGMA": 0.05,
            "IBRION": -1,
            "NSW": 0,
            "ICHARG": 11,  # Read CHGCAR
            "LWAVE": False,
            "LCHARG": False,
            "LORBIT": 11,
        }, bands_dir / "INCAR")
        write_kpoints({
            "mode": "line",
            "path": [
                [[0.0, 0.0, 0.0], [0.5, 0.0, 0.5]],  # G to X
                [[0.5, 0.0, 0.5], [0.5, 0.25, 0.75]],  # X to W
            ],
            "npoints": 20,
        }, bands_dir / "KPOINTS")
        write_potcar(structure, {"Si": {}}, bands_dir / "POTCAR", "PBE")
        
        # Run VASP
        vasp_bin = resolve_vasp_bin("std")
        result = subprocess.run(
            [str(vasp_bin)],
            cwd=bands_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        # Verify outputs exist
        assert (bands_dir / "OUTCAR").exists(), "OUTCAR not created"
        assert (bands_dir / "EIGENVAL").exists(), "EIGENVAL not created"
        
        # Parse EIGENVAL
        eigenval_data = parse_eigenval(bands_dir / "EIGENVAL")
        assert eigenval_data is not None, "Failed to parse EIGENVAL"
        assert eigenval_data.get("n_kpoints", 0) > 0, "No k-points in parsed EIGENVAL"
        assert eigenval_data.get("n_bands", 0) > 0, "No bands in parsed EIGENVAL"
        
        print(f"Bands: {eigenval_data['n_kpoints']} k-points, {eigenval_data['n_bands']} bands")
        print(f"Exit code: {result.returncode}")
    
    def test_dos_smoke(self, real_vasp_required):
        """Run real DOS and verify DOSCAR."""
        from pymatgen.core import Structure, Lattice
        from quantumvitas.engine.vasp_writer import write_poscar, write_incar, write_kpoints, write_potcar
        from quantumvitas.engine.vasp_parser import parse_doscar
        from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
        from quantumvitas.core.paths import get_qmatsuite_tmp_root
        import subprocess
        import shutil
        
        # Create minimal Si structure
        lattice = Lattice.cubic(5.43)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        tmp_root = get_qmatsuite_tmp_root()
        scf_dir = tmp_root / "vasp_real_smoke" / "scf"
        dos_dir = tmp_root / "vasp_real_smoke" / "dos"
        dos_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy CHGCAR from SCF (prerequisite)
        if not (scf_dir / "CHGCAR").exists():
            pytest.skip("SCF CHGCAR not found. Run test_scf_smoke first.")
        
        shutil.copy2(scf_dir / "CHGCAR", dos_dir / "CHGCAR")
        
        # Write input files
        write_poscar(structure, dos_dir / "POSCAR")
        write_incar({
            "SYSTEM": "Si2_dos_smoke",
            "ENCUT": 300,
            "ISMEAR": -5,  # Tetrahedron method
            "SIGMA": 0.05,
            "IBRION": -1,
            "NSW": 0,
            "ICHARG": 11,  # Read CHGCAR
            "LWAVE": False,
            "LCHARG": False,
            "LORBIT": 11,
            "NEDOS": 3001,
        }, dos_dir / "INCAR")
        write_kpoints({"mode": "automatic", "mesh": [8, 8, 8], "shift": [0, 0, 0]}, dos_dir / "KPOINTS")
        write_potcar(structure, {"Si": {}}, dos_dir / "POTCAR", "PBE")
        
        # Run VASP
        vasp_bin = resolve_vasp_bin("std")
        result = subprocess.run(
            [str(vasp_bin)],
            cwd=dos_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        # Verify outputs exist
        assert (dos_dir / "OUTCAR").exists(), "OUTCAR not created"
        assert (dos_dir / "DOSCAR").exists(), "DOSCAR not created"
        
        # Parse DOSCAR
        doscar_data = parse_doscar(dos_dir / "DOSCAR")
        assert doscar_data is not None, "Failed to parse DOSCAR"
        assert doscar_data.get("n_dos_points", 0) > 0, "No DOS points in parsed DOSCAR"
        assert doscar_data.get("efermi") is not None, "No Fermi energy in parsed DOSCAR"
        
        print(f"DOS: {doscar_data['n_dos_points']} points, E_fermi = {doscar_data['efermi']} eV")
        print(f"Exit code: {result.returncode}")

