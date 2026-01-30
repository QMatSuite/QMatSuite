"""
End-to-end integration tests for RELAX feature.

These tests verify the complete flow of relax steps, including:
- Structure generation and artifact management
- Promote functionality
- Error handling
- Integration with existing calculation system
"""

import json
import pytest
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.api.errors import APIError
from quantumvitas.core.exceptions import MissingArtifactError
from quantumvitas.execution.relax_artifacts import (
    get_generated_structure_path,
    read_generated_structure,
    write_generated_structure,
    is_relax_step_type,
)
from quantumvitas.workflow.registry import get_registry


class TestRelaxE2E:
    """End-to-end tests for relax feature."""

    def test_relax_step_type_detection(self):
        """Verify relax step types are correctly identified."""
        assert is_relax_step_type("qe_relax") is True
        # qe_vc_relax is deprecated and normalizes to qe_relax
        assert is_relax_step_type("qe_vc_relax") is True  # Should normalize and return True
        assert is_relax_step_type("qe_scf") is False
        
        # Verify registry configuration
        registry = get_registry()
        relax_spec = registry.get("qe_relax")
        assert relax_spec is not None
        assert relax_spec.is_structure_transform is True
        assert relax_spec.produces_charge_density is False

    def test_generated_structure_path_format(self, tmp_path):
        """Verify generated structure path follows canonical format."""
        calc_dir = tmp_path / "calc"
        step_ulid = "01TESTULID123456789012"
        
        path = get_generated_structure_path(calc_dir, step_ulid)
        
        expected = calc_dir / "generated_structures" / f"step_{step_ulid}" / "current.json"
        assert path == expected

    def test_write_and_read_generated_structure(self, tmp_path):
        """Verify write and read cycle for generated structures."""
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.5)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        calc_dir = tmp_path / "calc"
        step_ulid = "01WRITEREAD"
        
        # Write
        written_path = write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_relax",
            run_id="run001",
            calculation_ulid="calc001",
            input_structure_ulid="struct001",
        )
        
        assert written_path.exists()
        
        # Verify metadata
        data = json.loads(written_path.read_text())
        assert "__qv_meta__" in data
        assert data["__qv_meta__"]["type"] == "generated_structure"
        assert data["__qv_meta__"]["source_step_ulid"] == step_ulid
        assert data["__qv_meta__"]["provenance"]["method"] == "qe_relax"
        
        # Read
        loaded = read_generated_structure(calc_dir, step_ulid)
        
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded.lattice.a == pytest.approx(5.5)

    def test_promote_relax_structure_e2e(self, tmp_path):
        """End-to-end test: create relax step, write structure, promote."""
        from pymatgen.core import Structure, Lattice
        
        # Create project
        project_root = QVService.init_project(tmp_path / "project")
        
        # Import initial structure
        source = tmp_path / "si.json"
        lattice = Lattice.cubic(5.43)
        initial_structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        source.write_text(json.dumps(initial_structure.as_dict()))
        
        struct_result = QVService.import_structure(project_root, source, name="Silicon")
        
        # Create calculation
        calc_result = QVService.init_calculation(project_root, "calc001", structure_selector=struct_result.meta.ulid)
        calc_ulid = calc_result.ulid
        
        # Create relax step
        step_result = QVService.init_step(project_root, calc_ulid, step_type="qe_relax", name="relax")
        step_ulid = step_result.ulid
        
        # Write generated structure (simulating relax execution)
        relaxed_lattice = Lattice.cubic(5.5)  # Different lattice
        relaxed_structure = Structure(relaxed_lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        calc_dir = project_root / "calculations" / "calc001"
        write_generated_structure(
            structure=relaxed_structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_relax",
            calculation_ulid=calc_ulid,
            input_structure_ulid=struct_result.meta.ulid,
        )
        
        # Verify current.json exists
        artifact_path = get_generated_structure_path(calc_dir, step_ulid)
        assert artifact_path.exists()
        
        # Promote
        promoted_result = QVService.promote_relax_structure(
            project_root=project_root,
            calculation_selector=calc_ulid,
            step_selector=step_ulid,
            name="relaxed_silicon",
        )
        
        # Verify new structure created
        assert promoted_result.meta.ulid != struct_result.meta.ulid
        assert promoted_result.meta.name == "relaxed_silicon"
        assert promoted_result.absolute_path.exists()
        
        # Verify structure content
        from quantumvitas.io import read_structure
        loaded = read_structure(promoted_result.absolute_path)
        assert loaded.lattice.a == pytest.approx(5.5)

    def test_promote_requires_current_json(self, tmp_path):
        """Promote fails if current.json doesn't exist."""
        # Create project
        project_root = QVService.init_project(tmp_path / "project")
        
        # Import structure
        source = tmp_path / "si.json"
        from pymatgen.core import Structure, Lattice
        lattice = Lattice.cubic(5.43)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        source.write_text(json.dumps(structure.as_dict()))
        
        struct_result = QVService.import_structure(project_root, source, name="Silicon")
        
        # Create calculation and relax step
        calc_result = QVService.init_calculation(project_root, "calc001", structure_selector=struct_result.meta.ulid)
        step_result = QVService.init_step(project_root, calc_result.ulid, step_type="qe_relax", name="relax")
        
        # Try to promote without current.json
        with pytest.raises(APIError) as exc_info:
            QVService.promote_relax_structure(
                project_root=project_root,
                calculation_selector=calc_result.ulid,
                step_selector=step_result.ulid,
            )
        
        assert "No generated structure found" in str(exc_info.value)

    def test_promote_requires_relax_step_type(self, tmp_path):
        """Promote fails if step is not a relax step."""
        # Create project
        project_root = QVService.init_project(tmp_path / "project")
        
        # Import structure
        source = tmp_path / "si.json"
        from pymatgen.core import Structure, Lattice
        lattice = Lattice.cubic(5.43)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        source.write_text(json.dumps(structure.as_dict()))
        
        struct_result = QVService.import_structure(project_root, source, name="Silicon")
        
        # Create calculation and SCF step (not relax)
        calc_result = QVService.init_calculation(project_root, "calc001", structure_selector=struct_result.meta.ulid)
        step_result = QVService.init_step(project_root, calc_result.ulid, step_type="qe_scf", name="scf")
        
        # Try to promote non-relax step
        with pytest.raises(APIError) as exc_info:
            QVService.promote_relax_structure(
                project_root=project_root,
                calculation_selector=calc_result.ulid,
                step_selector=step_result.ulid,
            )
        
        assert "not a relax step" in str(exc_info.value)

    def test_generated_structure_metadata_preserved(self, tmp_path):
        """Verify generated structure metadata is preserved in current.json."""
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        calc_dir = tmp_path / "calc"
        step_ulid = "01METADATA"
        run_id = "run123"
        calc_ulid = "calc456"
        input_ulid = "struct789"
        
        write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_relax",  # Use unified type instead of deprecated qe_vc_relax
            run_id=run_id,
            calculation_ulid=calc_ulid,
            input_structure_ulid=input_ulid,
        )
        
        # Read and verify metadata
        data = json.loads(get_generated_structure_path(calc_dir, step_ulid).read_text())
        meta = data["__qv_meta__"]
        
        assert meta["type"] == "generated_structure"
        assert meta["source_step_ulid"] == step_ulid
        assert meta["source_run_id"] == run_id
        assert meta["provenance"]["method"] == "qe_relax"
        assert meta["provenance"]["calculation_ulid"] == calc_ulid
        assert meta["provenance"]["input_structure_ulid"] == input_ulid
        assert "generated_at" in meta

