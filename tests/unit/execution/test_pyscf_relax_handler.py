"""
Unit tests for PySCF relax handler.
"""

import json
import pytest
from pathlib import Path

from quantumvitas.execution.pyscf_relax_handler import handle_pyscf_relax_output
from quantumvitas.execution.relax_artifacts import get_generated_structure_path
from pymatgen.core import Molecule


class TestHandlePySCFRelaxOutput:
    """Test handling PySCF relax output."""

    def test_handle_pyscf_relax_creates_current_json(self, tmp_path):
        """handle_pyscf_relax_output creates current.json from results dict."""
        # Create calc directory
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        # Create results dict (as returned by run_pyscf_relax)
        results = {
            "success": True,
            "optimized_atoms": [
                {"element": "H", "xyz": [0.0, 0.0, 0.0]},
                {"element": "H", "xyz": [0.74, 0.0, 0.0]},
            ],
            "charge": 0,
            "spin_multiplicity": 1,
            "final_energy": -1.123456,
            "solver": "geometric",
        }
        
        step_ulid = "01PYSCFRELAX"
        step_type= "pyscf_relax"
        calculation_ulid = "01CALCTEST"
        input_structure_ulid = "01STRUCTEST"
        run_id = "run001"
        
        # Call handler
        artifact_path = handle_pyscf_relax_output(
            step_ulid=step_ulid,
            step_type=step_type,
            calc_dir=calc_dir,
            results=results,
            calculation_ulid=calculation_ulid,
            input_structure_ulid=input_structure_ulid,
            run_ulid=run_id,
        )
        
        # Verify current.json was created
        assert artifact_path.exists()
        assert artifact_path == get_generated_structure_path(calc_dir, step_ulid)
        
        # Verify content
        data = json.loads(artifact_path.read_text())
        assert "__qv_meta__" in data
        assert data["__qv_meta__"]["source_step_ulid"] == step_ulid
        assert data["__qv_meta__"]["provenance"]["method"] == step_type
        assert data["__qv_meta__"]["provenance"]["calculation_ulid"] == calculation_ulid
        assert data["__qv_meta__"]["provenance"]["input_structure_ulid"] == input_structure_ulid
        
        # Verify structure can be read
        structure_dict = data.copy()
        structure_dict.pop("__qv_meta__", None)
        loaded = Molecule.from_dict(structure_dict)
        assert loaded is not None
        assert len(loaded) == 2  # 2 H atoms
        assert loaded.charge == 0
        assert loaded.spin_multiplicity == 1

    def test_handle_pyscf_relax_missing_optimized_atoms_raises(self, tmp_path):
        """handle_pyscf_relax_output raises ValueError if optimized_atoms missing."""
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        # Results dict without optimized_atoms
        results = {
            "success": True,
            "error": "Some error",
        }
        
        with pytest.raises(ValueError, match="Results dict missing 'optimized_atoms' key"):
            handle_pyscf_relax_output(
                step_ulid="01TEST",
                step_type="pyscf_relax",
                calc_dir=calc_dir,
                results=results,
                calculation_ulid="01CALC",
                input_structure_ulid="01STRUCT",
            )

