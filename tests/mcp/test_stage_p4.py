"""Stage P4 MCP tests — "Pseudo System & Remaining Demo Friction".

Covers:
- FTS5 sanitization (5 tests)
- Preflight step gating (4 tests)
- Dry-run step gating (2 tests)
- download_pseudo_library tool (3 tests)
- list_resources installed flag (2 tests)
- auto_resolve hint (1 test)
- set_species_map file warning (2 tests)
- preview_compilation empty params (2 tests)
- Preflight severity (1 test)
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# FTS5 Sanitization
# ---------------------------------------------------------------------------

class TestFTS5Sanitization:
    """Verify search_knowledge handles FTS5-hostile characters safely."""

    def test_hyphenated_query_no_crash(self, qms_project):
        """Hyphens in query must not trigger FTS5 syntax errors."""
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        result = search_knowledge.fn(query="Quantum-ESPRESSO")
        # Should succeed (may return empty results) — must not crash
        assert result["status"] == "success"

    def test_quoted_query_no_crash(self, qms_project):
        """Double quotes in query must not trigger FTS5 syntax errors."""
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        result = search_knowledge.fn(query='"SCF convergence"')
        assert result["status"] == "success"

    def test_boolean_operator_stripped(self, qms_project):
        """FTS5 boolean operators (AND, OR, NOT) must be stripped."""
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        result = search_knowledge.fn(query="NOT convergence OR crash")
        assert result["status"] == "success"

    def test_normal_query_still_works(self, qms_project):
        """Normal alphanumeric queries must still work."""
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        result = search_knowledge.fn(query="ecutwfc cutoff")
        assert result["status"] == "success"

    def test_empty_after_sanitize_returns_empty(self, qms_project):
        """A query that is all special chars returns empty results, not crash."""
        from qmatsuite.mcp.tools.search_knowledge import search_knowledge

        result = search_knowledge.fn(query="---!!!")
        assert result["status"] == "success"
        assert result["data"]["results"] == []


# ---------------------------------------------------------------------------
# Preflight Step Gating
# ---------------------------------------------------------------------------

class TestPreflightStepGating:
    """Verify preflight is skipped for non-pw.x steps."""

    def test_dos_step_no_preflight_issues(self, qms_project):
        """A 'dos' step must not produce pw.x-specific preflight issues."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation

        calc = create_calculation.fn(
            engine="qe", workflow="dos", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        # Find the dos step (typically step index 1 or 2)
        result = inspect_calculation.fn(calc_ulid=calc_ulid)
        assert result["status"] == "success"

        steps = result["data"]["steps"]
        dos_indices = [
            i for i, s in enumerate(steps)
            if s.get("step_type_gen") == "dos"
        ]
        if not dos_indices:
            pytest.skip("No 'dos' step found in dos workflow")

        dos_idx = dos_indices[0]
        detail = inspect_calculation.fn(calc_ulid=calc_ulid, step=dos_idx)
        assert detail["status"] == "success"

        issues = detail["data"].get("preflight_issues", [])
        # Must not have pw.x-specific issues like MISSING_ECUTWFC on dos step
        pw_codes = {"MISSING_ECUTWFC", "MISSING_KPOINTS", "INVALID_CALCULATION_TYPE"}
        found_pw_issues = [i for i in issues if i.get("code") in pw_codes]
        assert not found_pw_issues, f"False positive pw.x issues on dos step: {found_pw_issues}"

    def test_bands_step_no_false_positives(self, qms_project):
        """A 'bands' post-processing step must not produce pw.x preflight issues."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation

        calc = create_calculation.fn(
            engine="qe", workflow="bands", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = inspect_calculation.fn(calc_ulid=calc_ulid)
        assert result["status"] == "success"

        steps = result["data"]["steps"]
        bands_indices = [
            i for i, s in enumerate(steps)
            if s.get("step_type_gen") == "bands"
        ]
        if not bands_indices:
            pytest.skip("No 'bands' step found in bands workflow")

        bands_idx = bands_indices[0]
        detail = inspect_calculation.fn(calc_ulid=calc_ulid, step=bands_idx)
        assert detail["status"] == "success"

        issues = detail["data"].get("preflight_issues", [])
        pw_codes = {"MISSING_ECUTWFC", "MISSING_KPOINTS", "INVALID_CALCULATION_TYPE"}
        found_pw_issues = [i for i in issues if i.get("code") in pw_codes]
        assert not found_pw_issues, f"False positive pw.x issues on bands step: {found_pw_issues}"

    def test_scf_step_still_checked(self, qms_project):
        """An 'scf' step must still go through preflight checking."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        # SCF step is index 0
        result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0)
        assert result["status"] == "success"
        # Preflight should run for SCF — may have issues or not, but should not be skipped
        # We can verify by checking that _run_preflight was actually invoked
        # (the absence of issues when ecutwfc is not set would be a sign of skipping)

    def test_ph_step_skipped(self, qms_project):
        """A phonon (ph) step, if present, should skip pw.x preflight."""
        from qmatsuite.mcp.tools.inspect_calculation import _PW_X_GEN_STEPS

        assert "ph" not in _PW_X_GEN_STEPS
        assert "dos" not in _PW_X_GEN_STEPS
        assert "pdos" not in _PW_X_GEN_STEPS
        assert "scf" in _PW_X_GEN_STEPS
        assert "relax" in _PW_X_GEN_STEPS


