"""Integration tests for VASP runner with fake_vasp.

These tests verify VASP execution flow using fake_vasp, covering:
- SCF calculation
- Bands calculation (with CHGCAR from SCF)
- DOS calculation (with CHGCAR from SCF)
- Prerequisite checking (bands fails if SCF not done)

Run with:
    pytest tests/integration/vasp/test_vasp_runner.py -v

These tests use fake_vasp and do not require real VASP binary.
"""

import pytest
from pathlib import Path
from typing import Dict, Any

from quantumvitas.engine.vasp_engine import VaspEngine
from quantumvitas.engine.vasp_parser import parse_vasp_output
from quantumvitas.execution.reference_resolver import find_reference_scf
from quantumvitas.execution.vasp_staging import stage_chgcar, MissingPrerequisiteError
from quantumvitas.calculation.manifest import Manifest, ManifestStepEntry


class MockStep:
    """Mock step for testing."""
    def __init__(self, step_id: str, step_type_spec: str, step_type_gen: str, parameters: Dict[str, Any] = None):
        self.id = step_id
        self.step_type_spec = step_type_spec
        self.step_type_gen = step_type_gen
        self.parameters = parameters or {}
        self.options = {}
        # Create mock meta object
        self.meta = type('Meta', (), {"ulid": step_id})()


class MockCalculation:
    """Mock calculation for testing."""
    def __init__(self, project_root: Path, structure_ulid: str = "test_structure"):
        self.project = MockProject(project_root)
        self.structure_ulid = structure_ulid
        self.species_map = {"Si": {"pseudopot": "Si.UPF"}}


class MockProject:
    """Mock project for testing."""
    def __init__(self, root: Path):
        self.root = root
    
    def get_structure(self, structure_ulid: str):
        """Return mock structure reference."""
        return MockStructureRef(self.root / "structures" / f"{structure_ulid}.yaml")


class MockStructureRef:
    """Mock structure reference."""
    def __init__(self, path: Path):
        self.path = path
    
    def resolve_path(self, project_root: Path) -> Path:
        """Resolve structure path."""
        if self.path.is_absolute():
            return self.path
        return project_root / self.path


