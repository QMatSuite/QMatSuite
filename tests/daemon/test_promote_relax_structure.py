"""
Tests for promote_relax_structure daemon RPC.

NOTE: These tests are skipped because promote_relax_structure is not yet
implemented in the new domain API (QVService). The functionality exists
in the legacy API but needs migration.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from quantumvitas.api import QVService
from quantumvitas.api.errors import APIError
from quantumvitas.daemon.server import QVDaemon, RPCRequest
from quantumvitas.execution.relax_artifacts import write_generated_structure


def send_request(daemon: QVDaemon, method: str, payload: dict) -> dict:
    """Helper to send RPC request and get response."""
    request = RPCRequest(
        id="test-request",
        type=method,
        payload=payload,
    )
    response = daemon.handle_request(request)
    
    if not response.ok:
        raise RuntimeError(f"Daemon request failed: {response.error}")
    
    return response.data


class TestPromoteRelaxStructureAPI:
    """Test promote_relax_structure API directly."""

    def test_promote_creates_new_resource(self, tmp_path):
        """Promote creates a new structure resource."""
        from pymatgen.core import Structure, Lattice
        
        # Create project
        project_root = QVService.init_project(tmp_path / "project")
        
        # Import structure - use pymatgen to create proper JSON
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.43)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        source = tmp_path / "si.json"
        source.write_text(json.dumps(structure.as_dict()))
        struct_result = QVService(project_root).structure.import_file(source, name="Silicon")
        
        # Create calculation
        calc_result = QVService(project_root).project.init_calculation(name="calc001", structure_selector=struct_result.meta.ulid, engine_family="qe")
        calc_ulid = calc_result.ulid
        
        # Create relax step
        step_result = QVService(project_root).calculation.add_step(calc_ulid, step_type_gen="relax", name="relax")  # GEN type for UI layer
        step_ulid = step_result.ulid
        
        # Write generated structure
        lattice = Lattice.cubic(5.5)  # Slightly different lattice
        relaxed_structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        calc_dir = project_root / "calculations" / "calc001"
        write_generated_structure(
            structure=relaxed_structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type_spec="qe_relax",  # Execution layer uses SPEC type
            calculation_ulid=calc_ulid,
            input_structure_ulid=struct_result.meta.ulid,
        )
        
        # Promote
        svc = QVService(project_root)
        result = svc.structure.promote_relax_structure(
            calculation_selector=calc_ulid,
            step_selector=step_ulid,
            name="relaxed_silicon",
        )
        
        # Verify new structure was created
        assert result.meta.ulid != struct_result.meta.ulid  # Different ULID
        assert result.meta.name == "relaxed_silicon"
        # StructureDTO doesn't have absolute_path, compute from slug
        structure_path = project_root / "structures" / f"{result.meta.slug}.json"
        assert structure_path.exists()

        # Verify structure content - read back using pymatgen
        from quantumvitas.io import read_structure
        loaded_structure = read_structure(structure_path)
        assert loaded_structure.lattice.a == pytest.approx(5.5)

    def test_promote_requires_current_json(self, tmp_path):
        """Promote fails if current.json doesn't exist."""
        # Create project
        project_root = QVService.init_project(tmp_path / "project")
        
        # Import structure - use pymatgen to create proper JSON
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.43)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        source = tmp_path / "si.json"
        source.write_text(json.dumps(structure.as_dict()))
        struct_result = QVService(project_root).structure.import_file(source, name="Silicon")
        
        # Create calculation and step
        calc_result = QVService(project_root).project.init_calculation(name="calc001", structure_selector=struct_result.meta.ulid, engine_family="qe")
        step_result = QVService(project_root).calculation.add_step(calc_result.ulid, step_type_gen="relax", name="relax")  # GEN type for UI layer
        
        # Try to promote without current.json
        svc = QVService(project_root)
        with pytest.raises(APIError) as exc_info:
            svc.structure.promote_relax_structure(
                calculation_selector=calc_result.ulid,
                step_selector=step_result.ulid,
            )
        
        assert "No generated structure found" in str(exc_info.value)

    def test_promote_requires_relax_step(self, tmp_path):
        """Promote fails if step is not a relax step."""
        # Create project
        project_root = QVService.init_project(tmp_path / "project")
        
        # Import structure - use pymatgen to create proper JSON
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.43)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        source = tmp_path / "si.json"
        source.write_text(json.dumps(structure.as_dict()))
        struct_result = QVService(project_root).structure.import_file(source, name="Silicon")
        
        # Create calculation and SCF step (not relax)
        calc_result = QVService(project_root).project.init_calculation(name="calc001", structure_selector=struct_result.meta.ulid, engine_family="qe")
        step_result = QVService(project_root).calculation.add_step(calc_result.ulid, step_type_gen="scf", name="scf")  # GEN type for UI layer
        
        # Try to promote non-relax step
        svc = QVService(project_root)
        with pytest.raises(APIError) as exc_info:
            svc.structure.promote_relax_structure(
                calculation_selector=calc_result.ulid,
                step_selector=step_result.ulid,
            )
        
        assert "not a relax step" in str(exc_info.value)


class TestPromoteRelaxStructureDaemonRPC:
    """Test promote_relax_structure via daemon RPC."""

    def test_daemon_promote_rpc(self, tmp_path):
        """Daemon RPC for promote works correctly."""
        from pymatgen.core import Structure, Lattice
        
        # Create project
        project_root = QVService.init_project(tmp_path / "project")
        
        # Import structure - use pymatgen to create proper JSON
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.43)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        source = tmp_path / "si.json"
        source.write_text(json.dumps(structure.as_dict()))
        struct_result = QVService(project_root).structure.import_file(source, name="Silicon")
        
        # Create calculation and relax step
        calc_result = QVService(project_root).project.init_calculation(name="calc001", structure_selector=struct_result.meta.ulid, engine_family="qe")
        step_result = QVService(project_root).calculation.add_step(calc_result.ulid, step_type_gen="relax", name="relax")  # GEN type for UI layer
        
        # Write generated structure
        lattice = Lattice.cubic(5.5)
        relaxed_structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        calc_dir = project_root / "calculations" / "calc001"
        write_generated_structure(
            structure=relaxed_structure,
            calc_dir=calc_dir,
            step_ulid=step_result.ulid,
            step_type_spec="qe_relax",  # Execution layer uses SPEC type
        )
        
        # Call via daemon
        daemon = QVDaemon()
        response = send_request(daemon, "promote_relax_structure", {
            "project_root": str(project_root),
            "calculation": calc_result.ulid,
            "step": step_result.ulid,
            "name": "promoted_silicon",
        })
        
        # Verify response - send_request already checks response.ok and returns response.data
        assert "structure" in response
        assert response["structure"]["name"] == "promoted_silicon"
        assert "ulid" in response["structure"]
        assert "path" in response["structure"]

