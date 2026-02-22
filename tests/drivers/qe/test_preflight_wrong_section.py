"""
Tests for the PARAM_WRONG_SECTION preflight rule.

Verifies that the QE preflight checker warns when parameters are placed
in the wrong namelist (e.g. diago_full_acc in SYSTEM instead of ELECTRONS).
"""

import pytest

from qmatsuite.drivers.qe.preflight import QEPreflightChecker


@pytest.fixture
def checker():
    return QEPreflightChecker()


class TestParamWrongSection:
    """Test PARAM_WRONG_SECTION advisory rule."""

    def test_diago_full_acc_in_system_triggers_warning(self, checker):
        """diago_full_acc in SYSTEM should emit PARAM_WRONG_SECTION."""
        params = {
            "CONTROL": {"calculation": "scf"},
            "SYSTEM": {
                "ecutwfc": 50,
                "diago_full_acc": True,  # WRONG: belongs in ELECTRONS
            },
            "ELECTRONS": {},
        }
        issues = checker.check(params, None, None)
        wrong_section = [i for i in issues if i.code == "PARAM_WRONG_SECTION"]
        assert len(wrong_section) == 1
        issue = wrong_section[0]
        assert issue.severity == "warning"
        assert "diago_full_acc" in issue.message
        assert "ELECTRONS" in issue.message
        assert "SYSTEM" in issue.parameter
        assert "ELECTRONS" in issue.suggestion

    def test_diago_full_acc_in_electrons_no_warning(self, checker):
        """diago_full_acc in ELECTRONS (correct) should NOT emit warning."""
        params = {
            "CONTROL": {"calculation": "scf"},
            "SYSTEM": {"ecutwfc": 50},
            "ELECTRONS": {"diago_full_acc": True},
        }
        issues = checker.check(params, None, None)
        wrong_section = [i for i in issues if i.code == "PARAM_WRONG_SECTION"]
        assert len(wrong_section) == 0

    def test_conv_thr_in_system_triggers_warning(self, checker):
        """conv_thr in SYSTEM should emit PARAM_WRONG_SECTION."""
        params = {
            "CONTROL": {"calculation": "scf"},
            "SYSTEM": {
                "ecutwfc": 50,
                "conv_thr": 1e-8,  # WRONG: belongs in ELECTRONS
            },
        }
        issues = checker.check(params, None, None)
        wrong_section = [i for i in issues if i.code == "PARAM_WRONG_SECTION"]
        assert len(wrong_section) == 1
        assert "conv_thr" in wrong_section[0].message
        assert "ELECTRONS" in wrong_section[0].suggestion

    def test_ecutwfc_in_electrons_triggers_warning(self, checker):
        """ecutwfc in ELECTRONS should emit PARAM_WRONG_SECTION."""
        params = {
            "CONTROL": {"calculation": "scf"},
            "SYSTEM": {},
            "ELECTRONS": {
                "ecutwfc": 50,  # WRONG: belongs in SYSTEM
            },
        }
        issues = checker.check(params, None, None)
        wrong_section = [i for i in issues if i.code == "PARAM_WRONG_SECTION"]
        assert len(wrong_section) == 1
        assert "ecutwfc" in wrong_section[0].message
        assert "SYSTEM" in wrong_section[0].suggestion

    def test_correct_params_no_warnings(self, checker):
        """All parameters in correct namelists should produce no warnings."""
        params = {
            "CONTROL": {"calculation": "scf", "outdir": "./outdir"},
            "SYSTEM": {"ecutwfc": 50, "occupations": "smearing", "degauss": 0.01},
            "ELECTRONS": {"conv_thr": 1e-8, "diago_full_acc": True},
        }
        issues = checker.check(params, None, None)
        wrong_section = [i for i in issues if i.code == "PARAM_WRONG_SECTION"]
        assert len(wrong_section) == 0

    def test_unknown_param_silently_skipped(self, checker):
        """Parameters not in QE metadata should NOT trigger warning."""
        params = {
            "CONTROL": {"calculation": "scf"},
            "SYSTEM": {
                "ecutwfc": 50,
                "my_custom_param_xyz": 42,  # Unknown param
            },
        }
        issues = checker.check(params, None, None)
        wrong_section = [i for i in issues if i.code == "PARAM_WRONG_SECTION"]
        assert len(wrong_section) == 0

    def test_multiple_misplaced_params(self, checker):
        """Multiple misplaced params should each get their own warning."""
        params = {
            "CONTROL": {"calculation": "scf"},
            "SYSTEM": {
                "ecutwfc": 50,
                "conv_thr": 1e-8,        # WRONG: ELECTRONS
                "diago_full_acc": True,   # WRONG: ELECTRONS
            },
        }
        issues = checker.check(params, None, None)
        wrong_section = [i for i in issues if i.code == "PARAM_WRONG_SECTION"]
        assert len(wrong_section) == 2
        param_names = {i.parameter for i in wrong_section}
        assert "SYSTEM.conv_thr" in param_names
        assert "SYSTEM.diago_full_acc" in param_names

    def test_ions_param_in_system_triggers_warning(self, checker):
        """IONS parameter in SYSTEM should trigger warning."""
        params = {
            "CONTROL": {"calculation": "relax"},
            "SYSTEM": {
                "ecutwfc": 50,
                "ion_dynamics": "bfgs",  # WRONG: belongs in IONS
            },
        }
        issues = checker.check(params, None, None)
        wrong_section = [i for i in issues if i.code == "PARAM_WRONG_SECTION"]
        assert len(wrong_section) == 1
        assert "IONS" in wrong_section[0].suggestion


class TestParamRegistryUtility:
    """Test the shared param_registry module."""

    def test_get_qe_param_namelist_known(self):
        from qmatsuite.drivers.qe.param_registry import get_qe_param_namelist

        assert get_qe_param_namelist("ecutwfc") == "SYSTEM"
        assert get_qe_param_namelist("conv_thr") == "ELECTRONS"
        assert get_qe_param_namelist("diago_full_acc") == "ELECTRONS"
        assert get_qe_param_namelist("calculation") == "CONTROL"
        assert get_qe_param_namelist("ion_dynamics") == "IONS"

    def test_get_qe_param_namelist_unknown(self):
        from qmatsuite.drivers.qe.param_registry import get_qe_param_namelist

        assert get_qe_param_namelist("nonexistent_param_xyz") is None

    def test_case_insensitive(self):
        from qmatsuite.drivers.qe.param_registry import get_qe_param_namelist

        assert get_qe_param_namelist("ECUTWFC") == "SYSTEM"
        assert get_qe_param_namelist("Ecutwfc") == "SYSTEM"