@pytest.mark.integration
class TestVASPRunner:
    """Integration tests for VASP runner."""
    
    def test_scf_with_fake_vasp(self, vasp_engine, use_fake_vasp, tmp_path):
        """Test SCF calculation with fake_vasp succeeds."""
        working_dir = tmp_path / "scf"
        working_dir.mkdir()
        
        # Create minimal input files
        (working_dir / "POSCAR").write_text("""Si2
1.0
3.867 0.000 0.000
1.934 3.349 0.000
1.934 1.116 3.157
Si
2
Direct
0.0 0.0 0.0
0.25 0.25 0.25
""")
        
        (working_dir / "INCAR").write_text("""SYSTEM = Si2_SCF_test
ENCUT = 300
PREC = Normal
ISMEAR = 0
SIGMA = 0.05
IBRION = -1
NSW = 0
""")
        
        (working_dir / "KPOINTS").write_text("""Automatic
0
Gamma
4 4 4
0 0 0
""")
        
        (working_dir / "POTCAR").write_text("FAKE POTCAR\n")
        
        # Create mock step
        step = MockStep("s1", "vasp_scf", "scf")
        
        # Run VASP
        result = vasp_engine.run_step(step, working_dir, None)
        
        # Check results
        assert result.success, f"SCF failed: {result.error}"
        assert (working_dir / "OSZICAR").exists()
        assert (working_dir / "OUTCAR").exists()
        assert (working_dir / "CHGCAR").exists()
        
        # Parse outputs
        parsed = parse_vasp_output(working_dir)
        assert parsed["success"] is True
        assert parsed["energy"] is not None
        assert parsed["converged"] is True
    
    def test_bands_copies_chgcar_from_scf(self, vasp_engine, use_fake_vasp, tmp_path):
        """Test bands calculation copies CHGCAR from SCF and succeeds."""
        # Setup SCF directory
        scf_dir = tmp_path / "scf"
        scf_dir.mkdir()
        
        # Create SCF inputs
        (scf_dir / "POSCAR").write_text("""Si2
1.0
3.867 0.000 0.000
1.934 3.349 0.000
1.934 1.116 3.157
Si
2
Direct
0.0 0.0 0.0
0.25 0.25 0.25
""")
        (scf_dir / "INCAR").write_text("""SYSTEM = Si2_SCF
ENCUT = 300
PREC = Normal
ISMEAR = 0
SIGMA = 0.05
IBRION = -1
NSW = 0
""")
        (scf_dir / "KPOINTS").write_text("""Automatic
0
Gamma
4 4 4
0 0 0
""")
        (scf_dir / "POTCAR").write_text("FAKE POTCAR\n")
        
        # Run SCF
        scf_step = MockStep("s1", "vasp_scf", "scf")
        scf_result = vasp_engine.run_step(scf_step, scf_dir, None)
        assert scf_result.success
        
        # Verify SCF produced CHGCAR
        assert (scf_dir / "CHGCAR").exists()
        
        # Setup bands directory
        bands_dir = tmp_path / "bands"
        bands_dir.mkdir()
        
        # Create bands inputs
        (bands_dir / "POSCAR").write_text((scf_dir / "POSCAR").read_text())
        (bands_dir / "INCAR").write_text("""SYSTEM = Si2_bands
ENCUT = 300
PREC = Normal
ISMEAR = 0
SIGMA = 0.05
IBRION = -1
NSW = 0
ICHARG = 11
""")
        (bands_dir / "KPOINTS").write_text("""k-points along high symmetry path
40
Line-mode
Reciprocal
0.0 0.0 0.0   ! G
0.5 0.0 0.5   ! X
""")
        (bands_dir / "POTCAR").write_text("FAKE POTCAR\n")
        
        # Copy CHGCAR from SCF
        import shutil
        shutil.copy(scf_dir / "CHGCAR", bands_dir / "CHGCAR")
        
        # Run bands
        bands_step = MockStep("s2", "vasp_bandspw", "bandspw")
        bands_result = vasp_engine.run_step(bands_step, bands_dir, None)
        
        # Check results
        assert bands_result.success, f"Bands failed: {bands_result.error}"
        assert (bands_dir / "EIGENVAL").exists()
        
        # Parse outputs
        parsed = parse_vasp_output(bands_dir)
        assert parsed["success"] is True
    
    def test_dos_copies_chgcar_from_scf(self, vasp_engine, use_fake_vasp, tmp_path):
        """Test DOS calculation copies CHGCAR from SCF and succeeds."""
        # Setup SCF directory
        scf_dir = tmp_path / "scf"
        scf_dir.mkdir()
        
        # Create SCF inputs and run (reuse from test_bands)
        (scf_dir / "POSCAR").write_text("""Si2
1.0
3.867 0.000 0.000
1.934 3.349 0.000
1.934 1.116 3.157
Si
2
Direct
0.0 0.0 0.0
0.25 0.25 0.25
""")
        (scf_dir / "INCAR").write_text("""SYSTEM = Si2_SCF
ENCUT = 300
PREC = Normal
ISMEAR = 0
SIGMA = 0.05
IBRION = -1
NSW = 0
""")
        (scf_dir / "KPOINTS").write_text("""Automatic
0
Gamma
4 4 4
0 0 0
""")
        (scf_dir / "POTCAR").write_text("FAKE POTCAR\n")
        
        scf_step = MockStep("s1", "vasp_scf", "scf")
        scf_result = vasp_engine.run_step(scf_step, scf_dir, None)
        assert scf_result.success
        assert (scf_dir / "CHGCAR").exists()
        
        # Setup DOS directory
        dos_dir = tmp_path / "dos"
        dos_dir.mkdir()
        
        # Create DOS inputs
        (dos_dir / "POSCAR").write_text((scf_dir / "POSCAR").read_text())
        (dos_dir / "INCAR").write_text("""SYSTEM = Si2_dos
ENCUT = 300
PREC = Normal
ISMEAR = -5
SIGMA = 0.05
IBRION = -1
NSW = 0
ICHARG = 11
NEDOS = 3001
""")
        (dos_dir / "KPOINTS").write_text("""Automatic
0
Gamma
12 12 12
0 0 0
""")
        (dos_dir / "POTCAR").write_text("FAKE POTCAR\n")
        
        # Copy CHGCAR from SCF
        import shutil
        shutil.copy(scf_dir / "CHGCAR", dos_dir / "CHGCAR")
        
        # Run DOS
        dos_step = MockStep("s3", "vasp_dos", "dos")
        dos_result = vasp_engine.run_step(dos_step, dos_dir, None)
        
        # Check results
        assert dos_result.success, f"DOS failed: {dos_result.error}"
        assert (dos_dir / "DOSCAR").exists()
        
        # Parse outputs
        parsed = parse_vasp_output(dos_dir)
        assert parsed["success"] is True
    
    def test_bands_fails_if_scf_not_done(self, vasp_engine, use_fake_vasp, tmp_path):
        """Test bands fails if SCF prerequisite not met."""
        # Setup bands directory without CHGCAR
        bands_dir = tmp_path / "bands"
        bands_dir.mkdir()
        
        # Create bands inputs
        (bands_dir / "POSCAR").write_text("""Si2
1.0
3.867 0.000 0.000
1.934 3.349 0.000
1.934 1.116 3.157
Si
2
Direct
0.0 0.0 0.0
0.25 0.25 0.25
""")
        (bands_dir / "INCAR").write_text("""SYSTEM = Si2_bands
ENCUT = 300
PREC = Normal
ISMEAR = 0
SIGMA = 0.05
IBRION = -1
NSW = 0
ICHARG = 11
""")
        (bands_dir / "KPOINTS").write_text("""k-points along high symmetry path
40
Line-mode
Reciprocal
0.0 0.0 0.0   ! G
0.5 0.0 0.5   ! X
""")
        (bands_dir / "POTCAR").write_text("FAKE POTCAR\n")
        
        # Note: CHGCAR is missing
        
        # Try to run bands - should work with fake_vasp (it generates outputs anyway)
        # But in real scenario, VASP would fail without CHGCAR for ICHARG=11
        # This test verifies the workflow, not the actual VASP behavior
        bands_step = MockStep("s2", "vasp_bandspw", "bandspw")
        
        # With fake_vasp, it will succeed (fake_vasp doesn't check prerequisites)
        # But we can verify the staging logic would fail
        from quantumvitas.execution.vasp_staging import MissingArtifactError
        
        # Test staging logic directly
        # Create a mock reference SCF step
        ref_scf_step = MockStep("s1", "vasp_scf", "scf")
        
        # Create a mock reference step entry that is not done
        ref_entry = ManifestStepEntry(
            kind="vasp_scf",
            step_ulid="s1",
            pseudo_set_sha="fake_sha",
            structure_sha="fake_sha",
            step_sha="fake_sha",
            done=False,  # Not done!
        )
        
        # Try to stage CHGCAR - should fail for non-SCF step
        scf_dir = tmp_path / "scf"
        scf_dir.mkdir()
        bands_workdir = tmp_path / "bands_workdir"
        bands_workdir.mkdir()
        
        with pytest.raises(MissingPrerequisiteError):
            stage_chgcar(
                current_step=bands_step,
                reference_scf_step=ref_scf_step,
                manifest_entry=ref_entry,
                calc_raw_dir=tmp_path,
                target_workdir=bands_workdir,
            )

