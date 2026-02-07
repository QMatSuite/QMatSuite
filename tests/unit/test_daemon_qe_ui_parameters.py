"""
Tests for engine UI parameters RPC (QE engine).

Uses the generic list_engine_ui_parameters handler with engine_family=qe.
"""

import pytest

from quantumvitas.daemon.server import QVDaemon


class TestEngineUIParametersQE:
    """Tests for list_engine_ui_parameters with engine_family=qe."""

    def test_ui_parameters_pw_scf(self):
        """Test fetching UI parameters for QE scf (inferred module=pw)."""
        daemon = QVDaemon()
        payload = {"engine_family": "qe", "step_type_gen": "scf"}

        result = daemon._handle_list_engine_ui_parameters(payload)

        assert "parameters" in result
        assert isinstance(result["parameters"], list)
        assert len(result["parameters"]) > 0

        # Check structure of first parameter (generic shape)
        first_param = result["parameters"][0]
        assert "key" in first_param
        assert "label" in first_param
        assert "type" in first_param
        assert "section" in first_param
        assert first_param["section"] in ["SYSTEM", "ELECTRONS", "CONTROL"]

    def test_ui_parameters_pw_nscf(self):
        """Test fetching UI parameters for QE nscf (inferred module=pw)."""
        daemon = QVDaemon()
        payload = {"engine_family": "qe", "step_type_gen": "nscf"}

        result = daemon._handle_list_engine_ui_parameters(payload)

        assert "parameters" in result
        assert isinstance(result["parameters"], list)
        assert len(result["parameters"]) > 0

    def test_ui_parameters_bands(self):
        """Test fetching UI parameters for QE bands (inferred module=bands)."""
        daemon = QVDaemon()
        payload = {"engine_family": "qe", "step_type_gen": "bands"}

        result = daemon._handle_list_engine_ui_parameters(payload)

        assert "parameters" in result
        assert isinstance(result["parameters"], list)
        assert len(result["parameters"]) > 0

        # Bands module should have BANDS section parameters
        bands_params = [p for p in result["parameters"] if p["section"] == "BANDS"]
        assert len(bands_params) > 0

    def test_missing_engine_family_raises(self):
        """Test that missing engine_family raises error."""
        daemon = QVDaemon()
        payload = {"step_type_gen": "scf"}

        with pytest.raises(ValueError, match="'engine_family' is required"):
            daemon._handle_list_engine_ui_parameters(payload)

    def test_missing_step_type_raises(self):
        """Test that missing step_type_gen raises error."""
        daemon = QVDaemon()
        payload = {"engine_family": "qe"}

        with pytest.raises(ValueError, match="'step_type_gen' is required"):
            daemon._handle_list_engine_ui_parameters(payload)

    def test_ui_parameters_exist_in_qe_params(self):
        """Test that all returned parameter keys exist in qe_module_parameters.json."""
        from quantumvitas.data import get_module_param_sections

        daemon = QVDaemon()
        payload = {"engine_family": "qe", "step_type_gen": "scf"}

        result = daemon._handle_list_engine_ui_parameters(payload)

        # Get all valid parameters for pw module (scf maps to pw)
        sections = get_module_param_sections("pw")
        all_valid_params = set()
        for param_list in sections.values():
            all_valid_params.update(param.lower() for param in param_list)

        # Check each UI parameter exists
        for param in result["parameters"]:
            param_name = param["key"].lower()
            assert param_name in all_valid_params, \
                f"UI parameter '{param['key']}' not found in qe_module_parameters.json"
