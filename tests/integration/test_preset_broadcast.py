"""
Integration tests for BROADCAST preset application.

Per Constitution §10.1.1: Preset application is BROADCAST, not filtered.
The UI and calc layer do NOT decide which steps accept it.
Each step defines its own "preset receiver".

This test suite verifies:
1. BROADCAST apply targets all steps in a calculation
2. Steps with receiver capability accept and update parameters
3. Non-receiver steps (post-processing) are skipped
4. Detector returns correct state after apply
"""

import pytest
import tempfile
import shutil
from pathlib import Path

import yaml

from quantumvitas.presets.integration import (
    apply_presets_to_step,
    detect_presets_from_calculation,
)
from quantumvitas.presets.receivers import (
    get_receiver_registry,
    is_receiver,
    filter_presets_for_step,
    PW_STEP_TYPES,
    POST_PROCESSING_STEP_TYPES,
    V0_DIMENSIONS,
)
from quantumvitas.presets.detector import detect_spin, detect_soc, detect_material
from quantumvitas.presets.dimensions import SpinOption, SOCOption, MaterialOption


class TestReceiverRegistry:
    """Tests for the preset receiver registry (Phase 8A)."""
    
    def test_pw_step_types_accept_v0_dimensions(self):
        """Verify pw.x step types accept all v0 preset dimensions."""
        registry = get_receiver_registry()
        
        for step_type in PW_STEP_TYPES:
            accepted = registry.get_accepted_dimensions(step_type)
            assert accepted == V0_DIMENSIONS, f"{step_type} should accept all v0 dimensions"
            assert is_receiver(step_type), f"{step_type} should be a receiver"
    
    def test_post_processing_step_types_accept_none(self):
        """Verify post-processing step types accept no presets."""
        registry = get_receiver_registry()
        
        for step_type in POST_PROCESSING_STEP_TYPES:
            accepted = registry.get_accepted_dimensions(step_type)
            assert len(accepted) == 0, f"{step_type} should accept no presets"
            assert not is_receiver(step_type), f"{step_type} should NOT be a receiver"
    
    def test_filter_presets_for_receiver_step(self):
        """Filter presets for a receiver step type."""
        presets = {"spin": "collinear", "soc": "no_soc", "material": "metal"}
        
        # SCF step should accept all presets
        filtered = filter_presets_for_step("scf", presets)
        assert filtered == presets
        
        # NSCF step should accept all presets
        filtered = filter_presets_for_step("nscf", presets)
        assert filtered == presets
    
    def test_filter_presets_for_non_receiver_step(self):
        """Filter presets for a non-receiver step type."""
        presets = {"spin": "collinear", "soc": "no_soc", "material": "metal"}
        
        # DOS step should filter out all presets
        filtered = filter_presets_for_step("dos", presets)
        assert filtered == {}
        
        # Bands step should filter out all presets
        filtered = filter_presets_for_step("bands", presets)
        assert filtered == {}
    
    def test_unknown_step_type_accepts_none(self):
        """Unknown step types should accept no presets (safe default)."""
        presets = {"spin": "collinear"}
        filtered = filter_presets_for_step("unknown_step_type", presets)
        assert filtered == {}


