"""
Tests that set_parameters returns validation_warnings for misplaced QE parameters.

The warnings are advisory — parameters are still set (warn, never block).
"""

import pytest

from quantumvitas.api import QVService


class TestSetParametersValidationWarnings:
    """Verify set_parameters returns validation_warnings for QE section mismatches."""

    @pytest.fixture
    def qe_scf_calc(self, qv_project):
        """Create a QE SCF calculation and return its calc_ulid."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation

        result = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert result["status"] == "success"
        return result["data"]["calc_ulid"]

    def test_wrong_section_emits_warning(self, qv_project, qe_scf_calc):
        """diago_full_acc in SYSTEM should succeed but emit a validation_warning."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        result = set_parameters.fn(
            calc_ulid=qe_scf_calc,
            params={"SYSTEM": {"diago_full_acc": True}},
            step=0,
        )
        assert result["status"] == "success"
        data = result["data"]
        assert "validation_warnings" in data
        warnings = data["validation_warnings"]
        assert len(warnings) == 1
        w = warnings[0]
        assert w["code"] == "PARAM_WRONG_SECTION"
        assert w["parameter"] == "diago_full_acc"
        assert w["current_section"] == "SYSTEM"
        assert w["expected_section"] == "ELECTRONS"
        assert w["severity"] == "warning"

    def test_wrong_section_includes_suggested_fix(self, qv_project, qe_scf_calc):
        """Suggested fix should contain corrective params dict."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        result = set_parameters.fn(
            calc_ulid=qe_scf_calc,
            params={"SYSTEM": {"diago_full_acc": True}},
            step=0,
        )
        data = result["data"]
        w = data["validation_warnings"][0]
        fix = w["suggested_fix"]
        assert fix["tool"] == "set_parameters"
        assert fix["params"]["SYSTEM"]["diago_full_acc"] is None  # delete from wrong
        assert fix["params"]["ELECTRONS"]["diago_full_acc"] is True  # set in correct

    def test_correct_section_no_warnings(self, qv_project, qe_scf_calc):
        """diago_full_acc in ELECTRONS should produce no warnings."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        result = set_parameters.fn(
            calc_ulid=qe_scf_calc,
            params={"ELECTRONS": {"diago_full_acc": True}},
            step=0,
        )
        assert result["status"] == "success"
        data = result["data"]
        assert "validation_warnings" not in data

    def test_params_still_set_despite_warning(self, qv_project, qe_scf_calc):
        """Even with warnings, the parameter must be set (warn, never block)."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        # Set param in wrong section
        result = set_parameters.fn(
            calc_ulid=qe_scf_calc,
            params={"SYSTEM": {"diago_full_acc": True}},
            step=0,
        )
        assert result["status"] == "success"

        # Inspect to verify it was actually set
        inspect_result = inspect_calculation.fn(calc_ulid=qe_scf_calc, step=0)
        data = inspect_result["data"]
        step_params = data["step_detail"]["parameters"]
        # The parameter should be in SYSTEM (where we set it, even though it's wrong)
        assert step_params.get("SYSTEM", {}).get("diago_full_acc") is True

    def test_multiple_wrong_sections(self, qv_project, qe_scf_calc):
        """Multiple misplaced params should each get their own warning."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        result = set_parameters.fn(
            calc_ulid=qe_scf_calc,
            params={"SYSTEM": {"diago_full_acc": True, "conv_thr": 1e-8}},
            step=0,
        )
        assert result["status"] == "success"
        data = result["data"]
        warnings = data.get("validation_warnings", [])
        assert len(warnings) == 2
        param_names = {w["parameter"] for w in warnings}
        assert "diago_full_acc" in param_names
        assert "conv_thr" in param_names

    def test_unknown_param_no_warning(self, qv_project, qe_scf_calc):
        """Parameters not in QE metadata should NOT trigger warning."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        result = set_parameters.fn(
            calc_ulid=qe_scf_calc,
            params={"SYSTEM": {"my_custom_xyz": 42}},
            step=0,
        )
        assert result["status"] == "success"
        data = result["data"]
        assert "validation_warnings" not in data


class TestValidateQeSectionsUnit:
    """Unit test the _validate_qe_sections helper directly."""

    def test_empty_params(self):
        from quantumvitas.mcp.tools.set_parameters import _validate_qe_sections

        assert _validate_qe_sections({}) == []

    def test_correct_placement(self):
        from quantumvitas.mcp.tools.set_parameters import _validate_qe_sections

        warnings = _validate_qe_sections({
            "SYSTEM": {"ecutwfc": 50},
            "ELECTRONS": {"conv_thr": 1e-8},
        })
        assert len(warnings) == 0

    def test_wrong_placement(self):
        from quantumvitas.mcp.tools.set_parameters import _validate_qe_sections

        warnings = _validate_qe_sections({
            "SYSTEM": {"conv_thr": 1e-8},
        })
        assert len(warnings) == 1
        assert warnings[0]["expected_section"] == "ELECTRONS"

    def test_non_namelist_keys_skipped(self):
        from quantumvitas.mcp.tools.set_parameters import _validate_qe_sections

        warnings = _validate_qe_sections({
            "kpoints": {"mesh": [4, 4, 4]},
        })
        assert len(warnings) == 0
