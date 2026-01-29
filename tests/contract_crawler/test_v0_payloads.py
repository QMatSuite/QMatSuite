"""
Unit tests for v0 payload schemas.

These tests ensure the v0 payload schemas don't drift.
If a test fails, DO NOT change the schema - investigate why the drift occurred.
"""

import pytest
from tests.contract_crawler.v0_payloads import (
    build_v0_payload,
    V0_PAYLOAD_BUILDERS,
    V0_EXEMPT_METHODS,
    get_v0_payload_methods,
    is_v0_exempt,
)


class TestV0PayloadSchemas:
    """Test v0 payload schema definitions."""

    @pytest.fixture
    def mock_world(self):
        """Create a mock world dict for testing."""
        return {
            "project_root": "/test/project",
            "project_id": "01TEST00000000000000000001",
            "structure_id": "01TEST00000000000000000002",
            "calc_id": "01TEST00000000000000000003",
            "step_ids": ["01TEST00000000000000000004", "01TEST00000000000000000005"],
            "calculation_selector": "01TEST00000000000000000003",
            "step_selector": "01TEST00000000000000000004",
            "calc_slug": "demo_calc",
        }

    # -------------------------------------------------------------------------
    # Structure methods - selector MUST be a plain string, not a dict
    # -------------------------------------------------------------------------

    def test_delete_structure_selector_is_string(self, mock_world):
        """delete_structure: selector must be a plain string, NOT a dict."""
        payload = build_v0_payload("delete_structure", mock_world)

        assert "selector" in payload
        assert isinstance(payload["selector"], str), "selector must be str, not dict"
        assert payload["selector"] == mock_world["structure_id"]
        assert "project_root" in payload

    def test_rename_structure_selector_is_string(self, mock_world):
        """rename_structure: selector must be a plain string, NOT a dict."""
        payload = build_v0_payload("rename_structure", mock_world, new_name="new_name")

        assert "selector" in payload
        assert isinstance(payload["selector"], str), "selector must be str, not dict"
        assert payload["selector"] == mock_world["structure_id"]
        assert payload["new_name"] == "new_name"

    def test_can_delete_structure_selector_is_string(self, mock_world):
        """can_delete_structure: selector must be a plain string, NOT a dict."""
        payload = build_v0_payload("can_delete_structure", mock_world)

        assert "selector" in payload
        assert isinstance(payload["selector"], str), "selector must be str, not dict"
        assert payload["selector"] == mock_world["structure_id"]

    def test_get_structure_vis_selector_is_string(self, mock_world):
        """get_structure_vis: selector must be a plain string, NOT a dict."""
        payload = build_v0_payload("get_structure_vis", mock_world)

        assert "selector" in payload
        assert isinstance(payload["selector"], str), "selector must be str, not dict"
        assert payload["selector"] == mock_world["structure_id"]

    def test_import_structure_uses_source_file_key(self, mock_world):
        """import_structure: key is 'source_file', NOT 'source'."""
        payload = build_v0_payload(
            "import_structure", mock_world, source_file="/path/to/file.cif"
        )

        assert "source_file" in payload, "Key must be 'source_file', not 'source'"
        assert "source" not in payload, "Should not have 'source' key"
        assert payload["source_file"] == "/path/to/file.cif"

    # -------------------------------------------------------------------------
    # QE parameter methods
    # -------------------------------------------------------------------------

    def test_list_qe_ui_parameters_requires_both_module_and_step_type(self, mock_world):
        """list_qe_ui_parameters: requires both module AND step_type."""
        payload = build_v0_payload(
            "list_qe_ui_parameters", mock_world, module="pw", step_type="scf"
        )

        assert "module" in payload, "Must have 'module' field"
        assert "step_type" in payload, "Must have 'step_type' field"
        assert payload["module"] == "pw"
        assert payload["step_type"] == "scf"

    # -------------------------------------------------------------------------
    # Calculation/step methods
    # -------------------------------------------------------------------------

    def test_run_single_step_requires_calculation_and_step_ulid(self, mock_world):
        """run_single_step: requires calculation AND step_ulid."""
        payload = build_v0_payload("run_single_step", mock_world)

        assert "calculation" in payload, "Must have 'calculation' field"
        assert "step_ulid" in payload, "Must have 'step_ulid' field"
        assert payload["calculation"] == mock_world["calculation_selector"]
        assert payload["step_ulid"] == mock_world["step_selector"]

    def test_set_common_card_uses_view_model_not_card_value(self, mock_world):
        """set_common_card: key is 'view_model', NOT 'card_value'."""
        payload = build_v0_payload(
            "set_common_card",
            mock_world,
            card_name="K_POINTS",
            view_model={"grid": [4, 4, 4]},
        )

        assert "view_model" in payload, "Key must be 'view_model', not 'card_value'"
        assert "card_value" not in payload, "Should not have 'card_value' key"
        assert payload["card_name"] == "K_POINTS"

    # -------------------------------------------------------------------------
    # Workflow methods
    # -------------------------------------------------------------------------

    def test_instantiate_workflow_requires_all_fields(self, mock_world):
        """instantiate_workflow: requires workflow_id, calculation_path, structure_id, calculation_id."""
        payload = build_v0_payload("instantiate_workflow", mock_world, workflow_id="scf")

        assert "workflow_id" in payload
        assert "calculation_path" in payload
        assert "structure_id" in payload
        assert "calculation_id" in payload

        # calculation_path must use calc_slug for filesystem path
        assert mock_world["calc_slug"] in payload["calculation_path"]

    # -------------------------------------------------------------------------
    # Exempt methods
    # -------------------------------------------------------------------------

    def test_reset_step_params_is_exempt(self):
        """reset_step_params should be in exempt list (broken in 0873ebf)."""
        assert is_v0_exempt("reset_step_params"), (
            "reset_step_params must be exempt - 0873ebf handler passes "
            "calculation_ulid to service but service doesn't accept it"
        )

    def test_known_exempt_methods(self):
        """Verify known exempt methods are in the list."""
        expected_exempt = {
            # Baseline handler bugs
            "reset_step_params",
            "apply_presets_to_step",
            "get_pseudo_options_for_calculation",
            "set_common_card",
            # Ephemeral job state
            "cancel_job",
            "get_job_status",
            "get_job_logs",
            # Requires specific fixtures
            "compile_fixture_volume",
            # Terminates daemon
            "shutdown",
        }
        assert expected_exempt == V0_EXEMPT_METHODS

    # -------------------------------------------------------------------------
    # Registry completeness
    # -------------------------------------------------------------------------

    def test_unknown_method_raises_keyerror(self, mock_world):
        """Requesting unknown method should raise KeyError."""
        with pytest.raises(KeyError, match="No v0 payload schema"):
            build_v0_payload("nonexistent_method", mock_world)
