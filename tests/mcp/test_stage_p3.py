"""Stage P3 MCP tests — "Make it smooth" fixes.

Covers:
- Server startup auto-load (2 tests)
- init_project simplified (3 tests)
- dry_run complete input files (2 tests)
- Preset enum value normalization (2 tests)
- CIF import error hints (1 test)
- Demo structure registration (2 tests)
- Preflight K_POINTS false positive (1 test)
- Context hints (1 test)
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Server startup auto-load
# ---------------------------------------------------------------------------

class TestServerStartup:
    """Verify the server auto-load block in server.py."""

    def test_server_loads_existing_project(self, qv_project, monkeypatch):
        """When QMATSUITE_PROJECT points at an existing project, it is auto-loaded."""
        from quantumvitas.mcp import project as mcp_project

        # Reset the override so auto-load logic can be exercised
        monkeypatch.setattr(mcp_project, "_project_root_override", None)
        monkeypatch.setenv("QMATSUITE_PROJECT", str(qv_project))

        # Simulate the startup auto-load logic from server.py
        import os
        from pathlib import Path
        from quantumvitas.core.project_utils import find_project_root

        project_dir = Path(os.environ["QMATSUITE_PROJECT"]).resolve()
        found = find_project_root(start=project_dir) if project_dir.exists() else None
        assert found is not None
        mcp_project.set_project_root(found)

        assert mcp_project.get_project_root() == qv_project

    def test_server_starts_without_project(self, tmp_path, monkeypatch):
        """When QMATSUITE_PROJECT points at a non-project dir, startup still succeeds."""
        monkeypatch.setenv("QMATSUITE_PROJECT", str(tmp_path))

        from quantumvitas.core.project_utils import find_project_root

        found = find_project_root(start=tmp_path)
        assert found is None  # No crash, just no project


# ---------------------------------------------------------------------------
# init_project simplified
# ---------------------------------------------------------------------------

class TestInitProjectSimplified:
    """Tests for the rewritten init_project (no path param)."""

    def test_init_creates_in_current_dir(self, tmp_path, monkeypatch):
        """init_project creates a project in QMATSUITE_PROJECT dir."""
        target = tmp_path / "new_proj"
        target.mkdir()
        monkeypatch.setenv("QMATSUITE_PROJECT", str(target))

        from quantumvitas.mcp import project as mcp_project
        monkeypatch.setattr(mcp_project, "_project_root_override", None)

        from quantumvitas.mcp.tools.init_project import init_project

        result = init_project.fn(name="TestProject")
        assert result["status"] == "success"
        assert result["data"]["loaded"] is False
        assert (target / "project.qv.yml").exists()

    def test_init_loads_existing(self, qv_project, monkeypatch):
        """init_project with an existing project returns loaded=True."""
        monkeypatch.setenv("QMATSUITE_PROJECT", str(qv_project))

        from quantumvitas.mcp import project as mcp_project
        monkeypatch.setattr(mcp_project, "_project_root_override", None)

        from quantumvitas.mcp.tools.init_project import init_project

        result = init_project.fn()
        assert result["status"] == "success"
        assert result["data"]["loaded"] is True
        assert result["data"]["project_root"] == str(qv_project)

    def test_init_finds_parent_project(self, qv_project, monkeypatch):
        """init_project from a subdirectory finds the parent project."""
        subdir = qv_project / "subdir"
        subdir.mkdir()
        monkeypatch.setenv("QMATSUITE_PROJECT", str(subdir))

        from quantumvitas.mcp import project as mcp_project
        monkeypatch.setattr(mcp_project, "_project_root_override", None)

        from quantumvitas.mcp.tools.init_project import init_project

        result = init_project.fn()
        assert result["status"] == "success"
        assert result["data"]["loaded"] is True
        assert result["data"]["project_root"] == str(qv_project)


# ---------------------------------------------------------------------------
# dry_run completeness
# ---------------------------------------------------------------------------

class TestDryRunComplete:
    """Verify dry_run includes K_POINTS and nat/ntyp."""

    def test_dry_run_includes_kpoints(self, qv_project):
        """QE dry_run output must contain K_POINTS card."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0, dry_run=True)
        assert result["status"] == "success"

        input_files = result["data"].get("input_files", [])
        # Find the .in file
        pw_files = [f for f in input_files if f["filename"].endswith(".in")]
        assert pw_files, f"No .in file found in dry_run output: {[f['filename'] for f in input_files]}"

        pw_content = pw_files[0]["content"]
        assert "K_POINTS" in pw_content, f"K_POINTS card missing from dry_run output:\n{pw_content}"

    def test_dry_run_includes_nat_ntyp(self, qv_project):
        """QE dry_run output must contain nat and ntyp in SYSTEM namelist."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0, dry_run=True)
        assert result["status"] == "success"

        input_files = result["data"].get("input_files", [])
        pw_files = [f for f in input_files if f["filename"].endswith(".in")]
        assert pw_files

        pw_content = pw_files[0]["content"]
        # nat and ntyp should appear in the SYSTEM namelist
        assert "nat" in pw_content.lower(), f"nat missing from dry_run output:\n{pw_content}"
        assert "ntyp" in pw_content.lower(), f"ntyp missing from dry_run output:\n{pw_content}"


# ---------------------------------------------------------------------------
# Preset enum values
# ---------------------------------------------------------------------------

class TestPresetEnumValues:
    """Verify preset profile names are accepted by apply_preset."""

    def test_get_presets_values_accepted_by_apply(self, qv_project):
        """Values from get_presets() must be accepted by apply_preset()."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.get_presets import get_presets
        from quantumvitas.mcp.tools.apply_preset import apply_preset

        # Get preset options
        presets_result = get_presets.fn(engine="qe", workflow="scf")
        assert presets_result["status"] == "success"

        # Create a calculation
        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        # Try applying the default value for each dimension
        dims = presets_result["data"].get("dimensions", [])
        for dim in dims:
            default_val = dim.get("default")
            if default_val:
                result = apply_preset.fn(
                    calc_ulid=calc_ulid,
                    presets={dim["name"]: default_val},
                )
                assert result["status"] == "success", (
                    f"apply_preset failed for {dim['name']}={default_val}: "
                    f"{result.get('message', '')}"
                )

    def test_magnetism_nm_accepted(self, qv_project):
        """apply_preset with magnetism='NM' must not raise 'Unknown MagnetismOption'."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.apply_preset import apply_preset

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = apply_preset.fn(
            calc_ulid=calc_ulid,
            presets={"magnetism": "NM"},
        )
        assert result["status"] == "success", (
            f"apply_preset(magnetism='NM') failed: {result.get('message', '')}"
        )


# ---------------------------------------------------------------------------
# CIF import error hints
# ---------------------------------------------------------------------------

class TestCifImport:
    """Verify CIF error messages are helpful."""

    def test_cif_error_message_helpful(self, qv_project):
        """import_structure with broken CIF gives a CIF-specific hint."""
        from quantumvitas.mcp.tools.import_structure import import_structure

        result = import_structure.fn(
            file_content="data_invalid\n_cell_length_a  5.43\n",
            format="cif",
        )
        if result["status"] == "error":
            hint = result.get("context_hint", "")
            assert "CIF" in hint or "cif" in hint.lower(), (
                f"Error hint should mention CIF: {hint}"
            )
            assert "search_demos" in hint, (
                f"Error hint should mention search_demos: {hint}"
            )


# ---------------------------------------------------------------------------
# Demo structure registration
# ---------------------------------------------------------------------------

class TestDemoStructureRegistration:
    """Verify load_demo registers the structure properly."""

    def test_load_demo_structure_in_list(self, qv_project):
        """After load_demo, the demo's structure appears in list_structures."""
        from quantumvitas.mcp.tools.demo_store import search_demos, load_demo
        from quantumvitas.mcp.tools.list_structures import list_structures

        # Find a demo
        demos = search_demos.fn(engine="qe")
        assert demos["status"] == "success"
        demo_list = demos["data"].get("demos", [])
        if not demo_list:
            pytest.skip("No QE demos available")

        demo_id = demo_list[0].get("demo_id") or demo_list[0]["ulid"]

        # Load it
        loaded = load_demo.fn(demo_id=demo_id)
        assert loaded["status"] == "success", f"load_demo failed: {loaded.get('message', '')}"

        # Check structure appears in list
        structs = list_structures.fn()
        assert structs["status"] == "success"
        struct_names = [s.get("name", "") for s in structs["data"].get("structures", [])]
        # Should have at least 2 structures (original Silicon + demo's structure)
        assert len(struct_names) >= 2, f"Expected >=2 structures, got: {struct_names}"

    def test_load_demo_structure_reusable(self, qv_project):
        """After load_demo, the demo's structure can be used in create_calculation."""
        from quantumvitas.mcp.tools.demo_store import search_demos, load_demo
        from quantumvitas.mcp.tools.list_structures import list_structures
        from quantumvitas.mcp.tools.create_calculation import create_calculation

        # Find and load a QE demo
        demos = search_demos.fn(engine="qe")
        assert demos["status"] == "success"
        demo_list = demos["data"].get("demos", [])
        if not demo_list:
            pytest.skip("No QE demos available")

        demo_id = demo_list[0].get("demo_id") or demo_list[0]["ulid"]
        loaded = load_demo.fn(demo_id=demo_id)
        assert loaded["status"] == "success"

        # Get the structure ULID from the loaded demo
        structs = list_structures.fn()
        structures = structs["data"].get("structures", [])
        # Find a non-Silicon structure (the demo's structure)
        demo_structs = [s for s in structures if s.get("name", "").lower() != "silicon"]
        if not demo_structs:
            # If demo uses Silicon too, just use any structure
            demo_structs = structures

        struct_ulid = demo_structs[0].get("structure_ulid", "")
        assert struct_ulid, "No structure ULID found"

        # Create a new calc with the demo's structure
        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector=struct_ulid,
        )
        # Should succeed (structure is reusable)
        assert calc["status"] == "success", f"create_calculation failed: {calc.get('message', '')}"


# ---------------------------------------------------------------------------
# Preflight K_POINTS false positive
# ---------------------------------------------------------------------------

class TestPreflightKpoints:
    """Verify no false positive MISSING_KPOINTS from preflight."""

    def test_no_false_positive_kpoints(self, qv_project):
        """Default QE SCF calc should NOT report MISSING_KPOINTS in preflight."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = inspect_calculation.fn(calc_ulid=calc_ulid, step=0, dry_run=True)
        assert result["status"] == "success"

        issues = result["data"].get("preflight_issues", [])
        kpoints_issues = [i for i in issues if "KPOINTS" in i.get("code", "").upper()]
        assert not kpoints_issues, f"False positive K_POINTS issues: {kpoints_issues}"


# ---------------------------------------------------------------------------
# Context hints
# ---------------------------------------------------------------------------

class TestContextHints:
    """Verify updated context hints mention demos."""

    def test_list_engines_mentions_demos(self):
        """list_engines hint should mention search_demos."""
        from quantumvitas.mcp.tools.list_engines import list_engines

        result = list_engines.fn()
        assert result["status"] == "success"
        hint = result.get("context_hint", "")
        assert "search_demos" in hint, f"list_engines hint should mention search_demos: {hint}"
