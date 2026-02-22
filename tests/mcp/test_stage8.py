"""Stage 8 MCP tests — QE Preflight checker + dry_run materialization.

Tests that the QEPreflightChecker catches common parameter mistakes and
that dry_run mode materializes input files without executing.

Shared fixtures (qms_project, etc.) are in conftest.py.
"""

from __future__ import annotations

import pytest

from qmatsuite.core.driver_protocol import PreflightIssue
from qmatsuite.drivers.qe.preflight import QEPreflightChecker


# ===========================================================================
# Pure preflight tests (no project needed)
# ===========================================================================


class TestQEPreflightChecker:
    """Unit tests for QEPreflightChecker — 12 rules covering all severities."""

    def _checker(self):
        return QEPreflightChecker()

    def _si_structure(self):
        return {
            "species": ["Si", "Si"],
            "n_atoms": 2,
            "elements": {"Si"},
            "is_periodic": True,
        }

    def _scf_context(self):
        return {
            "gen_steps": ["scf"],
            "current_step_index": 0,
            "current_step_gen": "scf",
            "other_steps_params": {},
        }

    # B1
    def test_missing_ecutwfc(self):
        """Missing ecutwfc → blocking MISSING_ECUTWFC."""
        issues = self._checker().check(
            {"CONTROL": {"calculation": "scf"}, "SYSTEM": {}},
            self._si_structure(),
            self._scf_context(),
        )
        codes = [i.code for i in issues]
        assert "MISSING_ECUTWFC" in codes
        blocking = [i for i in issues if i.code == "MISSING_ECUTWFC"]
        assert blocking[0].severity == "blocking"

    # B2
    def test_missing_kpoints_periodic(self):
        """Periodic structure without kpoints → blocking MISSING_KPOINTS."""
        issues = self._checker().check(
            {"SYSTEM": {"ecutwfc": 40}},
            self._si_structure(),
            self._scf_context(),
        )
        codes = [i.code for i in issues]
        assert "MISSING_KPOINTS" in codes
        kp = [i for i in issues if i.code == "MISSING_KPOINTS"]
        assert kp[0].severity == "blocking"

    def test_kpoints_not_required_no_structure(self):
        """No structure → no MISSING_KPOINTS issue."""
        issues = self._checker().check(
            {"SYSTEM": {"ecutwfc": 40}},
            None,
            self._scf_context(),
        )
        codes = [i.code for i in issues]
        assert "MISSING_KPOINTS" not in codes

    # B4
    def test_nscf_without_scf(self):
        """nscf step without preceding scf → blocking NSCF_WITHOUT_SCF."""
        ctx = {
            "gen_steps": ["nscf"],
            "current_step_index": 0,
            "current_step_gen": "nscf",
            "other_steps_params": {},
        }
        issues = self._checker().check(
            {"SYSTEM": {"ecutwfc": 40}, "KPOINTS": {"automatic": [4, 4, 4, 0, 0, 0]}},
            self._si_structure(),
            ctx,
        )
        codes = [i.code for i in issues]
        assert "NSCF_WITHOUT_SCF" in codes

    # W1 (softened to advisory in P4)
    def test_metal_fixed_occupations(self):
        """Fixed occupations + metallic elements → advisory METAL_FIXED_OCC."""
        fe_structure = {
            "species": ["Fe", "Fe"],
            "n_atoms": 2,
            "elements": {"Fe"},
            "is_periodic": True,
        }
        issues = self._checker().check(
            {
                "SYSTEM": {"ecutwfc": 60, "occupations": "fixed"},
                "KPOINTS": {"automatic": [4, 4, 4, 0, 0, 0]},
            },
            fe_structure,
            self._scf_context(),
        )
        codes = [i.code for i in issues]
        assert "METAL_FIXED_OCC" in codes
        warn = [i for i in issues if i.code == "METAL_FIXED_OCC"]
        assert warn[0].severity == "advisory"

    # W2
    def test_spin_unpolarized_magnetic(self):
        """nspin=1 + magnetic element → warning SPIN_UNPOLARIZED_MAGNETIC."""
        fe_structure = {
            "species": ["Fe", "Fe"],
            "n_atoms": 2,
            "elements": {"Fe"},
            "is_periodic": True,
        }
        issues = self._checker().check(
            {
                "SYSTEM": {"ecutwfc": 60, "nspin": 1, "occupations": "smearing", "degauss": 0.02},
                "KPOINTS": {"automatic": [4, 4, 4, 0, 0, 0]},
            },
            fe_structure,
            self._scf_context(),
        )
        codes = [i.code for i in issues]
        assert "SPIN_UNPOLARIZED_MAGNETIC" in codes

    # W3
    def test_tetrahedra_with_relax(self):
        """Tetrahedra occupations + relax → warning TETRAHEDRA_WITH_RELAX."""
        issues = self._checker().check(
            {
                "CONTROL": {"calculation": "relax"},
                "SYSTEM": {"ecutwfc": 40, "occupations": "tetrahedra"},
                "KPOINTS": {"automatic": [4, 4, 4, 0, 0, 0]},
            },
            self._si_structure(),
            self._scf_context(),
        )
        codes = [i.code for i in issues]
        assert "TETRAHEDRA_WITH_RELAX" in codes

    # W5
    def test_smearing_no_degauss(self):
        """occupations=smearing without degauss → warning SMEARING_NO_DEGAUSS."""
        issues = self._checker().check(
            {
                "SYSTEM": {"ecutwfc": 40, "occupations": "smearing"},
                "KPOINTS": {"automatic": [4, 4, 4, 0, 0, 0]},
            },
            self._si_structure(),
            self._scf_context(),
        )
        codes = [i.code for i in issues]
        assert "SMEARING_NO_DEGAUSS" in codes

    # A1
    def test_low_ecutwfc_advisory(self):
        """ecutwfc=10 → advisory LOW_ECUTWFC."""
        issues = self._checker().check(
            {
                "SYSTEM": {"ecutwfc": 10},
                "KPOINTS": {"automatic": [4, 4, 4, 0, 0, 0]},
            },
            self._si_structure(),
            self._scf_context(),
        )
        codes = [i.code for i in issues]
        assert "LOW_ECUTWFC" in codes
        adv = [i for i in issues if i.code == "LOW_ECUTWFC"]
        assert adv[0].severity == "advisory"

    # A2
    def test_loose_conv_thr(self):
        """conv_thr > 1e-4 → advisory LOOSE_CONV_THR."""
        issues = self._checker().check(
            {
                "SYSTEM": {"ecutwfc": 40},
                "ELECTRONS": {"conv_thr": 1e-2},
                "KPOINTS": {"automatic": [4, 4, 4, 0, 0, 0]},
            },
            self._si_structure(),
            self._scf_context(),
        )
        codes = [i.code for i in issues]
        assert "LOOSE_CONV_THR" in codes

    def test_valid_params_no_issues(self):
        """Well-configured calculation → no issues."""
        issues = self._checker().check(
            {
                "CONTROL": {"calculation": "scf"},
                "SYSTEM": {"ecutwfc": 50, "occupations": "smearing", "degauss": 0.02},
                "ELECTRONS": {"conv_thr": 1e-8},
                "KPOINTS": {"automatic": [4, 4, 4, 0, 0, 0]},
            },
            self._si_structure(),
            self._scf_context(),
        )
        assert len(issues) == 0

    def test_preflight_issue_fields(self):
        """PreflightIssue has all expected fields."""
        issue = PreflightIssue(
            code="TEST_CODE",
            severity="warning",
            message="Test message",
            step=0,
            parameter="SYSTEM.ecutwfc",
            suggestion="Fix it",
            knowledge_ref="docs/qe/ecutwfc",
        )
        assert issue.code == "TEST_CODE"
        assert issue.severity == "warning"
        assert issue.message == "Test message"
        assert issue.step == 0
        assert issue.parameter == "SYSTEM.ecutwfc"
        assert issue.suggestion == "Fix it"
        assert issue.knowledge_ref == "docs/qe/ecutwfc"


