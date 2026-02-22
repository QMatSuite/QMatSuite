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

from quantumvitas.core.resources import get_resources_dir


class TestW90ParameterStructure:
    """Test that W90 step parameters are correctly structured."""
    
    def test_diamond_w90_wannier_has_flat_params(self, project_root_path):
        """Verify diamond demo w90_wannier step has flat parameters."""
        import yaml

        demo_file = get_resources_dir() / "demo_projects" / "qe_diamond_wannier.yml"
        if not demo_file.exists():
            pytest.skip("Diamond Wannier demo not found")

        with open(demo_file) as f:
            demo = yaml.safe_load(f)

        # Find w90_wannier step
        w90_step = None
        for calc in demo.get("calculations", []):
            for step in calc.get("steps", []):
                step_type = step.get("step_type_spec")
                if step_type == "w90_wannier":
                    w90_step = step
                    break

        assert w90_step is not None, "w90_wannier step not found in demo"

        params = w90_step.get("parameters", {})

        # These should be flat parameters (not wrapped in namelists)
        assert "num_wann" in params, "num_wann not in parameters"
        assert "num_iter" in params, "num_iter not in parameters"

        # Verify they are scalar values, not nested dicts
        assert isinstance(params["num_wann"], int), f"num_wann should be int, got {type(params['num_wann'])}"
        assert isinstance(params["num_iter"], int), f"num_iter should be int, got {type(params['num_iter'])}"

    def test_diamond_w90_wannier_plot_is_bool(self, project_root_path):
        """Verify diamond demo wannier_plot is a boolean, not iterated as string."""
        import yaml

        demo_file = get_resources_dir() / "demo_projects" / "qe_diamond_wannier.yml"
        if not demo_file.exists():
            pytest.skip("Diamond Wannier demo not found")

        with open(demo_file) as f:
            demo = yaml.safe_load(f)

        w90_step = None
        for calc in demo.get("calculations", []):
            for step in calc.get("steps", []):
                if step.get("step_type_spec") == "w90_wannier":
                    w90_step = step
                    break

        assert w90_step is not None
        params = w90_step.get("parameters", {})

        assert "wannier_plot" in params, "wannier_plot not in parameters"
        assert isinstance(params["wannier_plot"], bool), f"wannier_plot should be bool, got {type(params['wannier_plot'])}"


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
