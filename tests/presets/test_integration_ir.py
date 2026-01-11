"""
Integration tests for IR layer with preset system.

Tests SSOT enforcement, round-trip behavior, and integration with preset application.
"""

import pytest
import yaml
from pathlib import Path

from quantumvitas.presets.integration import (
    apply_presets_to_step,
    detect_presets_from_calculation_typed,
)
from quantumvitas.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    ConvergenceOption,
    CUSTOM,
    _CustomType,
)


class TestSSOTEnforcement:
    """Test that step.yaml remains SSOT and contains only QE params."""
    
    def test_preset_application_writes_only_qe_params(self, tmp_path):
        """Applying presets should write only QE params to step.yaml, not IR/preset."""
        step_path = tmp_path / "test.step.yaml"
        
        # Initial step.yaml with some QE params
        initial_content = {
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": 30.0,
                },
                "ELECTRONS": {
                    "conv_thr": 1e-4,
                },
            },
        }
        step_path.write_text(yaml.safe_dump(initial_content))
        
        # Apply presets
        options = {
            "magnetism": MagnetismOption.COLLINEAR_LSDA,
            "convergence": ConvergenceOption.FAST,
        }
        
        apply_presets_to_step(step_path, options, validate_physics=False)
        
        # Read back step.yaml
        result_content = yaml.safe_load(step_path.read_text())
        
        # Verify step.yaml contains only QE params (no IR/preset sections)
        assert "parameters" in result_content
        assert "SYSTEM" in result_content["parameters"]
        assert "ELECTRONS" in result_content["parameters"]
        
        # Should NOT contain IR-specific keys or preset metadata
        assert "ir" not in result_content
        assert "preset" not in result_content
        assert "ir_parameters" not in result_content
        
        # Should contain QE params
        assert "nspin" in result_content["parameters"]["SYSTEM"]  # QE param
        assert "mixing_beta" in result_content["parameters"]["ELECTRONS"]  # QE param
    
    def test_step_yaml_structure_preserved(self, tmp_path):
        """Step.yaml structure should be preserved (parameters section only)."""
        step_path = tmp_path / "test.step.yaml"
        
        initial_content = {
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {"ecutwfc": 30.0},
            },
            "some_other_field": "should_persist",
        }
        step_path.write_text(yaml.safe_dump(initial_content))
        
        # Apply preset
        options = {"magnetism": MagnetismOption.NONMAGNETIC}
        apply_presets_to_step(step_path, options, validate_physics=False)
        
        # Read back
        result_content = yaml.safe_load(step_path.read_text())
        
        # Other fields should persist
        assert result_content["step_type"] == "scf"
        assert result_content["some_other_field"] == "should_persist"
        
        # Parameters should be updated
        assert "parameters" in result_content
        assert "SYSTEM" in result_content["parameters"]


class TestRoundTripBehavior:
    """Test compile→detect round-trip behavior with IR layer."""
    
    def test_apply_then_detect_round_trip(self, tmp_path):
        """Apply preset then detect should return same preset."""
        step_path = tmp_path / "test.step.yaml"
        
        # Initial empty step
        initial_content = {
            "step_type": "scf",
            "parameters": {},
        }
        step_path.write_text(yaml.safe_dump(initial_content))
        
        # Apply presets
        applied_options = {
            "magnetism": MagnetismOption.COLLINEAR_LSDA,
            "occupations_scheme": OccupationsSchemeOption.FIXED,
            "convergence": ConvergenceOption.NORMAL,
        }
        apply_presets_to_step(step_path, applied_options, validate_physics=False)
        
        # Detect presets from step (use typed version for enum comparison)
        # Note: detect_presets_from_calculation_typed requires proper calculation structure
        # For this test, we'll use detect_dimension directly on the step YAML
        from quantumvitas.presets.spaces_registry import detect_dimension
        
        step_content = yaml.safe_load(step_path.read_text())
        step_yaml = step_content.get("parameters", {})
        
        # Detect each dimension
        detected_magnetism = detect_dimension("magnetism", step_yaml)
        detected_occupations = detect_dimension("occupations_scheme", step_yaml)
        detected_convergence = detect_dimension("convergence", step_yaml)
        
        # Should detect the same presets we applied
        assert detected_magnetism == MagnetismOption.COLLINEAR_LSDA
        assert detected_occupations == OccupationsSchemeOption.FIXED
        assert detected_convergence == ConvergenceOption.NORMAL
    
    def test_detect_then_apply_round_trip(self, tmp_path):
        """Detect preset then apply should preserve values."""
        step_path = tmp_path / "test.step.yaml"
        
        # Create step with QE params that match a preset
        initial_content = {
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {
                    "nspin": 2,
                    "noncolin": False,
                    "lspinorb": False,
                },
            },
        }
        step_path.write_text(yaml.safe_dump(initial_content))
        
        # Detect presets (use detect_dimension directly)
        from quantumvitas.presets.spaces_registry import detect_dimension
        
        step_content = yaml.safe_load(step_path.read_text())
        step_yaml = step_content.get("parameters", {})
        
        detected_magnetism = detect_dimension("magnetism", step_yaml)
        assert detected_magnetism == MagnetismOption.COLLINEAR_LSDA
        
        # Apply detected preset (should preserve values)
        apply_presets_to_step(
            step_path,
            {"magnetism": detected_magnetism},
            validate_physics=False,
        )
        
        # Read back and verify values preserved
        result_content = yaml.safe_load(step_path.read_text())
        assert result_content["parameters"]["SYSTEM"]["nspin"] == 2
        # Compiler output uses QE string format for booleans (per Fix #1: canonical encoding)
        # step.yaml stores QE strings, not Python bools
        assert result_content["parameters"]["SYSTEM"]["noncolin"] == ".false."


class TestBackwardCompatibility:
    """Test backward compatibility with existing step.yaml files."""
    
    def test_old_step_yaml_still_works(self, tmp_path):
        """Old step.yaml files (QE params only) should still work."""
        step_path = tmp_path / "test.step.yaml"
        
        # Old-style step.yaml with QE params only
        old_content = {
            "step_type": "scf",
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": 50.0,
                    "nspin": 2,
                },
                "ELECTRONS": {
                    "conv_thr": 1e-6,
                },
            },
        }
        step_path.write_text(yaml.safe_dump(old_content))
        
        # Detection should still work (use detect_dimension directly)
        from quantumvitas.presets.spaces_registry import detect_dimension
        
        step_content = yaml.safe_load(step_path.read_text())
        step_yaml = step_content.get("parameters", {})
        
        detected_magnetism = detect_dimension("magnetism", step_yaml)
        # Should detect magnetism
        assert detected_magnetism == MagnetismOption.COLLINEAR_LSDA
        
        # Should be able to apply additional presets
        apply_presets_to_step(
            step_path,
            {"convergence": ConvergenceOption.FAST},
            validate_physics=False,
        )
        
        # Verify old params preserved, new params added
        result_content = yaml.safe_load(step_path.read_text())
        assert result_content["parameters"]["SYSTEM"]["ecutwfc"] == 50.0
        assert result_content["parameters"]["SYSTEM"]["nspin"] == 2
        assert "mixing_beta" in result_content["parameters"]["ELECTRONS"]

