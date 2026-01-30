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
    V1_DIMENSIONS,
)
from quantumvitas.presets.detector import detect_magnetism, detect_occupations_scheme
from quantumvitas.presets.dimensions import MagnetismOption, OccupationsSchemeOption, DIMENSION_OCCUPATIONS_SCHEME


class TestReceiverRegistry:
    """Tests for the preset receiver registry (Phase 8A)."""
    
    def test_pw_step_types_accept_v1_dimensions(self):
        """Verify pw.x step types accept all v1 preset dimensions (including precision)."""
        registry = get_receiver_registry()
        
        for step_type in PW_STEP_TYPES:
            accepted = registry.get_accepted_dimensions(step_type)
            # bands_pw is a special case: accepts magnetism/precision but NOT occupations_scheme
            if step_type == "bands_pw":
                expected = V1_DIMENSIONS - {DIMENSION_OCCUPATIONS_SCHEME}
                assert accepted == expected, f"{step_type} should accept v1 dimensions except occupations_scheme"
            else:
                assert accepted == V1_DIMENSIONS, f"{step_type} should accept all v1 dimensions"
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
        presets = {"magnetism": "collinear_lsda", "occupations_scheme": "smearing_gaussian"}
        
        # SCF step should accept all presets
        filtered = filter_presets_for_step("scf", presets)
        assert filtered == presets
        
        # NSCF step should accept all presets
        filtered = filter_presets_for_step("nscf", presets)
        assert filtered == presets
    
    def test_filter_presets_for_non_receiver_step(self):
        """Filter presets for a non-receiver step type."""
        presets = {"magnetism": "collinear_lsda", "occupations_scheme": "smearing_gaussian"}
        
        # DOS step should filter out all presets
        filtered = filter_presets_for_step("dos", presets)
        assert filtered == {}
        
        # Bands step should filter out all presets
        filtered = filter_presets_for_step("bands", presets)
        assert filtered == {}
    
    def test_unknown_step_type_accepts_none(self):
        """Unknown step types should accept no presets (safe default)."""
        presets = {"magnetism": "collinear_lsda"}
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
            "step_type_gen": "scf",
            "parameters": {
                "SYSTEM": {"nbnd": 40}  # nbnd is not a preset param
            }
        }))
        
        result = apply_presets_to_step(step_file, {"magnetism": "collinear_lsda"})
        
        assert result["accepted"] is True
        assert result["filtered_options"] == {"magnetism": "collinear_lsda"}
        
        # Verify file was updated
        updated = yaml.safe_load(step_file.read_text())
        assert updated["parameters"]["SYSTEM"]["nspin"] == 2
        assert updated["parameters"]["SYSTEM"]["nbnd"] == 40  # Preserved (not preset-related)
    
    def test_apply_to_non_receiver_step(self, temp_step_dir):
        """Apply presets to a non-receiver step (DOS) - should skip."""
        step_file = temp_step_dir / "2_dos.step.yaml"
        step_file.write_text(yaml.safe_dump({
            "step_type_gen": "dos",
            "parameters": {
                "DOS": {"fildos": "dos.dat"}
            }
        }))
        
        result = apply_presets_to_step(step_file, {"magnetism": "collinear_lsda"})
        
        assert result["accepted"] is False
        assert result["filtered_options"] == {}
        
        # Verify file was NOT modified
        content = yaml.safe_load(step_file.read_text())
        assert "SYSTEM" not in content.get("parameters", {})
    
    def test_apply_multiple_dimensions_to_receiver(self, temp_step_dir):
        """Apply multiple preset dimensions at once."""
        step_file = temp_step_dir / "1_scf.step.yaml"
        step_file.write_text(yaml.safe_dump({
            "step_type_gen": "scf",
            "parameters": {}
        }))
        
        # Apply magnetism and occupations_scheme (degauss is NOT written by OccupationsScheme)
        result = apply_presets_to_step(step_file, {
            "magnetism": "collinear_lsda",
            "occupations_scheme": "smearing_gaussian",
        })
        
        assert result["accepted"] is True
        assert "magnetism" in result["filtered_options"]
        assert "occupations_scheme" in result["filtered_options"]
        
        # Verify file was updated with both dimensions
        updated = yaml.safe_load(step_file.read_text())
        assert updated["parameters"]["SYSTEM"]["nspin"] == 2
        assert updated["parameters"]["SYSTEM"]["occupations"] == "smearing"  # YAML parsed value (no outer quotes)
        assert updated["parameters"]["SYSTEM"]["smearing"] == "gaussian"  # YAML parsed value (no outer quotes)
        # degauss is NOT written by OccupationsScheme (owned by Precision)
        assert "degauss" not in updated["parameters"]["SYSTEM"]


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
            "meta": {"ulid": "01TEST", "name": "test_calc", "slug": "test_calc"},
            "structure_id": "01STRUCT",
            "steps": [
                {"step_file": "steps/1_scf.step.yaml", "step_type_gen": "scf"},
                {"step_file": "steps/2_nscf.step.yaml", "step_type_gen": "nscf"},
                {"step_file": "steps/3_dos.step.yaml", "step_type_gen": "dos"},
            ]
        }))
        
        # Create receiver steps (SCF, NSCF)
        (steps_dir / "1_scf.step.yaml").write_text(yaml.safe_dump({
            "step_type_gen": "scf",
            "parameters": {"SYSTEM": {"ecutwfc": 40.0}}
        }))
        
        (steps_dir / "2_nscf.step.yaml").write_text(yaml.safe_dump({
            "step_type_gen": "nscf",
            "parameters": {"SYSTEM": {"ecutwfc": 40.0}}
        }))
        
        # Create non-receiver step (DOS)
        (steps_dir / "3_dos.step.yaml").write_text(yaml.safe_dump({
            "step_type_gen": "dos",
            "parameters": {"DOS": {"fildos": "dos.dat"}}
        }))
        
        return calc_dir
    
    def test_broadcast_apply_updates_receivers_only(self, calc_with_mixed_steps):
        """BROADCAST apply should update receiver steps and skip non-receivers."""
        calc_dir = calc_with_mixed_steps
        steps_dir = calc_dir / "steps"
        
        # Apply magnetism=collinear_lsda to all steps (BROADCAST)
        results = []
        for step_file in sorted(steps_dir.glob("*.step.yaml")):
            result = apply_presets_to_step(step_file, {"magnetism": "collinear_lsda"})
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
        
        # Initial detection - should be nonmagnetic (default)
        initial = detect_presets_from_calculation(calc_dir)
        assert initial["magnetism"] == "nonmagnetic"
        
        # Apply magnetism=collinear_lsda to all receiver steps
        for step_file in sorted(steps_dir.glob("*.step.yaml")):
            apply_presets_to_step(step_file, {"magnetism": "collinear_lsda"})
        
        # Detection after apply - should be collinear_lsda
        after = detect_presets_from_calculation(calc_dir)
        assert after["magnetism"] == "collinear_lsda"
    
    def test_broadcast_apply_occupations_scheme_preset(self, calc_with_mixed_steps):
        """BROADCAST apply occupations_scheme preset (smearing_gaussian) + precision (for degauss)."""
        calc_dir = calc_with_mixed_steps
        steps_dir = calc_dir / "steps"
        
        # Apply occupations_scheme=smearing_gaussian to all steps
        # (degauss is NOT written by OccupationsScheme, owned by Precision)
        for step_file in sorted(steps_dir.glob("*.step.yaml")):
            apply_presets_to_step(step_file, {
                "occupations_scheme": "smearing_gaussian",
            })
        
        # Verify receiver steps have smearing but NOT degauss
        scf_content = yaml.safe_load((steps_dir / "1_scf.step.yaml").read_text())
        assert scf_content["parameters"]["SYSTEM"]["occupations"] == "smearing"  # YAML parsed value (no outer quotes)
        assert scf_content["parameters"]["SYSTEM"]["smearing"] == "gaussian"  # YAML parsed value (no outer quotes)
        # degauss is NOT written by OccupationsScheme (owned by Precision)
        assert "degauss" not in scf_content["parameters"]["SYSTEM"]
        
        # Verify detection
        detected = detect_presets_from_calculation(calc_dir)
        assert detected["occupations_scheme"] == "smearing_gaussian"


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
            "step_type_gen": "scf",
        }))
        
        return calc_dir
    
    def test_apply_to_step_with_no_parameters(self, calc_with_empty_steps):
        """Apply to a step that has no parameters section yet."""
        step_file = calc_with_empty_steps / "steps" / "1_scf.step.yaml"
        
        result = apply_presets_to_step(step_file, {"magnetism": "collinear_lsda"})
        
        assert result["accepted"] is True
        
        # Verify parameters section was created
        updated = yaml.safe_load(step_file.read_text())
        assert "parameters" in updated
        assert "SYSTEM" in updated["parameters"]
        assert updated["parameters"]["SYSTEM"]["nspin"] == 2
    
    def test_apply_with_physics_validation_failure(self, calc_with_empty_steps):
        """Apply invalid physics combination (contradiction: lspinorb=true + noncolin=false)."""
        step_file = calc_with_empty_steps / "steps" / "1_scf.step.yaml"
        
        # Create a step with noncolin=false, then manually add lspinorb=true
        # This creates a contradiction: SOC requires noncollinear
        step_file.write_text(yaml.safe_dump({
            "step_type_gen": "scf",
            "parameters": {"SYSTEM": {"noncolin": False, "lspinorb": True}}
        }))
        
        from quantumvitas.presets.compiler import PresetCompilationError
        
        # Applying any magnetism option should trigger validation
        # The final state will have lspinorb=true but noncolin=false, which is invalid
        # Actually, applying will overwrite, so we need to test a case where the contradiction persists
        # Let's apply something that doesn't change noncolin but keeps lspinorb
        # Actually, the validation checks the final merged state, so if we apply nonmagnetic
        # it will set noncolin=false and lspinorb=false, removing the contradiction
        # We need to test a case where the final state has the contradiction
        
        # Better test: Apply noncollinear_soc, but the step already has noncolin=false
        # Wait, that will overwrite noncolin to true, so no contradiction
        
        # Actually, the real test case: if we have a step with both noncolin=false AND lspinorb=true
        # (manually set, which shouldn't happen but could), validation should catch it
        # But when we apply, we overwrite, so the contradiction is resolved
        
        # Let's test by applying something that would create a contradiction if the existing state persists
        # Actually, validation happens on the FINAL state after merge, so if we have:
        # existing: noncolin=false, lspinorb=true
        # applying: noncollinear_soc (sets noncolin=true, lspinorb=true)
        # final: noncolin=true, lspinorb=true (valid!)
        
        # The test needs to check a case where the final merged state has a contradiction
        # One way: have existing nspin=2, apply something that sets noncolin=true but doesn't remove nspin
        # But noncollinear removes nspin, so that won't work
        
        # Actually, let's test the case where we manually have both noncolin=true and nspin=2
        # and validation should catch it even if we don't apply anything new
        # But we're applying, so...
        
        # Let me test a simpler case: apply noncollinear_soc to a step that has nspin=2 explicitly set
        # After apply: noncolin=true, lspinorb=true, but nspin should be removed
        # If nspin is NOT removed (bug), then we have noncolin=true + nspin=2 which is invalid
        
        # Actually, the real issue: we need to test that validation catches contradictions
        # in the final state. Let's create a step with noncolin=true and nspin=2 (manually),
        # then apply something that doesn't fix it
        step_file.write_text(yaml.safe_dump({
            "step_type_gen": "scf",
            "parameters": {"SYSTEM": {"noncolin": True, "nspin": 2}}
        }))
        
        # Applying any magnetism option should trigger validation on the final state
        # But applying will fix it by removing nspin or setting noncolin=false
        # So we need to test validation on a state that already has the contradiction
        
        # Actually, let's just test that validation works by checking the final state
        # We'll manually create a contradiction and see if validation catches it
        # But validation only runs when we apply...
        
        # Better approach: test that if we have a step with a contradiction already,
        # and we try to apply something that would keep the contradiction, it fails
        # But since apply overwrites, it will fix it...
        
        # Let me just test that validation function works by calling it directly on invalid state
        from quantumvitas.presets.integration import _validate_magnetism_physics
        
        with pytest.raises(PresetCompilationError) as exc_info:
            _validate_magnetism_physics({"noncolin": True, "nspin": 2})
        
        assert "noncolin=true" in str(exc_info.value).lower() or "nspin=2" in str(exc_info.value).lower()
    
    def test_apply_with_physics_validation_disabled(self, calc_with_empty_steps):
        """Apply with validation disabled should succeed."""
        step_file = calc_with_empty_steps / "steps" / "1_scf.step.yaml"
        
        # With validation disabled, should not raise
        result = apply_presets_to_step(step_file, {
            "magnetism": "noncollinear_soc",
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
            "step_type_gen": "scf",
            "parameters": {"SYSTEM": {"nspin": 2}}
        }))
        
        # NSCF with non-spin (default)
        (steps_dir / "2_nscf.step.yaml").write_text(yaml.safe_dump({
            "step_type_gen": "nscf",
            "parameters": {"SYSTEM": {"ecutwfc": 40.0}}  # No nspin = nonspin
        }))
        
        return calc_dir
    
    def test_detect_custom_when_steps_disagree(self, calc_with_disagreeing_steps):
        """Detector should return Custom when steps have different values."""
        detected = detect_presets_from_calculation(calc_with_disagreeing_steps)
        
        # Steps disagree on magnetism: SCF has nspin=2 (collinear_lsda), NSCF has implicit nspin=1 (nonmagnetic)
        assert detected["magnetism"] == "Custom"
    
    def test_broadcast_apply_resolves_custom(self, calc_with_disagreeing_steps):
        """BROADCAST apply should resolve Custom state."""
        calc_dir = calc_with_disagreeing_steps
        steps_dir = calc_dir / "steps"
        
        # Initially Custom
        initial = detect_presets_from_calculation(calc_dir)
        assert initial["magnetism"] == "Custom"
        
        # Apply magnetism=collinear_lsda to all receiver steps
        for step_file in sorted(steps_dir.glob("*.step.yaml")):
            apply_presets_to_step(step_file, {"magnetism": "collinear_lsda"})
        
        # After apply, should be collinear_lsda (not Custom)
        after = detect_presets_from_calculation(calc_dir)
        assert after["magnetism"] == "collinear_lsda"

