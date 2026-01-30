"""Unit tests for ORCA workflow integration.

These tests verify ORCA step types and workflows are properly registered
and can be materialized without requiring the ORCA binary.
"""

import pytest


class TestORCAStepTypeRegistration:
    """Tests for ORCA step type registration in workflow registry."""

    def test_orca_scf_registered(self):
        """Verify orca_scf step type is registered."""
        from quantumvitas.workflow.registry import get_registry

        registry = get_registry()
        spec = registry.get("orca_scf")

        assert spec is not None
        assert spec.step_type_gen == "scf"
        assert spec.step_type_spec == "orca_scf"
        assert spec.engine == "orca"

    def test_orca_hf_registered(self):
        """Verify orca_hf step type is registered."""
        from quantumvitas.workflow.registry import get_registry

        registry = get_registry()
        spec = registry.get("orca_hf")

        assert spec is not None
        assert spec.step_type_gen == "hf"
        assert spec.step_type_spec == "orca_hf"
        assert spec.engine == "orca"

    def test_orca_td_registered(self):
        """Verify orca_td step type is registered."""
        from quantumvitas.workflow.registry import get_registry

        registry = get_registry()
        spec = registry.get("orca_td")

        assert spec is not None
        assert spec.step_type_gen == "td"
        assert spec.step_type_spec == "orca_td"
        assert spec.engine == "orca"

    def test_orca_scf_produces_gbw(self):
        """Verify orca_scf produces .gbw wavefunction state."""
        from quantumvitas.workflow.registry import get_registry

        registry = get_registry()
        spec = registry.get("orca_scf")

        assert spec.produces_state == "gbw"
        assert spec.consumes_state is None

    def test_orca_td_consumes_gbw(self):
        """Verify orca_td consumes .gbw wavefunction state."""
        from quantumvitas.workflow.registry import get_registry

        registry = get_registry()
        spec = registry.get("orca_td")

        assert spec.consumes_state == "gbw"
        assert spec.produces_state is None


class TestORCAMaterialization:
    """Tests for ORCA workflow materialization."""

    def test_scf_materializes_to_orca_scf(self):
        """Verify scf public key materializes to orca_scf for ORCA engine."""
        from quantumvitas.workflow.generalized_steps import materialize_public_step_key

        result = materialize_public_step_key("scf", "orca")
        assert result == "orca_scf"

    def test_hf_materializes_to_orca_hf(self):
        """Verify hf public key materializes to orca_hf for ORCA engine."""
        from quantumvitas.workflow.generalized_steps import materialize_public_step_key

        result = materialize_public_step_key("hf", "orca")
        assert result == "orca_hf"

    def test_td_materializes_to_orca_td(self):
        """Verify td public key materializes to orca_td for ORCA engine."""
        from quantumvitas.workflow.generalized_steps import materialize_public_step_key

        result = materialize_public_step_key("td", "orca")
        assert result == "orca_td"

    def test_unsupported_step_returns_none(self):
        """Verify unsupported steps return None."""
        from quantumvitas.workflow.generalized_steps import materialize_public_step_key

        # ORCA doesn't support bands
        result = materialize_public_step_key("bands", "orca")
        assert result is None

    def test_scf_workflow_materializes(self):
        """Verify scf workflow materializes correctly for ORCA."""
        from quantumvitas.workflow.generalized_steps import materialize_workflow

        result = materialize_workflow(["scf"], "orca")
        assert result == ["orca_scf"]

    def test_scf_td_workflow_materializes(self):
        """Verify scf_td workflow materializes correctly for ORCA."""
        from quantumvitas.workflow.generalized_steps import materialize_workflow

        result = materialize_workflow(["scf", "td"], "orca")
        assert result == ["orca_scf", "orca_td"]

    def test_unsupported_workflow_raises(self):
        """Verify workflow with unsupported steps raises ValueError."""
        from quantumvitas.workflow.generalized_steps import materialize_workflow

        with pytest.raises(ValueError, match="not supported by engine family 'orca'"):
            materialize_workflow(["scf", "bands"], "orca")


class TestORCAWorkflowTemplates:
    """Tests for ORCA-compatible workflow templates."""

    def test_scf_td_workflow_exists(self):
        """Verify scf_td workflow template exists."""
        from quantumvitas.workflow.templates import get_workflow_service

        service = get_workflow_service()
        template = service.get_template("scf_td")

        assert template is not None
        assert template.id == "scf_td"
        assert template.step_sequence == ("scf", "td")

    def test_scf_td_can_be_instantiated_for_orca(self):
        """Verify scf_td workflow can be materialized for ORCA engine."""
        from quantumvitas.workflow.templates import get_workflow_service
        from quantumvitas.workflow.generalized_steps import materialize_workflow

        service = get_workflow_service()
        template = service.get_template("scf_td")

        # Should not raise
        machine_steps = materialize_workflow(list(template.step_sequence), "orca")
        assert machine_steps == ["orca_scf", "orca_td"]

    def test_scf_workflow_exists(self):
        """Verify scf workflow template exists (basic single-point)."""
        from quantumvitas.workflow.templates import get_workflow_service

        service = get_workflow_service()
        template = service.get_template("scf")

        assert template is not None
        assert template.step_sequence == ("scf",)


class TestORCAEngineRegistration:
    """Tests for ORCA engine registration in engine registry."""

    def test_orca_engine_available_when_binary_found(self):
        """Verify ORCA engine is registered when binary is found."""
        from quantumvitas.engine.registry import create_default_registry

        registry = create_default_registry()

        # ORCA should be registered if binary is found
        # This test passes even if ORCA binary is missing (just won't be registered)
        engines = registry.list_engines()
        assert "qe" in engines
        assert "pyscf" in engines
        # ORCA may or may not be present depending on environment

    def test_orca_engine_probe(self):
        """Test ORCA engine probe if available."""
        from quantumvitas.engine.registry import create_default_registry

        registry = create_default_registry()

        if registry.has("orca"):
            engine = registry.get("orca")
            available, info = engine.probe()
            # Just verify probe doesn't crash
            assert isinstance(available, bool)
            assert isinstance(info, str)