class TestApplyPresetsToStep:
    """Tests for apply_presets_to_step with receiver logic."""
    
    @pytest.fixture
    def temp_step_dir(self):
        """Create a temporary directory for step files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    def test_apply_to_receiver_step(self, temp_step_dir):
        """Apply presets to a receiver step (SCF) - should update."""
        step_file = temp_step_dir / "1_scf.step.yaml"
        step_file.write_text(yaml.safe_dump({
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {"ecutwfc": 40.0}
            }
        }))
        
        result = apply_presets_to_step(step_file, {"spin": "collinear"})
        
        assert result["accepted"] is True
        assert result["filtered_options"] == {"spin": "collinear"}
        
        # Verify file was updated
        updated = yaml.safe_load(step_file.read_text())
        assert updated["parameters"]["SYSTEM"]["nspin"] == 2
        assert updated["parameters"]["SYSTEM"]["ecutwfc"] == 40.0  # Preserved
    
    def test_apply_to_non_receiver_step(self, temp_step_dir):
        """Apply presets to a non-receiver step (DOS) - should skip."""
        step_file = temp_step_dir / "2_dos.step.yaml"
        step_file.write_text(yaml.safe_dump({
            "step_type": "dos",
            "parameters": {
                "DOS": {"fildos": "dos.dat"}
            }
        }))
        
        result = apply_presets_to_step(step_file, {"spin": "collinear"})
        
        assert result["accepted"] is False
        assert result["filtered_options"] == {}
        
        # Verify file was NOT modified
        content = yaml.safe_load(step_file.read_text())
        assert "SYSTEM" not in content.get("parameters", {})
    
    def test_apply_multiple_dimensions_to_receiver(self, temp_step_dir):
        """Apply multiple preset dimensions at once."""
        step_file = temp_step_dir / "1_scf.step.yaml"
        step_file.write_text(yaml.safe_dump({
            "step_type": "scf",
            "parameters": {}
        }))
        
        result = apply_presets_to_step(step_file, {
            "spin": "collinear",
            "material": "metal",
        })
        
        assert result["accepted"] is True
        assert "spin" in result["filtered_options"]
        assert "material" in result["filtered_options"]
        
        # Verify file was updated with both
        updated = yaml.safe_load(step_file.read_text())
        assert updated["parameters"]["SYSTEM"]["nspin"] == 2
        assert updated["parameters"]["SYSTEM"]["occupations"] == "'smearing'"


class TestBroadcastApply:
    """Integration tests for BROADCAST apply across a calculation."""
    
    @pytest.fixture
    def calc_with_mixed_steps(self, tmp_path):
        """Create a calculation with both receiver and non-receiver steps."""
        calc_dir = tmp_path / "calculations" / "test_calc"
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir(parents=True)
        
        # Create calculation.yaml
        calc_yaml = calc_dir / "calculation.yaml"
        calc_yaml.write_text(yaml.safe_dump({
            "meta": {"id": "01TEST", "name": "test_calc", "slug": "test_calc"},
            "structure_id": "01STRUCT",
            "steps": [
                {"step_file": "steps/1_scf.step.yaml", "step_type": "scf"},
                {"step_file": "steps/2_nscf.step.yaml", "step_type": "nscf"},
                {"step_file": "steps/3_dos.step.yaml", "step_type": "dos"},
            ]
        }))
        
        # Create receiver steps (SCF, NSCF)
        (steps_dir / "1_scf.step.yaml").write_text(yaml.safe_dump({
            "step_type": "scf",
            "parameters": {"SYSTEM": {"ecutwfc": 40.0}}
        }))
        
        (steps_dir / "2_nscf.step.yaml").write_text(yaml.safe_dump({
            "step_type": "nscf",
            "parameters": {"SYSTEM": {"ecutwfc": 40.0}}
        }))
        
        # Create non-receiver step (DOS)
        (steps_dir / "3_dos.step.yaml").write_text(yaml.safe_dump({
            "step_type": "dos",
            "parameters": {"DOS": {"fildos": "dos.dat"}}
        }))
        
        return calc_dir
    
    def test_broadcast_apply_updates_receivers_only(self, calc_with_mixed_steps):
        """BROADCAST apply should update receiver steps and skip non-receivers."""
        calc_dir = calc_with_mixed_steps
        steps_dir = calc_dir / "steps"
        
        # Apply spin=collinear to all steps (BROADCAST)
        results = []
        for step_file in sorted(steps_dir.glob("*.step.yaml")):
            result = apply_presets_to_step(step_file, {"spin": "collinear"})
            results.append({
                "file": step_file.name,
                "accepted": result["accepted"],
            })
        
        # Verify: SCF and NSCF accepted, DOS skipped
        assert results[0]["file"] == "1_scf.step.yaml"
        assert results[0]["accepted"] is True
        
        assert results[1]["file"] == "2_nscf.step.yaml"
        assert results[1]["accepted"] is True
        
        assert results[2]["file"] == "3_dos.step.yaml"
        assert results[2]["accepted"] is False
        
        # Verify SCF was updated
        scf_content = yaml.safe_load((steps_dir / "1_scf.step.yaml").read_text())
        assert scf_content["parameters"]["SYSTEM"]["nspin"] == 2
        
        # Verify NSCF was updated
        nscf_content = yaml.safe_load((steps_dir / "2_nscf.step.yaml").read_text())
        assert nscf_content["parameters"]["SYSTEM"]["nspin"] == 2
        
        # Verify DOS was NOT updated (no SYSTEM namelist)
        dos_content = yaml.safe_load((steps_dir / "3_dos.step.yaml").read_text())
        assert "SYSTEM" not in dos_content.get("parameters", {})
    
    def test_detect_presets_after_broadcast_apply(self, calc_with_mixed_steps):
        """Detector should return correct state after BROADCAST apply."""
        calc_dir = calc_with_mixed_steps
        steps_dir = calc_dir / "steps"
        
        # Initial detection - should be nonspin (default)
        initial = detect_presets_from_calculation(calc_dir)
        assert initial["spin"] == "nonspin"
        
        # Apply spin=collinear to all receiver steps
        for step_file in sorted(steps_dir.glob("*.step.yaml")):
            apply_presets_to_step(step_file, {"spin": "collinear"})
        
        # Detection after apply - should be collinear
        after = detect_presets_from_calculation(calc_dir)
        assert after["spin"] == "collinear"
    
    def test_broadcast_apply_material_preset(self, calc_with_mixed_steps):
        """BROADCAST apply material preset (metal)."""
        calc_dir = calc_with_mixed_steps
        steps_dir = calc_dir / "steps"
        
        # Apply material=metal to all steps
        for step_file in sorted(steps_dir.glob("*.step.yaml")):
            apply_presets_to_step(step_file, {"material": "metal"})
        
        # Verify receiver steps have smearing
        scf_content = yaml.safe_load((steps_dir / "1_scf.step.yaml").read_text())
        assert scf_content["parameters"]["SYSTEM"]["occupations"] == "'smearing'"
        assert "smearing" in scf_content["parameters"]["SYSTEM"]
        assert "degauss" in scf_content["parameters"]["SYSTEM"]
        
        # Verify detection
        detected = detect_presets_from_calculation(calc_dir)
        assert detected["material"] == "metal"


class TestBroadcastApplyEdgeCases:
    """Edge cases for BROADCAST apply."""
    
    @pytest.fixture
    def calc_with_empty_steps(self, tmp_path):
        """Create a calculation with minimal step files."""
        calc_dir = tmp_path / "calculations" / "minimal"
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir(parents=True)
        
        # Create a step with no parameters section
        (steps_dir / "1_scf.step.yaml").write_text(yaml.safe_dump({
            "step_type": "scf",
        }))
        
        return calc_dir
    
    def test_apply_to_step_with_no_parameters(self, calc_with_empty_steps):
        """Apply to a step that has no parameters section yet."""
        step_file = calc_with_empty_steps / "steps" / "1_scf.step.yaml"
        
        result = apply_presets_to_step(step_file, {"spin": "collinear"})
        
        assert result["accepted"] is True
        
        # Verify parameters section was created
        updated = yaml.safe_load(step_file.read_text())
        assert "parameters" in updated
        assert "SYSTEM" in updated["parameters"]
        assert updated["parameters"]["SYSTEM"]["nspin"] == 2
    
    def test_apply_with_physics_validation_failure(self, calc_with_empty_steps):
        """Apply invalid physics combination (SOC without non-collinear)."""
        step_file = calc_with_empty_steps / "steps" / "1_scf.step.yaml"
        
        # This should raise PresetCompilationError due to physics validation
        from quantumvitas.presets.compiler import PresetCompilationError
        
        with pytest.raises(PresetCompilationError):
            apply_presets_to_step(step_file, {
                "spin": "collinear",  # Not noncollinear!
                "soc": "with_soc",    # Requires noncollinear
            }, validate_physics=True)
    
    def test_apply_with_physics_validation_disabled(self, calc_with_empty_steps):
        """Apply invalid physics combination with validation disabled."""
        step_file = calc_with_empty_steps / "steps" / "1_scf.step.yaml"
        
        # With validation disabled, should not raise
        result = apply_presets_to_step(step_file, {
            "spin": "collinear",
            "soc": "with_soc",
        }, validate_physics=False)
        
        assert result["accepted"] is True


class TestCustomStateDetection:
    """Tests for Custom state when steps disagree."""
    
    @pytest.fixture
    def calc_with_disagreeing_steps(self, tmp_path):
        """Create a calculation where steps have different preset values."""
        calc_dir = tmp_path / "calculations" / "custom"
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir(parents=True)
        
        # SCF with collinear spin
        (steps_dir / "1_scf.step.yaml").write_text(yaml.safe_dump({
            "step_type": "scf",
            "parameters": {"SYSTEM": {"nspin": 2}}
        }))
        
        # NSCF with non-spin (default)
        (steps_dir / "2_nscf.step.yaml").write_text(yaml.safe_dump({
            "step_type": "nscf",
            "parameters": {"SYSTEM": {"ecutwfc": 40.0}}  # No nspin = nonspin
        }))
        
        return calc_dir
    
    def test_detect_custom_when_steps_disagree(self, calc_with_disagreeing_steps):
        """Detector should return Custom when steps have different values."""
        detected = detect_presets_from_calculation(calc_with_disagreeing_steps)
        
        # Steps disagree on spin: SCF has nspin=2, NSCF has implicit nspin=1
        assert detected["spin"] == "Custom"
    
    def test_broadcast_apply_resolves_custom(self, calc_with_disagreeing_steps):
        """BROADCAST apply should resolve Custom state."""
        calc_dir = calc_with_disagreeing_steps
        steps_dir = calc_dir / "steps"
        
        # Initially Custom
        initial = detect_presets_from_calculation(calc_dir)
        assert initial["spin"] == "Custom"
        
        # Apply spin=collinear to all receiver steps
        for step_file in sorted(steps_dir.glob("*.step.yaml")):
            apply_presets_to_step(step_file, {"spin": "collinear"})
        
        # After apply, should be collinear (not Custom)
        after = detect_presets_from_calculation(calc_dir)
        assert after["spin"] == "collinear"

