"""
Tests for Phase 3B: Workflow materialization by engine_family (QE-only).

Tests verify:
- QE family mapping correctness: PUBLIC templates -> MACHINE materialization list
- Unsupported family mapping: returns errors (no crash)
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from quantumvitas.workflow.generalized_steps import (
    materialize_public_step_key,
    materialize_workflow,
)
from quantumvitas.workflow.templates import get_workflow_service


class TestQEFamilyMaterialization:
    """Test QE family mapping correctness: PUBLIC templates -> MACHINE materialization."""
    
    def test_scf_materializes_to_qe_scf(self):
        """PUBLIC key 'scf' materializes to 'qe_scf' for QE family."""
        result = materialize_public_step_key("scf", "qe")
        assert result == "qe_scf"
    
    def test_nscf_materializes_to_qe_nscf(self):
        """PUBLIC key 'nscf' materializes to 'qe_nscf' for QE family."""
        result = materialize_public_step_key("nscf", "qe")
        assert result == "qe_nscf"
    
    def test_dos_materializes_to_qe_dos(self):
        """PUBLIC key 'dos' materializes to 'qe_dos' for QE family."""
        result = materialize_public_step_key("dos", "qe")
        assert result == "qe_dos"
    
    def test_bands_pw_materializes_to_qe_bands_pw(self):
        """PUBLIC key 'bands_pw' materializes to 'qe_bands_pw' for QE family."""
        result = materialize_public_step_key("bands_pw", "qe")
        assert result == "qe_bands_pw"
    
    def test_bands_materializes_to_qe_bands(self):
        """PUBLIC key 'bands' materializes to 'qe_bands' for QE family."""
        result = materialize_public_step_key("bands", "qe")
        assert result == "qe_bands"
    
    def test_pw2wannier90_materializes_to_qe_pw2wannier90(self):
        """PUBLIC key 'pw2wannier90' materializes to 'qe_pw2wannier90' for QE family."""
        result = materialize_public_step_key("pw2wannier90", "qe")
        assert result == "qe_pw2wannier90"
    
    def test_workflow_template_scf_materializes(self):
        """Workflow template 'scf' materializes correctly for QE family."""
        result = materialize_workflow(["scf"], "qe")
        assert result == ["qe_scf"]
    
    def test_workflow_template_dos_materializes(self):
        """Workflow template 'dos' (scf, nscf, dos) materializes correctly for QE family."""
        result = materialize_workflow(["scf", "nscf", "dos"], "qe")
        assert result == ["qe_scf", "qe_nscf", "qe_dos"]
    
    def test_workflow_template_bands_materializes(self):
        """Workflow template 'bands' (scf, bands_pw, bands) materializes correctly for QE family."""
        result = materialize_workflow(["scf", "bands_pw", "bands"], "qe")
        assert result == ["qe_scf", "qe_bands_pw", "qe_bands"]
    
    def test_workflow_template_wannier_materializes(self):
        """Workflow template 'wannier' materializes correctly for QE family."""
        result = materialize_workflow(["scf", "nscf", "pw2wannier90", "w90_run"], "qe")
        assert result == ["qe_scf", "qe_nscf", "qe_pw2wannier90", "w90_run"]
    
    def test_zero_one_mapping_invariant(self):
        """Each PUBLIC step key maps to at most one MACHINE step type for QE family (0-1 rule)."""
        # Test that each PUBLIC key maps to exactly one MACHINE type or None
        public_keys = ["scf", "nscf", "dos", "bands_pw", "bands", "pw2wannier90", "w90_run"]
        for public_key in public_keys:
            result = materialize_public_step_key(public_key, "qe")
            # Result should be a single machine type string or None (not a list)
            assert result is None or isinstance(result, str)
            if result is not None:
                # Should start with engine prefix
                assert result.startswith(("qe_", "w90_"))


class TestUnsupportedFamilyMaterialization:
    """Test unsupported family mapping: returns errors (no crash)."""
    
    def test_unsupported_family_returns_none(self):
        """Unsupported family returns None (not an error, but materialization will fail)."""
        result = materialize_public_step_key("scf", "vasp")
        assert result is None
    
    def test_unsupported_family_workflow_raises_error(self):
        """Materialization of unsupported family raises ValueError (no crash)."""
        with pytest.raises(ValueError, match="not supported"):
            materialize_workflow(["scf"], "vasp")
    
    def test_mixed_supported_unsupported_workflow_raises_error(self):
        """Materialization fails if any step is unsupported (no partial materialization)."""
        with pytest.raises(ValueError, match="not supported"):
            materialize_workflow(["scf", "nscf"], "vasp")
    
    def test_pyscf_only_scf_supported(self):
        """PySCF family only supports SCF currently."""
        result = materialize_public_step_key("scf", "pyscf")
        assert result == "pyscf_scf"
        
        # Other steps should return None
        result = materialize_public_step_key("nscf", "pyscf")
        assert result is None
        
        result = materialize_public_step_key("dos", "pyscf")
        assert result is None
    
    def test_pyscf_workflow_with_unsupported_raises_error(self):
        """PySCF workflow with unsupported steps raises error."""
        # SCF alone works
        result = materialize_workflow(["scf"], "pyscf")
        assert result == ["pyscf_scf"]
        
        # DOS workflow fails (includes unsupported steps)
        with pytest.raises(ValueError, match="not supported"):
            materialize_workflow(["scf", "nscf", "dos"], "pyscf")

