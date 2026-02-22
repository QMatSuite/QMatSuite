"""
Unit tests for PySCF chain registry contract enforcement.

Phase 3C: Tests that registry contract for state dependencies is correctly enforced.
"""

import pytest
from qmatsuite.workflow.registry import get_registry


class TestPySCFRegistryContract:
    """Tests for PySCF registry contract correctness.

    Uses get_for_engine(gen_type, engine) per constitution: registry.get() takes GEN only.
    """

    def test_pyscf_scf_registry_contract(self):
        """PYSCF_SCF has correct registry contract."""
        registry = get_registry()
        spec = registry.get_for_engine("scf", "pyscf")

        assert spec is not None
        assert spec.requires_structure is True, "SCF must require structure to build molecule"
        assert spec.consumes_state is None, "SCF has no dependencies"
        assert spec.produces_state == "mf", "SCF produces mean-field state"

    def test_pyscf_mp2_registry_contract(self):
        """PYSCF_MP2 has correct registry contract (must NOT require structure)."""
        registry = get_registry()
        spec = registry.get_for_engine("mp2", "pyscf")

        assert spec is not None
        assert spec.requires_structure is False, "MP2 must NOT require structure; consumes mf from state"
        assert spec.requires_charge_density is False, "MP2 must NOT require charge density; consumes mf from state"
        assert spec.consumes_state == "mf", "MP2 consumes mean-field state from SCF"
        assert spec.produces_state == "mp2", "MP2 produces mp2 state object (in-memory)"

    def test_pyscf_td_registry_contract(self):
        """PYSCF_TD has correct registry contract."""
        registry = get_registry()
        spec = registry.get_for_engine("td", "pyscf")

        assert spec is not None
        assert spec.requires_structure is False, "TD must NOT require structure; consumes mf from state"
        assert spec.requires_charge_density is False, "TD must NOT require charge density; consumes mf from state"
        assert spec.consumes_state == "mf", "TD consumes mean-field state from SCF"
        assert spec.produces_state is None, "TD does not produce state"
