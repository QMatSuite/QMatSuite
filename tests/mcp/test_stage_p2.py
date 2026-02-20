"""Stage P2 MCP tests — resource discovery + auto-resolution.

Tests:
- list_available_resources (QE, VASP, LAMMPS, xTB builtin, unknown engine)
- auto_resolve_species_map (QE resolve, unsupported engine, bad ULID)
- quick_run auto-resolve (auto without species_map, explicit map honoured)
- create_calculation auto-resolve (auto-resolve, hint content)
- run_calculation validation (missing species_map error, with map proceeds)
- inspect_calculation resource_status (key present, flags missing)
- Tool count (26 tools)
- Context hints

Shared fixtures (qv_project, qe_available, qe_project_with_si) in conftest.py.
"""

from __future__ import annotations

import asyncio

import pytest

from quantumvitas.api import QVService


# ===========================================================================
# list_available_resources
# ===========================================================================


class TestListAvailableResources:
    """Test list_available_resources tool for various engines."""

    def test_qe_with_si(self, qv_project):
        """QE + [Si] returns managed resource info."""
        from quantumvitas.mcp.tools.list_resources import list_available_resources

        r = list_available_resources.fn(engine="qe", elements=["Si"])
        assert r["status"] == "success", f"Failed: {r}"
        data = r["data"]
        assert data["engine"] == "qe"
        assert data["resources_needed"] is True
        assert data["managed"] is True
        assert "Si" in data["elements"]

    def test_qe_default_elements(self, qv_project):
        """QE with no elements uses defaults."""
        from quantumvitas.mcp.tools.list_resources import list_available_resources

        r = list_available_resources.fn(engine="qe")
        assert r["status"] == "success"
        data = r["data"]
        assert data["engine"] == "qe"
        # Should have some elements from internal pseudos
        assert len(data["elements"]) > 0

    def test_vasp(self, qv_project):
        """VASP returns POTCAR variants (may be empty if not installed)."""
        from quantumvitas.mcp.tools.list_resources import list_available_resources

        r = list_available_resources.fn(engine="vasp")
        # Should succeed even if no POTCARs installed (just returns 0 variants)
        assert r["status"] == "success"
        data = r["data"]
        assert data["engine"] == "vasp"
        assert data["resources_needed"] is True

    def test_lammps(self, qv_project):
        """LAMMPS returns potential file info."""
        from quantumvitas.mcp.tools.list_resources import list_available_resources

        r = list_available_resources.fn(engine="lammps")
        assert r["status"] == "success"
        data = r["data"]
        assert data["engine"] == "lammps"
        assert data["resources_needed"] is True

    def test_xtb_builtin(self, qv_project):
        """xTB reports no resources needed."""
        from quantumvitas.mcp.tools.list_resources import list_available_resources

        r = list_available_resources.fn(engine="xtb")
        assert r["status"] == "success"
        data = r["data"]
        assert data["resources_needed"] is False

    def test_unknown_engine(self, qv_project):
        """Unknown engine returns error."""
        from quantumvitas.mcp.tools.list_resources import list_available_resources

        r = list_available_resources.fn(engine="nonexistent_xyz")
        assert r["status"] == "error"
        assert r["error_type"] == "unknown_engine"


# ===========================================================================
# auto_resolve_species_map
# ===========================================================================


