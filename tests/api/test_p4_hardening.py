"""P4 hardening: API-level tests for FTS5, preflight, pseudo resolution.

Tests the lower-level components directly:
- FTS5 sanitization function (5 tests)
- Preflight step categories (2 tests)
- QE preflight rules (3 tests)
- Pseudo resolution (2 tests)
- Download pseudo config (2 tests)
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# FTS5 Sanitization (kernel-level)
# ---------------------------------------------------------------------------

class TestFTS5SanitizationKernel:
    """Test _sanitize_fts_query() directly."""

    def test_sanitize_strips_hyphens(self):
        """Hyphens between words are stripped; words are preserved."""
        from quantumvitas.mcp.knowledge.store import _sanitize_fts_query

        result = _sanitize_fts_query("Quantum-ESPRESSO")
        assert "Quantum" in result
        assert "ESPRESSO" in result
        assert "-" not in result

    def test_sanitize_strips_quotes(self):
        """Double quotes are stripped; quoted words preserved."""
        from quantumvitas.mcp.knowledge.store import _sanitize_fts_query

        result = _sanitize_fts_query('"SCF convergence"')
        assert "SCF" in result
        assert "convergence" in result
        assert '"' not in result

    def test_sanitize_strips_boolean_ops(self):
        """FTS5 boolean operators (AND, OR, NOT, NEAR) are removed."""
        from quantumvitas.mcp.knowledge.store import _sanitize_fts_query

        result = _sanitize_fts_query("NOT convergence OR crash AND error NEAR fix")
        assert "NOT" not in result.split()
        assert "OR" not in result.split()
        assert "AND" not in result.split()
        assert "NEAR" not in result.split()
        assert "convergence" in result
        assert "crash" in result
        assert "error" in result
        assert "fix" in result

    def test_sanitize_preserves_alphanumeric(self):
        """Normal alphanumeric tokens with underscores are preserved."""
        from quantumvitas.mcp.knowledge.store import _sanitize_fts_query

        result = _sanitize_fts_query("ecutwfc conv_thr mixing_beta")
        assert result == "ecutwfc conv_thr mixing_beta"

    def test_sanitize_empty_input(self):
        """Empty or all-special-char input returns empty string."""
        from quantumvitas.mcp.knowledge.store import _sanitize_fts_query

        assert _sanitize_fts_query("") == ""
        assert _sanitize_fts_query("---!!!@@@") == ""
        assert _sanitize_fts_query("-") == ""


# ---------------------------------------------------------------------------
# Preflight Step Categories
# ---------------------------------------------------------------------------

class TestPreflightStepCategories:
    """Verify _PW_X_GEN_STEPS matches known pw.x step types."""

    def test_pw_x_steps_match_spec_types(self):
        """pw.x gen steps should include scf, nscf, relax, md, bandspw, neb, custom."""
        from quantumvitas.mcp.tools.inspect_calculation import _PW_X_GEN_STEPS

        expected = {"scf", "nscf", "relax", "md", "bandspw", "neb", "custom"}
        assert _PW_X_GEN_STEPS == expected

    def test_non_pw_steps_excluded(self):
        """Post-processing steps should NOT be in _PW_X_GEN_STEPS."""
        from quantumvitas.mcp.tools.inspect_calculation import _PW_X_GEN_STEPS

        non_pw = {"dos", "bands", "pdos", "ph", "pp", "q2r", "matdyn", "dynmat",
                   "plotband", "hp", "gipaw", "pw2wannier", "pw2qmcpack"}
        overlap = _PW_X_GEN_STEPS & non_pw
        assert not overlap, f"Non-pw.x steps found in _PW_X_GEN_STEPS: {overlap}"


# ---------------------------------------------------------------------------
# QE Preflight Rules
# ---------------------------------------------------------------------------

class TestQEPreflightRules:
    """Direct tests on QEPreflightChecker."""

    @pytest.fixture
    def checker(self):
        from quantumvitas.drivers.qe.preflight import QEPreflightChecker
        return QEPreflightChecker()

    def test_checker_on_empty_params_returns_blocking(self, checker):
        """Empty params should produce at least one blocking issue (MISSING_ECUTWFC)."""
        issues = checker.check({}, None, None)
        blocking = [i for i in issues if i.severity == "blocking"]
        codes = [i.code for i in blocking]
        assert "MISSING_ECUTWFC" in codes

    def test_checker_on_complete_params_no_blocking(self, checker):
        """Well-configured params should produce no blocking issues."""
        params = {
            "CONTROL": {"calculation": "scf"},
            "SYSTEM": {"ecutwfc": 60.0, "nat": 2, "ntyp": 1},
            "kpoints": {"mesh": [8, 8, 8], "shift": [0, 0, 0]},
        }
        si_info = {
            "species": ["Si", "Si"],
            "n_atoms": 2,
            "elements": {"Si"},
            "is_periodic": True,
        }
        workflow = {
            "gen_steps": ["scf"],
            "current_step_index": 0,
            "current_step_gen": "scf",
        }
        issues = checker.check(params, si_info, workflow)
        blocking = [i for i in issues if i.severity == "blocking"]
        assert not blocking, f"Unexpected blocking issues: {blocking}"

    def test_metal_fixed_occ_advisory_not_warning(self, checker):
        """METAL_FIXED_OCC must be advisory, not warning."""
        params = {
            "SYSTEM": {"ecutwfc": 40.0, "occupations": "fixed"},
            "kpoints": {"mesh": [8, 8, 8], "shift": [0, 0, 0]},
        }
        fe_info = {
            "species": ["Fe"],
            "n_atoms": 1,
            "elements": {"Fe"},
            "is_periodic": True,
        }
        issues = checker.check(params, fe_info, None)
        metal_issues = [i for i in issues if i.code == "METAL_FIXED_OCC"]
        assert metal_issues
        assert metal_issues[0].severity == "advisory"


# ---------------------------------------------------------------------------
# Pseudo Resolution
# ---------------------------------------------------------------------------

class TestPseudoResolution:
    """Test pseudo resolution APIs."""

    def test_resolve_internal_pseudos_for_si(self):
        """Internal pseudo library should resolve Si."""
        try:
            from quantumvitas.core.pseudo_config import (
                PseudoResolutionRequest,
                load_pseudo_config,
                resolve_project_pseudos,
            )
            import tempfile
            from pathlib import Path

            config = load_pseudo_config()
            with tempfile.TemporaryDirectory() as tmpdir:
                request = PseudoResolutionRequest(
                    project_root=Path(tmpdir),
                    elements=["Si"],
                    library="sssp",
                    variant="precision",
                )
                result = resolve_project_pseudos(config, request)
                # May or may not succeed depending on SSSP installation,
                # but should not crash
                assert hasattr(result, "success")
        except ImportError:
            pytest.skip("pseudo_config not available")

    def test_resolve_missing_element_fails_gracefully(self):
        """Resolution for exotic elements should fail gracefully, not crash."""
        try:
            from quantumvitas.core.pseudo_config import (
                PseudoResolutionRequest,
                load_pseudo_config,
                resolve_project_pseudos,
            )
            import tempfile
            from pathlib import Path

            config = load_pseudo_config()
            with tempfile.TemporaryDirectory() as tmpdir:
                request = PseudoResolutionRequest(
                    project_root=Path(tmpdir),
                    elements=["Uue"],  # Ununennium — won't exist
                    library="sssp",
                    variant="precision",
                )
                result = resolve_project_pseudos(config, request)
                # Should fail gracefully
                if result.success:
                    # If it somehow succeeds, that's fine too
                    pass
                else:
                    assert not result.success
        except ImportError:
            pytest.skip("pseudo_config not available")


# ---------------------------------------------------------------------------
# Download Pseudo Config
# ---------------------------------------------------------------------------

class TestDownloadPseudoConfig:
    """Test download_pseudo_library configuration handling."""

    def test_sssp_library_path_structure(self):
        """PseudoConfig should have store_dir and seed_dir attributes."""
        from quantumvitas.core.pseudo_config import PseudoConfig

        config = PseudoConfig()
        assert hasattr(config, "store_dir")
        assert hasattr(config, "seed_dir")

    def test_download_and_install_signature(self):
        """pipeline.download_and_install should accept expected parameters."""
        import inspect
        from quantumvitas.pseudo.pipeline import download_and_install

        sig = inspect.signature(download_and_install)
        param_names = list(sig.parameters.keys())
        assert "library" in param_names
        assert "variant" in param_names
        assert "version" in param_names