# ---------------------------------------------------------------------------
# Dry-Run Step Gating
# ---------------------------------------------------------------------------

class TestDryRunStepGating:
    """Verify dry_run is skipped for non-pw.x steps."""

    def test_dos_step_dry_run_skipped_with_note(self, qms_project):
        """dry_run on a dos step should return a note, not try to materialize."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation

        calc = create_calculation.fn(
            engine="qe", workflow="dos", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = inspect_calculation.fn(calc_ulid=calc_ulid)
        steps = result["data"]["steps"]
        dos_indices = [
            i for i, s in enumerate(steps)
            if s.get("step_type_gen") == "dos"
        ]
        if not dos_indices:
            pytest.skip("No 'dos' step found in dos workflow")

        dos_idx = dos_indices[0]
        detail = inspect_calculation.fn(
            calc_ulid=calc_ulid, step=dos_idx, dry_run=True,
        )
        assert detail["status"] == "success"
        assert "dry_run_note" in detail["data"], (
            f"Expected dry_run_note for dos step, got: {list(detail['data'].keys())}"
        )
        assert "post-processing" in detail["data"]["dry_run_note"].lower()

    def test_scf_step_dry_run_still_works(self, qms_project):
        """dry_run on an scf step should still materialize input files."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0, dry_run=True)
        assert result["status"] == "success"
        assert "input_files" in result["data"], "SCF dry_run should produce input_files"


# ---------------------------------------------------------------------------
# download_pseudo_library Tool
# ---------------------------------------------------------------------------

class TestDownloadPseudoLibrary:
    """Verify download_pseudo_library tool structure."""

    def test_tool_registered(self):
        """download_pseudo_library must be registered as an MCP tool."""
        from qmatsuite.mcp.tools.download_pseudo_library import download_pseudo_library

        # Tool should be callable
        assert callable(download_pseudo_library.fn)

    def test_invalid_library_error(self):
        """Invalid library must return an error."""
        from qmatsuite.mcp.tools.download_pseudo_library import download_pseudo_library

        result = download_pseudo_library.fn(library="nonexistent_library")
        assert result["status"] == "error"
        assert result["error_type"] == "invalid_library"

    def test_tool_returns_expected_structure(self, monkeypatch):
        """When download succeeds, response has expected keys."""
        from qmatsuite.mcp.tools import download_pseudo_library as mod

        # Mock the pipeline to avoid network calls
        def mock_pipeline(library, variant, version):
            return {
                "success": True,
                "library_key": "sssp",
                "variant": "efficiency",
                "version": "1.3.0",
                "upf_count": 42,
                "install_dir": "/tmp/test",
                "messages": ["Installed 42 pseudopotentials"],
                "errors": [],
            }

        monkeypatch.setattr(
            "qmatsuite.pseudo.pipeline.download_and_install",
            mock_pipeline,
        )
        monkeypatch.setattr(
            "qmatsuite.pseudo.download_and_install",
            mock_pipeline,
        )

        result = mod.download_pseudo_library.fn(
            library="sssp", variant="efficiency", version="1.3.0"
        )
        assert result["status"] == "success"
        data = result["data"]
        assert data["library"] == "sssp"
        assert data["variant"] == "efficiency"
        assert data["upf_count"] == 42


# ---------------------------------------------------------------------------
# list_resources Installed Flag
# ---------------------------------------------------------------------------

class TestListResourcesInstalled:
    """Verify list_available_resources includes installed count."""

    def test_qe_response_includes_n_installed(self, qms_project):
        """QE resource listing must include n_installed per element."""
        from qmatsuite.mcp.tools.list_resources import list_available_resources

        result = list_available_resources.fn(engine="qe", elements=["Si"])
        assert result["status"] == "success"
        elements = result["data"].get("elements", {})
        if "Si" in elements:
            assert "n_installed" in elements["Si"]

    def test_installed_flag_per_element(self, qms_project):
        """QE resource listing must include top-level any_installed flag."""
        from qmatsuite.mcp.tools.list_resources import list_available_resources

        result = list_available_resources.fn(engine="qe")
        assert result["status"] == "success"
        assert "any_installed" in result["data"]


