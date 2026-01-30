"""Unit tests for reference SCF resolver."""

import pytest
from quantumvitas.execution.reference_resolver import find_reference_scf, get_gen_type
from quantumvitas.workflow.registry import get_registry


class MockStep:
    """Mock step for testing."""
    def __init__(self, step_type: str, public_type: str = None):
        self.step_type_spec = step_type  # SPEC type (e.g., "vasp_scf")
        self.step_type_gen = public_type or step_type.split("_", 1)[-1] if "_" in step_type else step_type
        # For compatibility with find_reference_scf which checks step_type or public_type
        self.step_type = step_type
        self.public_type = self.step_type_gen


class TestReferenceSCFResolver:
    """Test reference SCF resolver logic."""
    
    def test_find_reference_scf_simple(self):
        """Test finding SCF in simple topology: scf → bands."""
        steps = [
            MockStep("vasp_scf", "scf"),
            MockStep("vasp_bands", "bands"),
        ]
        
        result = find_reference_scf(steps, current_step_idx=1)
        assert result is not None
        idx, step = result
        assert idx == 0
        assert step.step_type_spec == "vasp_scf"
    
    def test_find_reference_scf_with_relax_barrier(self):
        """Test relax barrier: scf_1 → relax → scf_2 → bands."""
        steps = [
            MockStep("vasp_scf", "scf"),      # idx 0
            MockStep("vasp_relax", "relax"),   # idx 1 (barrier)
            MockStep("vasp_scf", "scf"),       # idx 2
            MockStep("vasp_bands", "bands"),   # idx 3
        ]
        
        # For bands (idx 3), should find scf_2 (idx 2), not scf_1 (idx 0)
        result = find_reference_scf(steps, current_step_idx=3)
        assert result is not None
        idx, step = result
        assert idx == 2
        assert step.step_type_spec == "vasp_scf"
    
    def test_find_reference_scf_no_scf_before(self):
        """Test when no SCF exists before current step."""
        steps = [
            MockStep("vasp_bands", "bands"),
        ]
        
        result = find_reference_scf(steps, current_step_idx=0)
        assert result is None
    
    def test_find_reference_scf_blocked_by_relax(self):
        """Test when all SCF steps are blocked by relax."""
        steps = [
            MockStep("vasp_scf", "scf"),      # idx 0
            MockStep("vasp_relax", "relax"),   # idx 1 (barrier)
            MockStep("vasp_bands", "bands"),  # idx 2
        ]
        
        # For bands (idx 2), should find None (scf_1 blocked by relax)
        result = find_reference_scf(steps, current_step_idx=2)
        assert result is None
    
    def test_find_reference_scf_multiple_scf(self):
        """Test finding most recent SCF when multiple exist."""
        steps = [
            MockStep("vasp_scf", "scf"),      # idx 0
            MockStep("vasp_nscf", "nscf"),     # idx 1
            MockStep("vasp_scf", "scf"),       # idx 2
            MockStep("vasp_bands", "bands"),   # idx 3
        ]
        
        # For bands (idx 3), should find most recent scf (idx 2)
        result = find_reference_scf(steps, current_step_idx=3)
        assert result is not None
        idx, step = result
        assert idx == 2
    
    def test_get_gen_type(self):
        """Test get_gen_type helper."""
        registry = get_registry()
        
        step = MockStep("vasp_scf", "scf")
        gen_type = get_gen_type(step, registry)
        assert gen_type == "scf"
        
        step = MockStep("vasp_relax", "relax")
        gen_type = get_gen_type(step, registry)
        assert gen_type == "relax"
        
        step = MockStep("vasp_bands", "bands")
        gen_type = get_gen_type(step, registry)
        assert gen_type == "bands"







