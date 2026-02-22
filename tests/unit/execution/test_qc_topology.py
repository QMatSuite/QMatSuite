"""
Unit tests for QC topology verification.

Tests that verify_qc_topology() correctly identifies valid and invalid
topologies for QC engines (ORCA/PySCF) with relax steps.
"""

import pytest
from unittest.mock import MagicMock
from qmatsuite.execution.recipes import verify_qc_topology, TopologyError
from qmatsuite.workflow.registry import get_registry


class TestQCTopologyVerification:
    """Test QC topology verification logic."""

    def test_qc_topo_verify_scf_then_tddft_valid(self):
        """Valid topology: scf → tddft (no relax blocking)."""
        registry = get_registry()
        
        # Create mock steps
        scf_step = MagicMock()
        scf_step.step_type_gen = "scf"
        scf_step.step_type_spec= "orca_scf"
        scf_step.name = "scf"
        
        tddft_step = MagicMock()
        tddft_step.step_type_gen = "td"
        tddft_step.step_type_spec= "orca_td"
        tddft_step.name = "tddft"
        
        steps = [scf_step, tddft_step]
        
        # Should not raise
        verify_qc_topology(steps, registry)

    def test_qc_topo_verify_scf_relax_scf_mp2_valid(self):
        """Valid topology: scf → tddft → relax → scf → mp2 (relax is standalone)."""
        registry = get_registry()
        
        scf1 = MagicMock()
        scf1.step_type_gen = "scf"
        scf1.step_type_spec= "orca_scf"
        scf1.name = "scf1"
        
        tddft = MagicMock()
        tddft.step_type_gen = "td"
        tddft.step_type_spec= "orca_td"
        tddft.name = "tddft"
        
        relax = MagicMock()
        relax.step_type_gen = "relax"
        relax.step_type_spec= "qe_relax"
        relax.name = "relax"
        
        scf2 = MagicMock()
        scf2.step_type_gen = "scf"
        scf2.step_type_spec= "orca_scf"
        scf2.name = "scf2"
        
        mp2 = MagicMock()
        mp2.step_type_gen = "mp2"
        mp2.step_type_spec= "orca_mp2"
        mp2.name = "mp2"
        
        steps = [scf1, tddft, relax, scf2, mp2]
        
        # Should not raise
        verify_qc_topology(steps, registry)

    def test_qc_topo_verify_scf_relax_tddft_invalid(self):
        """Invalid topology: scf → relax → tddft (tddft blocked by relax)."""
        registry = get_registry()
        
        scf = MagicMock()
        scf.step_type_gen = "scf"
        scf.step_type_spec= "orca_scf"
        scf.name = "scf"
        
        relax = MagicMock()
        relax.step_type_gen = "relax"
        relax.step_type_spec= "qe_relax"
        relax.name = "relax"
        
        tddft = MagicMock()
        tddft.step_type_gen = "td"
        tddft.step_type_spec= "orca_td"
        tddft.name = "tddft"
        
        steps = [scf, relax, tddft]
        
        # Should raise TopologyError
        with pytest.raises(TopologyError) as exc_info:
            verify_qc_topology(steps, registry)
        
        error_msg = str(exc_info.value)
        assert "blocks the dependency chain" in error_msg or "blocked by relax" in error_msg
        assert "tddft" in error_msg or "index 2" in error_msg

    def test_qc_topo_verify_relax_tddft_invalid(self):
        """Invalid topology: relax → tddft (tddft has no SCF root)."""
        registry = get_registry()
        
        relax = MagicMock()
        relax.step_type_gen = "relax"
        relax.step_type_spec= "qe_relax"
        relax.name = "relax"
        
        tddft = MagicMock()
        tddft.step_type_gen = "td"
        tddft.step_type_spec= "orca_td"
        tddft.name = "tddft"
        
        steps = [relax, tddft]
        
        # Should raise TopologyError
        with pytest.raises(TopologyError) as exc_info:
            verify_qc_topology(steps, registry)
        
        error_msg = str(exc_info.value)
        assert "requires SCF root" in error_msg or "blocks the dependency chain" in error_msg
        assert "tddft" in error_msg or "index 1" in error_msg

    def test_qc_topo_verify_scf_mp2_relax_scf_relax_mp2_invalid(self):
        """Invalid topology: scf → mp2 → relax → scf → relax → mp2 (last mp2 blocked)."""
        registry = get_registry()
        
        scf1 = MagicMock()
        scf1.step_type_gen = "scf"
        scf1.step_type_spec= "orca_scf"
        scf1.name = "scf1"
        
        mp2_1 = MagicMock()
        mp2_1.step_type_gen = "mp2"
        mp2_1.step_type_spec= "orca_mp2"
        mp2_1.name = "mp2_1"
        
        relax1 = MagicMock()
        relax1.step_type_gen = "relax"
        relax1.step_type_spec= "qe_relax"
        relax1.name = "relax1"
        
        scf2 = MagicMock()
        scf2.step_type_gen = "scf"
        scf2.step_type_spec= "orca_scf"
        scf2.name = "scf2"
        
        relax2 = MagicMock()
        relax2.step_type_gen = "relax"
        relax2.step_type_spec= "qe_relax"
        relax2.name = "relax2"
        
        mp2_2 = MagicMock()
        mp2_2.step_type_gen = "mp2"
        mp2_2.step_type_spec= "orca_mp2"
        mp2_2.name = "mp2_2"
        
        steps = [scf1, mp2_1, relax1, scf2, relax2, mp2_2]
        
        # Should raise TopologyError
        with pytest.raises(TopologyError) as exc_info:
            verify_qc_topology(steps, registry)
        
        error_msg = str(exc_info.value)
        assert "blocks the dependency chain" in error_msg or "blocked by relax" in error_msg
        assert "mp2_2" in error_msg or "index 5" in error_msg

    def test_qc_topo_verify_relax_standalone_valid(self):
        """Valid topology: relax alone (standalone chain)."""
        registry = get_registry()
        
        relax = MagicMock()
        relax.step_type_gen = "relax"
        relax.step_type_spec= "qe_relax"
        relax.name = "relax"
        
        steps = [relax]
        
        # Should not raise
        verify_qc_topology(steps, registry)

    def test_qc_topo_verify_scf_mp2_relax_valid(self):
        """Valid topology: scf → mp2 → relax (relax is standalone)."""
        registry = get_registry()
        
        scf = MagicMock()
        scf.step_type_gen = "scf"
        scf.step_type_spec= "orca_scf"
        scf.name = "scf"
        
        mp2 = MagicMock()
        mp2.step_type_gen = "mp2"
        mp2.step_type_spec= "orca_mp2"
        mp2.name = "mp2"
        
        relax = MagicMock()
        relax.step_type_gen = "relax"
        relax.step_type_spec= "qe_relax"
        relax.name = "relax"
        
        steps = [scf, mp2, relax]
        
        # Should not raise
        verify_qc_topology(steps, registry)

    def test_qc_topo_verify_relax_scf_tddft_valid(self):
        """Valid topology: relax → scf → tddft (relax standalone, scf starts new chain)."""
        registry = get_registry()
        
        relax = MagicMock()
        relax.step_type_gen = "relax"
        relax.step_type_spec= "qe_relax"
        relax.name = "relax"
        
        scf = MagicMock()
        scf.step_type_gen = "scf"
        scf.step_type_spec= "orca_scf"
        scf.name = "scf"
        
        tddft = MagicMock()
        tddft.step_type_gen = "td"
        tddft.step_type_spec= "orca_td"
        tddft.name = "tddft"
        
        steps = [relax, scf, tddft]
        
        # Should not raise
        verify_qc_topology(steps, registry)

    def test_qc_topo_verify_scf_scf_tddft_valid(self):
        """Valid topology: scf → scf → tddft (second scf starts new chain)."""
        registry = get_registry()
        
        scf1 = MagicMock()
        scf1.step_type_gen = "scf"
        scf1.step_type_spec= "orca_scf"
        scf1.name = "scf1"
        
        scf2 = MagicMock()
        scf2.step_type_gen = "scf"
        scf2.step_type_spec= "orca_scf"
        scf2.name = "scf2"
        
        tddft = MagicMock()
        tddft.step_type_gen = "td"
        tddft.step_type_spec= "orca_td"
        tddft.name = "tddft"
        
        steps = [scf1, scf2, tddft]
        
        # Should not raise
        verify_qc_topology(steps, registry)