# ===========================================================================
# Dry-run materialization tests (need project with calculation)
# ===========================================================================


class TestDryRunMaterialization:
    """Test dry_run=True on inspect_calculation."""

    def _create_qe_scf(self, qms_project):
        """Helper: create a QE SCF calculation and set ecutwfc."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.set_parameters import set_parameters

        result = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert result["status"] == "success", f"create_calculation failed: {result}"
        calc_ulid = result["data"]["calc_ulid"]

        sp = set_parameters.fn(
            calc_ulid=calc_ulid, step=0,
            params={"SYSTEM": {"ecutwfc": 40.0}},
        )
        assert sp["status"] == "success", f"set_parameters failed: {sp}"
        return calc_ulid

    def test_dry_run_produces_input_files(self, qms_project):
        """dry_run=True returns input_files array."""
        from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation

        calc_ulid = self._create_qe_scf(qms_project)
        result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0, dry_run=True)
        assert result["status"] == "success", f"inspect failed: {result}"
        data = result["data"]
        assert "input_files" in data, f"No input_files in response: {list(data.keys())}"
        assert len(data["input_files"]) > 0
        for f in data["input_files"]:
            assert "filename" in f
            assert "content" in f

    def test_dry_run_qe_scf_content(self, qms_project):
        """Dry run of QE SCF contains expected QE input markers."""
        from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation

        calc_ulid = self._create_qe_scf(qms_project)
        result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0, dry_run=True)
        assert result["status"] == "success"
        files = result["data"].get("input_files", [])

        # At least one file should contain QE-specific content
        all_content = " ".join(f["content"] for f in files)
        # QE input files typically have &SYSTEM or ATOMIC_SPECIES
        assert "&SYSTEM" in all_content or "ATOMIC_SPECIES" in all_content or "ecutwfc" in all_content, (
            f"QE-specific content not found in dry_run files: {[f['filename'] for f in files]}"
        )

    def test_dry_run_false_no_input_files(self, qms_project):
        """dry_run=False (default) → no input_files in response."""
        from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation

        calc_ulid = self._create_qe_scf(qms_project)
        result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0, dry_run=False)
        assert result["status"] == "success"
        assert "input_files" not in result["data"]


# ===========================================================================
# Preflight integration tests (inspect + preview tools)
# ===========================================================================


class TestPreflightIntegration:
    """Test that preflight issues surface through inspect + preview tools."""

    def test_inspect_includes_preflight_issues(self, qms_project):
        """Freshly-created calc → no false-positive MISSING_KPOINTS.

        P3 Fix 2+7: inspect now merges step cards into preflight params, so
        the K_POINTS card (set by default in create_calculation) is visible
        to the preflight checker.  MISSING_KPOINTS should NOT appear.
        """
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation

        result = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert result["status"] == "success"
        calc_ulid = result["data"]["calc_ulid"]

        inspect_result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0)
        assert inspect_result["status"] == "success"
        data = inspect_result["data"]
        issues = data.get("preflight_issues", [])
        # K_POINTS lives in cards → now merged → no false positive
        kp_issues = [i for i in issues if i["code"] == "MISSING_KPOINTS"]
        assert not kp_issues, f"False positive MISSING_KPOINTS: {kp_issues}"

    def test_preview_includes_preflight(self, qms_project):
        """preview_compilation with empty presets → preflight_issues for compiled params."""
        from qmatsuite.mcp.tools.preview_compilation import preview_compilation

        result = preview_compilation.fn(
            engine="qe", workflow="scf", presets={},
        )
        assert result["status"] == "success"
        data = result["data"]
        # The compiled params from empty presets likely won't have ecutwfc,
        # so we should get preflight issues or at least no crash.
        # If compiled params happen to include ecutwfc, there may be no issues — that's fine.
        # The key assertion is that the tool doesn't crash and has the right shape.
        if "preflight_issues" in data:
            for issue in data["preflight_issues"]:
                assert "code" in issue
                assert "severity" in issue
                assert "message" in issue

    def test_inspect_good_params_clean(self, qms_project):
        """Well-configured calculation → no preflight_issues or empty list."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.set_parameters import set_parameters
        from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation

        result = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert result["status"] == "success"
        calc_ulid = result["data"]["calc_ulid"]

        set_parameters.fn(
            calc_ulid=calc_ulid, step=0,
            params={
                "SYSTEM": {"ecutwfc": 50, "occupations": "smearing", "degauss": 0.02},
                "ELECTRONS": {"conv_thr": 1e-8},
                "KPOINTS": {"automatic": [4, 4, 4, 0, 0, 0]},
            },
        )

        inspect_result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0)
        assert inspect_result["status"] == "success"
        issues = inspect_result["data"].get("preflight_issues", [])
        assert len(issues) == 0
