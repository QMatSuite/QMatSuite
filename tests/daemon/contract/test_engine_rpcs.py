"""RPC contract tests for engine management endpoints."""

import pytest
from quantumvitas.daemon.server import QVDaemon
from .conftest import send_request


class TestListEngineFamilies:
    """Contract tests for list_engine_families RPC."""

    def test_list_engine_families_happy_path(self, daemon: QVDaemon):
        """list_engine_families returns all 15 engines."""
        response = send_request(daemon, "list_engine_families", {})

        assert "engines" in response
        engines = response["engines"]
        assert isinstance(engines, list)
        assert len(engines) >= 15  # QE, VASP, ORCA, LAMMPS, etc.

        # Validate schema matches TypeScript EngineFamilyInfo
        for engine in engines:
            assert "engine_family" in engine
            assert "display_name" in engine
            assert "supported_gen_steps" in engine

    def test_list_engine_families_includes_qe(self, daemon: QVDaemon):
        """list_engine_families includes qe engine."""
        response = send_request(daemon, "list_engine_families", {})
        engine_names = [e["engine_family"] for e in response["engines"]]
        assert "qe" in engine_names


class TestSetEngineFamily:
    """Contract tests for set_engine_family RPC."""

    def test_set_engine_family_immutable(self, demo_project_with_calculation, daemon: QVDaemon):
        """set_engine_family errors when trying to change immutable engine."""
        project_root, _, calc_ulid = demo_project_with_calculation

        # Engine family is immutable after creation - should error
        with pytest.raises(RuntimeError) as exc_info:
            send_request(daemon, "set_engine_family", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "engine_family": "vasp"
            })
        
        assert "immutable" in str(exc_info.value).lower()

    def test_set_engine_family_invalid_engine(self, demo_project_with_calculation, daemon: QVDaemon):
        """set_engine_family errors on unknown engine."""
        project_root, _, calc_ulid = demo_project_with_calculation

        with pytest.raises(RuntimeError):
            send_request(daemon, "set_engine_family", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "engine_family": "nonexistent_engine"
            })