class TestAutoResolveSpeciesMap:
    """Test auto_resolve_species_map tool."""

    def test_qe_resolve_si(self, qv_project):
        """Auto-resolve QE Si returns species_map with pseudopot."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.resolve_species_map import auto_resolve_species_map

        # Create a QE calc with Si
        r = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert r["status"] == "success"
        calc_ulid = r["data"]["calc_ulid"]

        # Auto-resolve
        r = auto_resolve_species_map.fn(calc_ulid=calc_ulid)
        assert r["status"] == "success", f"Auto-resolve failed: {r}"
        data = r["data"]
        assert "Si" in data["species_map"]
        assert "pseudopot" in data["species_map"]["Si"]
        assert data["library"] == "sssp"
        assert data["flavor"] == "precision"

    def test_qe_resolve_metadata(self, qv_project):
        """Auto-resolve returns calc_ulid in the response."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.resolve_species_map import auto_resolve_species_map

        r = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = r["data"]["calc_ulid"]

        r = auto_resolve_species_map.fn(calc_ulid=calc_ulid)
        assert r["status"] == "success"
        assert r["data"]["calc_ulid"] == calc_ulid

    def test_bad_ulid(self, qv_project):
        """Bad ULID returns not_found error."""
        from quantumvitas.mcp.tools.resolve_species_map import auto_resolve_species_map

        r = auto_resolve_species_map.fn(calc_ulid="NONEXISTENT_ULID")
        assert r["status"] == "error"
        assert r["error_type"] == "not_found"

    def test_unsupported_engine(self, qv_project):
        """ORCA (unsupported) returns error."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.resolve_species_map import auto_resolve_species_map

        r = create_calculation.fn(
            engine="orca", workflow="scf", structure_selector="Silicon",
        )
        assert r["status"] == "success"
        calc_ulid = r["data"]["calc_ulid"]

        r = auto_resolve_species_map.fn(calc_ulid=calc_ulid)
        assert r["status"] == "error"
        assert r["error_type"] == "unsupported_engine"


# ===========================================================================
# quick_run auto-resolve
# ===========================================================================


class TestQuickRunAutoResolve:
    """Test quick_run auto-resolution of species_map."""

    def test_auto_resolve_without_explicit_map(self, qe_project_with_si):
        """quick_run with QE and no species_map auto-resolves and runs."""
        from quantumvitas.mcp.tools.quick_run import quick_run

        r = quick_run.fn(
            engine="qe", workflow="scf", structure_selector="Si",
        )
        assert r["status"] == "success", f"quick_run failed: {r}"
        assert r["data"]["status"] == "completed"

    def test_explicit_map_honoured(self, qe_project_with_si):
        """quick_run with explicit species_map uses that map (not auto-resolve)."""
        from quantumvitas.mcp.tools.quick_run import quick_run

        r = quick_run.fn(
            engine="qe", workflow="scf", structure_selector="Si",
            species_map={"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}},
        )
        assert r["status"] == "success", f"quick_run failed: {r}"
        assert r["data"]["status"] == "completed"


# ===========================================================================
# create_calculation auto-resolve
# ===========================================================================


class TestCreateCalcAutoResolve:
    """Test create_calculation auto-resolution of species_map."""

    def test_auto_resolve_flag(self, qv_project):
        """create_calculation for QE Si auto-resolves and reports flag."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation

        r = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert r["status"] == "success"
        data = r["data"]
        assert "species_map_resolved" in data
        # Should auto-resolve since Si is in internal pseudos
        assert data["species_map_resolved"] is True

    def test_hint_reflects_auto_resolve(self, qv_project):
        """When auto-resolved, hint should NOT say 'IMPORTANT: call set_species_map'."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation

        r = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert r["status"] == "success"
        hint = r["context_hint"]
        if r["data"]["species_map_resolved"]:
            assert "auto-resolved" in hint.lower() or "auto_resolve" not in hint
            assert "IMPORTANT" not in hint


# ===========================================================================
# run_calculation validation
# ===========================================================================


class TestRunCalcValidation:
    """Test run_calculation species_map validation."""

    def test_missing_species_map_error(self, qv_project):
        """QE calc without species_map returns missing_species_map error."""
        from quantumvitas.mcp.tools.run_calculation import run_calculation

        # Create calc manually (bypassing auto-resolve in create_calculation)
        svc = QVService(qv_project)
        calc = svc.project.init_calculation(
            name="test_no_map",
            structure_selector="Silicon",
            engine_family="qe",
        )
        calc_ulid = calc.ulid
        svc.calculation.add_step(calc_selector=calc_ulid, step_type_gen="scf")

        # Clear any auto-resolved species_map
        try:
            svc.calculation.update_species_map(calc_ulid, {})
        except Exception:
            pass

        r = run_calculation.fn(calc_ulid=calc_ulid)
        assert r["status"] == "error"
        assert r["error_type"] == "missing_species_map"
        assert "auto_resolve_species_map" in r["context_hint"]

    def test_run_calculation_accepts_run_mode(self, qv_project):
        """run_calculation accepts run_mode parameter without validation error."""
        from quantumvitas.mcp.tools.run_calculation import run_calculation

        # Create calc with species_map
        svc = QVService(qv_project)
        from quantumvitas.mcp.tools.create_calculation import create_calculation

        r = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert r["status"] == "success"
        calc_ulid = r["data"]["calc_ulid"]

        # Test run_mode="full" is accepted (no validation error about unknown param)
        r = run_calculation.fn(calc_ulid=calc_ulid, run_mode="full")
        # May fail for other reasons (no QE) but NOT invalid_run_mode
        assert r.get("error_type") != "invalid_run_mode"

        # Test invalid run_mode returns proper error
        r = run_calculation.fn(calc_ulid=calc_ulid, run_mode="bogus")
        assert r["status"] == "error"
        assert r["error_type"] == "invalid_run_mode"

    def test_with_species_map_no_validation_error(self, qv_project):
        """QE calc with species_map does not get missing_species_map error."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.run_calculation import run_calculation
        from quantumvitas.mcp.tools.set_species_map import set_species_map

        r = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert r["status"] == "success"
        calc_ulid = r["data"]["calc_ulid"]

        # If auto-resolve didn't work, set manually
        if not r["data"].get("species_map_resolved"):
            set_species_map.fn(
                calc_ulid=calc_ulid,
                species_map={"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}},
            )

        # Run will fail for other reasons (no QE binary) but NOT missing_species_map
        r = run_calculation.fn(calc_ulid=calc_ulid)
        assert r.get("error_type") != "missing_species_map"


# ===========================================================================
# inspect_calculation resource_status
# ===========================================================================


class TestInspectResourceStatus:
    """Test inspect_calculation resource_status field."""

    def test_resource_status_present(self, qv_project):
        """inspect_calculation includes resource_status key."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        r = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert r["status"] == "success"
        calc_ulid = r["data"]["calc_ulid"]

        r = inspect_calculation.fn(calc_ulid=calc_ulid)
        assert r["status"] == "success"
        data = r["data"]
        assert "resource_status" in data
        rs = data["resource_status"]
        assert "species_map_set" in rs
        assert "all_pseudos_resolved" in rs

    def test_resource_status_flags_missing(self, qv_project):
        """inspect_calculation flags when species_map is not set."""
        # Create calc manually without auto-resolve
        svc = QVService(qv_project)
        calc = svc.project.init_calculation(
            name="test_no_map",
            structure_selector="Silicon",
            engine_family="qe",
        )
        calc_ulid = calc.ulid
        svc.calculation.add_step(calc_selector=calc_ulid, step_type_gen="scf")

        # Clear species_map
        try:
            svc.calculation.update_species_map(calc_ulid, {})
        except Exception:
            pass

        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        r = inspect_calculation.fn(calc_ulid=calc_ulid)
        assert r["status"] == "success"
        rs = r["data"].get("resource_status", {})
        # With empty species_map, should flag as not set
        if not rs.get("species_map_set"):
            assert rs.get("all_pseudos_resolved") is False


# ===========================================================================
# Tool count
# ===========================================================================


class TestToolCount:
    """Test that all 27 tools are registered."""

    def test_31_tools(self):
        """Verify 31 tools registered (27 P4 + 2 Phase 2A + 1 generate_kpath + 1 cleanup_project)."""
        from quantumvitas.mcp import server  # noqa: F401
        from quantumvitas.mcp.app import mcp

        loop = asyncio.new_event_loop()
        try:
            tools = loop.run_until_complete(mcp.get_tools())
        finally:
            loop.close()
        assert len(tools) == 31, (
            f"Expected 31 tools, got {len(tools)}: {sorted(tools.keys())}"
        )

        # Verify P2 tools
        assert "list_available_resources" in tools
        assert "auto_resolve_species_map" in tools
        # Verify P4 tool
        assert "download_pseudo_library" in tools


# ===========================================================================
# Context hints
# ===========================================================================


class TestContextHints:
    """Test context hints reference correct tools."""

    def test_list_resources_hints(self, qv_project):
        """list_available_resources hints reference auto_resolve or set_species_map."""
        from quantumvitas.mcp.tools.list_resources import list_available_resources

        r = list_available_resources.fn(engine="qe", elements=["Si"])
        assert r["status"] == "success"
        hint = r["context_hint"]
        assert "auto_resolve_species_map" in hint or "set_species_map" in hint

    def test_resolve_species_map_hints(self, qv_project):
        """auto_resolve_species_map success hint references inspect and run."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.resolve_species_map import auto_resolve_species_map

        r = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = r["data"]["calc_ulid"]

        r = auto_resolve_species_map.fn(calc_ulid=calc_ulid)
        if r["status"] == "success":
            hint = r["context_hint"]
            assert "inspect_calculation" in hint
            assert "run_calculation" in hint