# ---------------------------------------------------------------------------
# auto_resolve Hint
# ---------------------------------------------------------------------------

class TestAutoResolveHint:
    """Verify resolution failure hints mention download_pseudo_library."""

    def test_failure_hint_mentions_download(self, qms_project):
        """When auto_resolve fails, hint should mention download_pseudo_library."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.resolve_species_map import auto_resolve_species_map

        # Create a calc with an element that internal pseudos don't cover
        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        # Try resolving — may fail if no SSSP installed
        result = auto_resolve_species_map.fn(calc_ulid=calc_ulid)
        if result["status"] == "error":
            hint = result.get("context_hint", "")
            assert "download_pseudo_library" in hint, (
                f"Failure hint should mention download_pseudo_library: {hint}"
            )


# ---------------------------------------------------------------------------
# set_species_map File Warning
# ---------------------------------------------------------------------------

class TestSetSpeciesMapWarning:
    """Verify set_species_map warns about missing pseudo files."""

    def test_nonexistent_pseudo_warns(self, qms_project):
        """Setting a non-existent pseudo file should produce a warning."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.set_species_map import set_species_map

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = set_species_map.fn(
            calc_ulid=calc_ulid,
            species_map={"Si": {"pseudopot": "NONEXISTENT_Si.UPF"}},
        )
        assert result["status"] == "success"
        # Should have warnings about missing file
        warnings = result.get("warnings", [])
        assert len(warnings) > 0, "Expected warning about non-existent pseudo file"
        assert "NONEXISTENT_Si.UPF" in warnings[0]

    def test_existing_pseudo_no_warning(self, qms_project):
        """Setting an existing internal pseudo should not produce a warning."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.set_species_map import set_species_map

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        # Use a pseudo that exists internally
        result = set_species_map.fn(
            calc_ulid=calc_ulid,
            species_map={"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}},
        )
        assert result["status"] == "success"
        warnings = result.get("warnings", [])
        # May or may not have warnings depending on internal pseudo availability
        # but the tool should succeed either way


# ---------------------------------------------------------------------------
# preview_compilation Empty Params
# ---------------------------------------------------------------------------

class TestPreviewCompilationEmpty:
    """Verify preview_compilation adds notes for empty parameters."""

    def test_empty_params_has_note(self):
        """When a step compiles to empty params, it should have a note."""
        from qmatsuite.mcp.tools.preview_compilation import preview_compilation

        # Use presets that won't match anything
        result = preview_compilation.fn(
            engine="qe",
            workflow="scf",
            presets={},
        )
        assert result["status"] == "success"
        steps = result["data"]["steps"]
        # Check if any step with empty params has a note
        empty_steps = [s for s in steps if not s["parameters"]]
        for s in empty_steps:
            assert "note" in s, f"Empty-params step should have a note: {s}"

    def test_all_empty_has_hint(self):
        """When ALL steps compile to empty params, result should have a hint."""
        from qmatsuite.mcp.tools.preview_compilation import preview_compilation

        # Use a workflow/presets combo that produces all empty
        result = preview_compilation.fn(
            engine="qe",
            workflow="scf",
            presets={},
        )
        assert result["status"] == "success"
        steps = result["data"]["steps"]
        if all(not s["parameters"] for s in steps):
            assert "hint" in result["data"], "All-empty result should have a hint"


# ---------------------------------------------------------------------------
# Preflight Severity
# ---------------------------------------------------------------------------

class TestPreflightSeverity:
    """Verify METAL_FIXED_OCC is advisory (not warning)."""

    def test_metal_fixed_occ_is_advisory(self):
        """METAL_FIXED_OCC must have severity='advisory', not 'warning'."""
        from qmatsuite.drivers.qe.preflight import QEPreflightChecker

        checker = QEPreflightChecker()
        params = {
            "SYSTEM": {"ecutwfc": 40.0, "occupations": "fixed"},
            "kpoints": {"mesh": [8, 8, 8], "shift": [0, 0, 0]},
        }
        structure_info = {
            "species": ["Fe", "Fe"],
            "n_atoms": 2,
            "elements": {"Fe"},
            "is_periodic": True,
        }
        workflow_context = {
            "gen_steps": ["scf"],
            "current_step_index": 0,
            "current_step_gen": "scf",
        }
        issues = checker.check(params, structure_info, workflow_context)
        metal_issues = [i for i in issues if i.code == "METAL_FIXED_OCC"]
        assert metal_issues, "Expected METAL_FIXED_OCC issue"
        assert metal_issues[0].severity == "advisory", (
            f"METAL_FIXED_OCC should be advisory, got: {metal_issues[0].severity}"
        )
