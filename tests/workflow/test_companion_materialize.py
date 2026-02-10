"""
Integration tests for companion allowlist materialization.

Verifies that materialize_public_step_key and materialize_workflow
use the companion allowlist correctly.
"""
import pytest

from quantumvitas.workflow.generalized_steps import (
    materialize_public_step_key,
    materialize_workflow,
    get_supported_generalized_steps,
)


class TestMaterializePublicStepKey:
    """Test materialize_public_step_key with companion routing."""

    def test_base_step_qe(self):
        assert materialize_public_step_key("scf", "qe") == "qe_scf"

    def test_base_step_vasp(self):
        assert materialize_public_step_key("scf", "vasp") == "vasp_scf"

    def test_companion_step_w90_via_qe(self):
        """W90 steps resolve through QE's companion allowlist."""
        assert materialize_public_step_key("wannierprep", "qe") == "w90_wannierprep"
        assert materialize_public_step_key("wannier", "qe") == "w90_wannier"

    def test_companion_step_qmcpack_via_qe(self):
        """QMCPACK steps resolve through QE's companion allowlist."""
        assert materialize_public_step_key("vmc", "qe") == "qmcpack_vmc"
        assert materialize_public_step_key("dmc", "qe") == "qmcpack_dmc"

    def test_companion_step_yambo_via_qe(self):
        """Yambo steps resolve through QE's companion allowlist."""
        result = materialize_public_step_key("setup", "qe")
        assert result == "yambo_setup"

    def test_companion_step_not_on_vasp(self):
        """VASP has no companions — postproc steps return None."""
        assert materialize_public_step_key("wannierprep", "vasp") is None
        assert materialize_public_step_key("vmc", "vasp") is None

    def test_unsupported_step(self):
        """Unknown gen step returns None."""
        assert materialize_public_step_key("nonexistent_step", "qe") is None

    def test_case_insensitive(self):
        """Gen step names are case-insensitive."""
        assert materialize_public_step_key("SCF", "qe") == "qe_scf"
        assert materialize_public_step_key("Scf", "vasp") == "vasp_scf"


class TestMaterializeWorkflow:
    """Test materialize_workflow with companion routing."""

    def test_qe_basic_workflow(self):
        result = materialize_workflow(["scf", "nscf", "dos"], "qe")
        assert result == ["qe_scf", "qe_nscf", "qe_dos"]

    def test_qe_with_companion_steps(self):
        """QE workflow with W90 companion steps."""
        result = materialize_workflow(["scf", "nscf", "wannierprep", "wannier"], "qe")
        assert result == ["qe_scf", "qe_nscf", "w90_wannierprep", "w90_wannier"]

    def test_vasp_basic_workflow(self):
        result = materialize_workflow(["scf", "nscf", "relax"], "vasp")
        assert result == ["vasp_scf", "vasp_nscf", "vasp_relax"]

    def test_unsupported_step_raises(self):
        """Unsupported step (not in base or companions, not zero-mapped) raises."""
        with pytest.raises(ValueError, match="not supported"):
            materialize_workflow(["scf", "nonexistent"], "qe")



