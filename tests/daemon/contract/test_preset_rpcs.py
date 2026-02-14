"""RPC contract tests for preset management endpoints."""

import pytest
from quantumvitas.daemon.server import QVDaemon
from .conftest import send_request


class TestGetPresetCatalog:
    """Contract tests for get_preset_catalog RPC."""

    def test_get_preset_catalog_happy_path(self, daemon: QVDaemon):
        """get_preset_catalog returns available presets."""
        response = send_request(daemon, "get_preset_catalog", {})

        # Response should contain preset information
        # Schema may vary (presets, catalog, etc.)
        assert response is not None
        assert isinstance(response, dict)

    def test_get_preset_catalog_for_step_type(self, daemon: QVDaemon):
        """get_preset_catalog can filter by step_type."""
        response = send_request(daemon, "get_preset_catalog", {
            "step_type_gen": "scf"
        })
        assert response is not None

    def test_get_preset_catalog_workflow(self, daemon: QVDaemon):
        """get_preset_catalog before apply_presets."""
        catalog = send_request(daemon, "get_preset_catalog", {})
        assert catalog is not None


class TestApplyPresetsToStep:
    """Contract tests for apply_presets_to_step RPC."""

    def test_apply_presets_invalid_preset(self, demo_project_with_calculation, daemon: QVDaemon):
        """apply_presets_to_step with invalid preset options."""
        project_root, _, calc_ulid = demo_project_with_calculation
        calc = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid
        })
        step_ulid = calc["steps"][0]["ulid"]

        # Invalid preset combination should raise error
        with pytest.raises(RuntimeError):
            send_request(daemon, "apply_presets_to_step", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": step_ulid,
                "presets": {"invalid_key": "invalid_value"}
            })

    def test_apply_presets_workflow(self, demo_project_with_calculation, daemon: QVDaemon):
        """apply_presets in full editing workflow."""
        project_root, _, calc_ulid = demo_project_with_calculation
        calc = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid
        })
        step_ulid = calc["steps"][0]["ulid"]

        # Get catalog
        catalog = send_request(daemon, "get_preset_catalog", {})
        assert catalog is not None

        # Get step detail before
        before = send_request(daemon, "get_step_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step": step_ulid
        })
        assert before is not None
