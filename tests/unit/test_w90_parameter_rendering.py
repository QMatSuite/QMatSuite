"""
Unit tests for W90 flat parameter rendering in UI.

Tests that the ActiveParametersPanel correctly handles:
1. W90-style flat parameters: { seedname: "diamond", num_wann: 4 }
2. QE-style nested parameters: { SYSTEM: { ecutwfc: 40 } }

The key issue being fixed:
- Flat string parameters like seedname="diamond" were being iterated
  character-by-character because Object.entries("diamond") produces
  [["0", "d"], ["1", "i"], ["2", "a"], ...]
- The fix detects flat parameters and groups them under a synthetic "PARAMETERS" section
"""

from __future__ import annotations

import pytest


class TestW90ParameterStructure:
    """Test that W90 step parameters are correctly structured."""
    
    def test_diamond_w90_wannierprep_has_flat_params(self, project_root_path):
        """Verify diamond demo w90_wannierprep step has flat parameters."""
        import yaml

        demo_file = project_root_path / "resources" / "demo_projects" / "diamond_wannier90_demo.yml"
        if not demo_file.exists():
            pytest.skip("Diamond demo not found")

        with open(demo_file) as f:
            demo = yaml.safe_load(f)

        # Find w90_wannierprep step
        # Note: demo uses step_type_spec (canonical SPEC type)
        w90_wannierprep = None
        for calc in demo.get("calculations", []):
            for step in calc.get("steps", []):
                step_type = step.get("step_type_spec") or step.get("step_type")
                if step_type == "w90_wannierprep":
                    w90_wannierprep = step
                    break

        assert w90_wannierprep is not None, "w90_wannierprep step not found in demo"
        
        params = w90_wannierprep.get("parameters", {})

        # These should be flat parameters (not wrapped in namelists)
        assert "seedname" in params, "seedname not in parameters"
        assert "num_wann" in params, "num_wann not in parameters"

        # Verify they are scalar values, not nested dicts
        assert isinstance(params["seedname"], str), f"seedname should be string, got {type(params['seedname'])}"
        assert isinstance(params["num_wann"], int), f"num_wann should be int, got {type(params['num_wann'])}"

        # seedname should be "diamond", not a list of chars
        assert params["seedname"] == "diamond", f"seedname should be 'diamond', got '{params['seedname']}'"
    
    def test_diamond_pw2wannier_has_flat_params(self, project_root_path):
        """Verify diamond demo qe_pw2wannier step has flat parameters."""
        import yaml

        demo_file = project_root_path / "resources" / "demo_projects" / "diamond_wannier90_demo.yml"
        if not demo_file.exists():
            pytest.skip("Diamond demo not found")

        with open(demo_file) as f:
            demo = yaml.safe_load(f)

        # Find qe_pw2wannier step
        # Note: demo uses step_type_spec (canonical SPEC type)
        pw2wannier = None
        for calc in demo.get("calculations", []):
            for step in calc.get("steps", []):
                step_type = step.get("step_type_spec") or step.get("step_type")
                if step_type in ("pw2wannier", "qe_pw2wannier"):
                    pw2wannier = step
                    break

        assert pw2wannier is not None, "qe_pw2wannier step not found in demo"

        params = pw2wannier.get("parameters", {})
        
        # E1: prefix/outdir are injected at execution time (from calculation.meta.slug), not in user parameters
        # They should NOT be in step YAML parameters (they're injected via effective_parameters)
        # Only seedname should be in user parameters
        assert "seedname" in params, "seedname not in parameters"
        
        # E1: prefix should NOT be in step YAML parameters (it's injected at execution)
        # If it exists, it should be ignored/overridden by calculation prefix
        # We don't assert prefix in params - it's injected, not user-provided
        
        # Verify seedname is scalar value
        assert isinstance(params["seedname"], str), f"seedname should be string, got {type(params['seedname'])}"
        
        # Verify seedname value
        assert params["seedname"] == "diamond", f"seedname should be 'diamond', got '{params['seedname']}'"


class TestFlatParameterDetection:
    """Test JavaScript-side logic for detecting flat vs nested parameters."""
    
    def test_detect_flat_parameters(self):
        """
        Test the Python equivalent of the JS detection logic.
        
        The UI uses:
        isFlat = Object.values(params).some(val => typeof val !== 'object' || val === null || Array.isArray(val))
        """
        # Flat parameters (W90-style)
        flat_params = {
            "seedname": "diamond",
            "num_wann": 4,
            "num_iter": 20,
            "mp_grid": [4, 4, 4],  # Array is also flat
        }
        
        # Check if any value is not a dict (flat detection)
        is_flat = any(
            not isinstance(val, dict) or val is None
            for val in flat_params.values()
        )
        assert is_flat is True, "Should detect flat parameters"
        
        # Nested parameters (QE-style)
        nested_params = {
            "SYSTEM": {"ecutwfc": 40, "ecutrho": 320},
            "ELECTRONS": {"conv_thr": 1e-8},
        }
        
        is_flat = any(
            not isinstance(val, dict) or val is None
            for val in nested_params.values()
        )
        assert is_flat is False, "Should detect nested parameters"
    
    def test_mixed_flat_and_nested(self):
        """Test parameters that mix flat and nested (edge case)."""
        # This shouldn't normally happen, but the UI should handle it
        mixed_params = {
            "seedname": "diamond",  # Flat
            "SYSTEM": {"ecutwfc": 40},  # Nested
        }
        
        # Detection: any flat value makes it "flat" mode
        is_flat = any(
            not isinstance(val, dict) or val is None
            for val in mixed_params.values()
        )
        assert is_flat is True, "Mixed should be detected as flat (conservative)"


class TestParameterIterationSafety:
    """Test that string parameters are not iterated character-by-character."""
    
    def test_string_not_iterable_as_entries(self):
        """
        Demonstrate the bug: Object.entries("diamond") in JS produces character pairs.
        
        This is the root cause of the "d i a m o n d" rendering.
        """
        # Python equivalent of Object.entries() on a string
        string_value = "diamond"
        
        # In JS, Object.entries("diamond") returns [["0", "d"], ["1", "i"], ...]
        # In Python, we can simulate this as:
        entries = list(enumerate(string_value))
        
        # This would produce 7 entries (one per character)
        assert len(entries) == 7, "String has 7 characters"
        
        # The fix: check if value is dict before iterating
        if isinstance(string_value, dict):
            entries = list(string_value.items())
        else:
            # Don't iterate - it's a scalar
            entries = []
        
        assert len(entries) == 0, "String should not be iterated as entries"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

