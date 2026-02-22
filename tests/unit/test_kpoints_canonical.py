"""
Unit tests for K_POINTS representation.

Tests that:
1. Applying precision writes K_POINTS to cards.K_POINTS only
2. Detector reads from cards.K_POINTS only
3. QE kpoints are represented as cards.K_POINTS only (no parameters.K_POINTS support)
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import yaml

from qmatsuite.presets.integration import apply_presets_to_step, detect_presets_from_calculation
from qmatsuite.presets.precision import PrecisionAdvisor, PrecisionOption


class TestKPointsCanonicalization:
    """Test K_POINTS canonical format (cards.K_POINTS)."""
    
    @pytest.fixture
    def temp_step_file(self):
        """Create a temporary step file."""
        temp_dir = tempfile.mkdtemp()
        step_file = Path(temp_dir) / "scf.step.yaml"
        step_file.write_text(yaml.safe_dump({
            "step_type_gen": "scf",
            "parameters": {
                "SYSTEM": {},
                "ELECTRONS": {},
            },
            "cards": {},
        }))
        yield step_file
        shutil.rmtree(temp_dir)
    
    def test_apply_precision_writes_to_cards_kpoints(self, temp_step_file):
        """Apply precision should write K_POINTS to cards.K_POINTS, not parameters.K_POINTS."""
        # Create PrecisionAdvisor
        species_map = {"Si": {"pseudo_sha256": "test_sha"}}
        lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
        advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice)
        
        # Apply precision=med
        precision_advice = advisor.advise_for_step(PrecisionOption.MED, "scf")
        apply_presets_to_step(
            temp_step_file,
            {"precision": "med"},
            precision_advice=precision_advice,
            precision_lattice_matrix=lattice,
        )
        
        # Verify step.yml content
        content = yaml.safe_load(temp_step_file.read_text())
        
        # Should have cards.K_POINTS (canonical)
        assert "cards" in content
        assert "K_POINTS" in content["cards"]
        kpoints_card = content["cards"]["K_POINTS"]
        assert kpoints_card["option"] == "automatic"
        assert kpoints_card["data"] == [[6, 6, 6, 0, 0, 0]]  # Si med precision
        
        # Should NOT have parameters.K_POINTS
        if "parameters" in content:
            assert "K_POINTS" not in content["parameters"], "parameters.K_POINTS should not exist"
    
    def test_detector_ignores_parameters_kpoints(self, temp_step_file):
        """Detector should ignore parameters.K_POINTS if present (treat as missing)."""
        # Add invalid parameters.K_POINTS (should be ignored)
        content = yaml.safe_load(temp_step_file.read_text())
        content["parameters"]["K_POINTS"] = {
            "step_type_gen": "automatic",
            "mesh": [4, 4, 4, 0, 0, 0],
        }
        # No cards.K_POINTS - should return None
        temp_step_file.write_text(yaml.safe_dump(content))
        
        # Test detector reading - should return None (no cards.K_POINTS)
        from qmatsuite.presets.detector import _get_kpoints_mesh
        
        step_content = yaml.safe_load(temp_step_file.read_text())
        params_dict = {
            "cards": step_content.get("cards", {}),
            **step_content.get("parameters", {}),
        }
        
        mesh = _get_kpoints_mesh(params_dict)
        assert mesh is None, "Should return None when only parameters.K_POINTS exists (not supported)"
    
    def test_detector_reads_from_cards_kpoints(self, temp_step_file):
        """Detector should read K_POINTS from cards.K_POINTS for detection."""
        # Write canonical format directly
        content = yaml.safe_load(temp_step_file.read_text())
        content["cards"]["K_POINTS"] = {
            "option": "automatic",
            "data": [[6, 6, 6, 0, 0, 0]],
        }
        content["parameters"]["SYSTEM"] = {
            "ecutwfc": 50,
            "ecutrho": 400,
        }
        content["parameters"]["ELECTRONS"] = {
            "conv_thr": 1e-8,
        }
        temp_step_file.write_text(yaml.safe_dump(content))
        
        # Test detector reading from cards.K_POINTS format
        from qmatsuite.presets.detector import _get_kpoints_mesh
        
        step_content = yaml.safe_load(temp_step_file.read_text())
        params_dict = {
            "cards": step_content.get("cards", {}),
            **step_content.get("parameters", {}),
        }
        
        mesh = _get_kpoints_mesh(params_dict)
        assert mesh is not None, "Should extract mesh from cards.K_POINTS"
        assert mesh == (6, 6, 6, 0, 0, 0), f"Expected (6, 6, 6, 0, 0, 0), got {mesh}"

