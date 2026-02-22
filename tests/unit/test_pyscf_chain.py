"""
Unit tests for PySCF dependency chain resolution.

Phase 3C: Tests for linear dependency model with nearest-provider rule.
"""

import pytest
from qmatsuite.engines.pyscf.chain import resolve_dependency_chain
from qmatsuite.workflow.registry import get_registry


class TestDependencyChainResolution:
    """Tests for dependency chain resolution."""
    
    def test_scf_only_chain(self):
        """SCF step with no dependencies returns just itself."""
        registry = get_registry()
        steps = [
            ("ulid-scf-1", "pyscf_scf"),
        ]
        
        chain_indices, error = resolve_dependency_chain(
            "ulid-scf-1",
            steps,
            registry,
        )
        
        assert error is None
        assert chain_indices == [0]
    
    def test_mp2_resolves_to_scf(self):
        """MP2 step resolves to SCF provider."""
        registry = get_registry()
        steps = [
            ("ulid-scf-1", "pyscf_scf"),
            ("ulid-mp2-1", "pyscf_mp2"),
        ]
        
        chain_indices, error = resolve_dependency_chain(
            "ulid-mp2-1",
            steps,
            registry,
        )
        
        assert error is None
        assert chain_indices == [0, 1]  # SCF then MP2
    
    def test_td_resolves_to_scf(self):
        """TD step resolves to SCF provider."""
        registry = get_registry()
        steps = [
            ("ulid-scf-1", "pyscf_scf"),
            ("ulid-td-1", "pyscf_td"),
        ]
        
        chain_indices, error = resolve_dependency_chain(
            "ulid-td-1",
            steps,
            registry,
        )
        
        assert error is None
        assert chain_indices == [0, 1]  # SCF then TD
    
    def test_missing_provider_error(self):
        """Missing provider returns error."""
        registry = get_registry()
        steps = [
            ("ulid-mp2-1", "pyscf_mp2"),  # MP2 requires SCF, but no SCF before it
        ]
        
        chain_indices, error = resolve_dependency_chain(
            "ulid-mp2-1",
            steps,
            registry,
        )
        
        assert error is not None
        assert "No provider found" in error
        assert "mf" in error
        assert chain_indices == []
    
    def test_nearest_provider_rule(self):
        """Post step binds to nearest left SCF (not furthest)."""
        registry = get_registry()
        steps = [
            ("ulid-scf-1", "pyscf_scf"),
            ("ulid-scf-2", "pyscf_scf"),  # Second SCF
            ("ulid-mp2-1", "pyscf_mp2"),  # Should bind to scf-2 (nearest left)
        ]
        
        chain_indices, error = resolve_dependency_chain(
            "ulid-mp2-1",
            steps,
            registry,
        )
        
        assert error is None
        # Should resolve to scf-2 (index 1), not scf-1 (index 0)
        assert chain_indices == [1, 2]  # scf-2 then mp2
    
    def test_target_not_found_error(self):
        """Target step not found returns error."""
        registry = get_registry()
        steps = [
            ("ulid-scf-1", "pyscf_scf"),
        ]
        
        chain_indices, error = resolve_dependency_chain(
            "ulid-nonexistent",
            steps,
            registry,
        )
        
        assert error is not None
        assert "not found" in error.lower()
        assert chain_indices == []
    
    def test_unknown_step_type_error(self):
        """Unknown step type in list returns error."""
        registry = get_registry()
        steps = [
            ("ulid-unknown", "unknown_step_type"),
        ]
        
        chain_indices, error = resolve_dependency_chain(
            "ulid-unknown",
            steps,
            registry,
        )
        
        assert error is not None
        assert "not found in registry" in error or "not found" in error.lower()

