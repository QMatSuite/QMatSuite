"""P3 hardening: Preflight accuracy — no false positives.

Tests the QE preflight checker directly to verify:
- K_POINTS in params → no MISSING_KPOINTS
- K_POINTS absent → MISSING_KPOINTS reported (true positive)
- ecutwfc set → no MISSING_ECUTWFC
- Properly configured calc → clean preflight
"""

from __future__ import annotations

import pytest

from quantumvitas.drivers.qe.preflight import QEPreflightChecker
from quantumvitas.core.driver_protocol import PreflightIssue


@pytest.fixture
def checker():
    """Create a QE preflight checker instance."""
    return QEPreflightChecker()


@pytest.fixture
def si_structure_info():
    """Minimal structure info for Silicon (2 atoms, periodic)."""
    return {
        "species": ["Si", "Si"],
        "n_atoms": 2,
        "elements": {"Si"},
        "is_periodic": True,
    }


@pytest.fixture
def scf_workflow_context():
    """Workflow context for a single SCF step."""
    return {
        "gen_steps": ["scf"],
        "current_step_index": 0,
        "current_step_gen": "scf",
        "other_steps_params": {},
    }


class TestKPointsAccuracy:
    """K_POINTS presence/absence detection must be accurate."""

    def test_kpoints_in_params_no_warning(self, checker, si_structure_info, scf_workflow_context):
        """QE calc with kpoints set → preflight does NOT report MISSING_KPOINTS."""
        params = {
            "SYSTEM": {"ecutwfc": 40.0, "nat": 2, "ntyp": 1},
            "kpoints": {"mesh": [8, 8, 8], "shift": [0, 0, 0]},
        }
        issues = checker.check(params, si_structure_info, scf_workflow_context)
        codes = [i.code for i in issues]
        assert "MISSING_KPOINTS" not in codes, (
            f"False positive MISSING_KPOINTS with kpoints in params: {issues}"
        )

    def test_kpoints_as_KPOINTS_key(self, checker, si_structure_info, scf_workflow_context):
        """KPOINTS key (uppercase) is also recognized."""
        params = {
            "SYSTEM": {"ecutwfc": 40.0},
            "KPOINTS": {"automatic": [4, 4, 4, 0, 0, 0]},
        }
        issues = checker.check(params, si_structure_info, scf_workflow_context)
        codes = [i.code for i in issues]
        assert "MISSING_KPOINTS" not in codes

    def test_kpoints_as_K_POINTS_key(self, checker, si_structure_info, scf_workflow_context):
        """K_POINTS key (with underscore) is also recognized."""
        params = {
            "SYSTEM": {"ecutwfc": 40.0},
            "K_POINTS": {"option": "automatic", "data": [[4, 4, 4, 0, 0, 0]]},
        }
        issues = checker.check(params, si_structure_info, scf_workflow_context)
        codes = [i.code for i in issues]
        assert "MISSING_KPOINTS" not in codes

    def test_kpoints_missing_does_warn(self, checker, si_structure_info, scf_workflow_context):
        """QE calc WITHOUT K_POINTS → preflight DOES report MISSING_KPOINTS."""
        params = {
            "SYSTEM": {"ecutwfc": 40.0},
            # No kpoints, KPOINTS, or K_POINTS key
        }
        issues = checker.check(params, si_structure_info, scf_workflow_context)
        codes = [i.code for i in issues]
        assert "MISSING_KPOINTS" in codes, (
            f"Expected MISSING_KPOINTS but got: {codes}"
        )

    def test_kpoints_missing_is_blocking(self, checker, si_structure_info, scf_workflow_context):
        """MISSING_KPOINTS issue has blocking severity."""
        params = {"SYSTEM": {"ecutwfc": 40.0}}
        issues = checker.check(params, si_structure_info, scf_workflow_context)
        kp_issues = [i for i in issues if i.code == "MISSING_KPOINTS"]
        assert kp_issues
        assert kp_issues[0].severity == "blocking"

    def test_kpoints_nonperiodic_no_warning(self, checker, scf_workflow_context):
        """Non-periodic structure → no MISSING_KPOINTS even without k-points."""
        molecule_info = {
            "species": ["H", "H"],
            "n_atoms": 2,
            "elements": {"H"},
            "is_periodic": False,
        }
        params = {"SYSTEM": {"ecutwfc": 40.0}}
        issues = checker.check(params, molecule_info, scf_workflow_context)
        codes = [i.code for i in issues]
        assert "MISSING_KPOINTS" not in codes


class TestEcutwfcAccuracy:
    """ecutwfc presence/absence detection must be accurate."""

    def test_ecutwfc_set_no_warning(self, checker, si_structure_info, scf_workflow_context):
        """QE calc with ecutwfc set → no MISSING_ECUTWFC."""
        params = {
            "SYSTEM": {"ecutwfc": 50.0, "nat": 2, "ntyp": 1},
            "kpoints": {"mesh": [4, 4, 4], "shift": [0, 0, 0]},
        }
        issues = checker.check(params, si_structure_info, scf_workflow_context)
        codes = [i.code for i in issues]
        assert "MISSING_ECUTWFC" not in codes

    def test_ecutwfc_missing_does_warn(self, checker, si_structure_info, scf_workflow_context):
        """QE calc without ecutwfc → MISSING_ECUTWFC reported."""
        params = {
            "SYSTEM": {"nat": 2, "ntyp": 1},
            "kpoints": {"mesh": [4, 4, 4], "shift": [0, 0, 0]},
        }
        issues = checker.check(params, si_structure_info, scf_workflow_context)
        codes = [i.code for i in issues]
        assert "MISSING_ECUTWFC" in codes

    def test_ecutwfc_zero_warns(self, checker, si_structure_info, scf_workflow_context):
        """ecutwfc=0 should trigger MISSING_ECUTWFC (non-positive)."""
        params = {
            "SYSTEM": {"ecutwfc": 0, "nat": 2, "ntyp": 1},
            "kpoints": {"mesh": [4, 4, 4], "shift": [0, 0, 0]},
        }
        issues = checker.check(params, si_structure_info, scf_workflow_context)
        codes = [i.code for i in issues]
        assert "MISSING_ECUTWFC" in codes


class TestCleanPreflight:
    """Well-configured calc should produce no blocking issues."""

    def test_well_configured_no_blocking(self, checker, si_structure_info, scf_workflow_context):
        """Properly configured QE SCF calc → no blocking preflight issues."""
        params = {
            "CONTROL": {"calculation": "'scf'"},
            "SYSTEM": {
                "ecutwfc": 40.0,
                "ecutrho": 320.0,
                "nat": 2,
                "ntyp": 1,
                "occupations": "'smearing'",
                "smearing": "'gaussian'",
                "degauss": 0.02,
            },
            "ELECTRONS": {"conv_thr": 1.0e-8},
            "kpoints": {"mesh": [8, 8, 8], "shift": [0, 0, 0]},
        }
        issues = checker.check(params, si_structure_info, scf_workflow_context)
        blocking = [i for i in issues if i.severity == "blocking"]
        assert not blocking, f"Blocking issues for well-configured calc: {blocking}"

    def test_empty_params_has_blocking(self, checker, si_structure_info, scf_workflow_context):
        """Empty params should produce at least MISSING_ECUTWFC blocking issue."""
        issues = checker.check({}, si_structure_info, scf_workflow_context)
        blocking = [i for i in issues if i.severity == "blocking"]
        assert len(blocking) > 0, "Empty params should have blocking issues"
        codes = [i.code for i in blocking]
        assert "MISSING_ECUTWFC" in codes
