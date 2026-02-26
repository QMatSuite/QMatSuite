"""Stage P1 MCP post-Phase-1 polish tests.

Covers:
- set_species_map tool (4 tests)
- quick_run presets fix (1 test)
- CIF error message fix (1 test)
- init_project tool (3 tests)
- Context hints & tool count (2 tests)
"""

from __future__ import annotations

import asyncio

import pytest


# ---------------------------------------------------------------------------
# set_species_map
# ---------------------------------------------------------------------------

class TestSetSpeciesMap:
    """Tests for the set_species_map MCP tool."""

    def test_set_valid(self, qms_project):
        """Create calc, set species_map, verify success."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation
        from qmatsuite.mcp.tools.set_species_map import set_species_map

        calc = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        result = set_species_map.fn(
            calc_ulid=calc_ulid,
            species_map={"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}},
        )
        assert result["status"] == "success"
        assert result["data"]["calc_ulid"] == calc_ulid
        assert result["data"]["species_map"]["Si"]["pseudopot"] == "Si.pbe-n-rrkjus_psl.1.0.0.UPF"

    def test_set_empty_fails(self, qms_project):
        """Empty dict returns invalid_species_map error."""
        from qmatsuite.mcp.tools.set_species_map import set_species_map

        result = set_species_map.fn(calc_ulid="bogus", species_map={})
        assert result["status"] == "error"
        assert result["error_type"] == "invalid_species_map"

    def test_set_missing_pseudopot_fails(self, qms_project):
        """Entry without 'pseudopot' key returns error."""
        from qmatsuite.mcp.tools.set_species_map import set_species_map

        result = set_species_map.fn(
            calc_ulid="bogus",
            species_map={"Si": {"mass": 28}},
        )
        assert result["status"] == "error"
        assert result["error_type"] == "invalid_species_map"
        assert "pseudopot" in result["message"]

    def test_set_nonexistent_calc_fails(self, qms_project):
        """Bad ULID returns error."""
        from qmatsuite.mcp.tools.set_species_map import set_species_map

        result = set_species_map.fn(
            calc_ulid="01NONEXISTENT",
            species_map={"Si": {"pseudopot": "Si.UPF"}},
        )
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# quick_run presets fix
# ---------------------------------------------------------------------------

class TestQuickRunPresetsFix:
    """Verify quick_run doesn't crash with presets argument."""

    def test_no_crash_with_presets(self, qms_project):
        """quick_run with presets returns a dict (no TypeError).

        The run itself will fail (no engine binary), but the presets
        code path must not crash with a wrong-signature TypeError.
        """
        from qmatsuite.mcp.tools.quick_run import quick_run

        result = quick_run.fn(
            engine="qe",
            workflow="scf",
            structure_selector="silicon",
            presets={"magnetism": "NM"},
        )
        assert isinstance(result, dict)
        # The error should not be a TypeError about unexpected keyword argument
        if result["status"] == "error":
            assert "unexpected keyword argument" not in result["message"]


# ---------------------------------------------------------------------------
# CIF error message
# ---------------------------------------------------------------------------

class TestCifErrorMessage:
    """Verify CIF parse errors surface clearly."""

    def test_invalid_cif_clear_error(self, qms_project):
        """import_structure with invalid CIF text gives a CIF-relevant error,
        not 'Cannot determine file type' from the Molecule fallback."""
        from qmatsuite.mcp.tools.import_structure import import_structure

        result = import_structure.fn(
            file_content="data_invalid\n_cell_length_a  5.43\n",
            format="cif",
        )
        # Should be an error since this CIF has no atomic positions
        if result["status"] == "error":
            assert "Cannot determine file type" not in result["message"]


# ---------------------------------------------------------------------------
# init_project
# ---------------------------------------------------------------------------

class TestInitProject:
    """Tests for the init_project MCP tool (P3: simplified, no path param)."""

    def test_creates_project(self, tmp_path, monkeypatch):
        """init_project creates project.qms.yml + subdirs."""
        target = tmp_path / "new_project"
        target.mkdir()
        monkeypatch.setenv("QMATSUITE_PROJECT", str(target))

        from qmatsuite.mcp import project as mcp_project
        monkeypatch.setattr(mcp_project, "_project_root_override", None)

        from qmatsuite.mcp.tools.init_project import init_project

        result = init_project.fn(name="TestProject")
        assert result["status"] == "success"
        assert result["data"]["name"] == "TestProject"
        assert (target / "project.qms.yml").exists()

    def test_sets_mcp_context(self, tmp_path, monkeypatch):
        """After init_project, get_project_root() returns the new path."""
        target = tmp_path / "ctx_project"
        target.mkdir()
        monkeypatch.setenv("QMATSUITE_PROJECT", str(target))

        from qmatsuite.mcp import project as mcp_project
        monkeypatch.setattr(mcp_project, "_project_root_override", None)

        from qmatsuite.mcp.tools.init_project import init_project

        init_project.fn()
        assert mcp_project.get_project_root() == target

    def test_loads_existing_project(self, qms_project, monkeypatch):
        """init_project with an existing project returns loaded=True (idempotent)."""
        monkeypatch.setenv("QMATSUITE_PROJECT", str(qms_project))

        from qmatsuite.mcp import project as mcp_project
        monkeypatch.setattr(mcp_project, "_project_root_override", None)

        from qmatsuite.mcp.tools.init_project import init_project

        result = init_project.fn()
        assert result["status"] == "success"
        assert result["data"]["loaded"] is True


# ---------------------------------------------------------------------------
# Context hints
# ---------------------------------------------------------------------------

class TestContextHints:
    """Verify context hints mention the right follow-up tools."""

    def test_create_calc_mentions_species_map(self, qms_project):
        """create_calculation hint must mention species_map (auto-resolved or manual)."""
        from qmatsuite.mcp.tools.create_calculation import create_calculation

        result = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert result["status"] == "success"
        hint = result["context_hint"]
        # Either auto-resolved (mentions "auto-resolved") or manual (mentions "set_species_map")
        assert "species_map" in hint.lower() or "auto-resolved" in hint.lower()

    def test_tool_count_38(self):
        """Verify 38 tools registered (32 previous + 6 engine management)."""
        from qmatsuite.mcp import server  # noqa: F401 — triggers registration
        from qmatsuite.mcp.app import mcp

        loop = asyncio.new_event_loop()
        try:
            tools = loop.run_until_complete(mcp.get_tools())
        finally:
            loop.close()
        assert len(tools) == 38, (
            f"Expected 38 tools, got {len(tools)}: {sorted(tools.keys())}"
        )

        # Verify the P1 tools exist
        assert "set_species_map" in tools
        assert "init_project" in tools
