"""Cross-project isolation tests — MCP layer.

Proves that MCP tools respect ``_project_root_override`` and never
leak structures or calculations across project boundaries, even when
both projects use identical names.

Uses the same nested-project topology as the API-layer tests (inner-first,
outer-second, adversarial naming) but exercises the MCP tool ``.fn()``
endpoints and switches project context via ``monkeypatch``.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from qmatsuite.api import QMSService
from qmatsuite.mcp import project as mcp_project
from qmatsuite.mcp.tools.list_structures import list_structures
from qmatsuite.mcp.tools.import_structure import import_structure
from qmatsuite.mcp.tools.create_calculation import create_calculation
from qmatsuite.mcp.tools.inspect_calculation import inspect_calculation
from qmatsuite.mcp.tools.get_results_summary import get_results_summary

# ---------------------------------------------------------------------------
# POSCAR inline constants
# ---------------------------------------------------------------------------

SI_POSCAR = """\
Si diamond
5.43
  0.5  0.5  0.0
  0.0  0.5  0.5
  0.5  0.0  0.5
Si
2
Direct
  0.00  0.00  0.00
  0.25  0.25  0.25
"""

AL_POSCAR = """\
Al FCC
4.05
  0.5  0.5  0.0
  0.0  0.5  0.5
  0.5  0.0  0.5
Al
1
Direct
  0.00  0.00  0.00
"""

FE_POSCAR = """\
Fe BCC
2.87
  1.0  0.0  0.0
  0.0  1.0  0.0
  0.0  0.0  1.0
Fe
2
Direct
  0.00  0.00  0.00
  0.50  0.50  0.50
"""

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mcp_nested_projects(tmp_path, monkeypatch):
    """Create nested projects and provide root-switching helper.

    Returns a dict with inner/outer roots, calc ULIDs, and a helper
    function ``set_root(root)`` that patches MCP project context.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # 1. Inner project
    inner_dir = workspace / "subdir" / "my-project"
    inner_dir.mkdir(parents=True)
    inner_root = QMSService.init_project(inner_dir, name="My Project")
    svc_inner = QMSService(inner_root)

    si_poscar = tmp_path / "si.vasp"
    si_poscar.write_text(SI_POSCAR)
    inner_struct = svc_inner.structure.import_file(si_poscar, name="Silicon")

    inner_calc = svc_inner.calculation.create(
        engine="qe", name="Si SCF", structure_selector="Silicon",
    )

    # 2. Outer project
    outer_root = QMSService.init_project(workspace, name="My Project")
    svc_outer = QMSService(outer_root)

    al_poscar = tmp_path / "al.vasp"
    al_poscar.write_text(AL_POSCAR)
    outer_struct = svc_outer.structure.import_file(al_poscar, name="Silicon")

    outer_calc = svc_outer.calculation.create(
        engine="qe", name="Si SCF", structure_selector="Silicon",
    )

    def set_root(root):
        monkeypatch.setattr(mcp_project, "_project_root_override", root)

    return {
        "inner_root": inner_root,
        "outer_root": outer_root,
        "inner_calc_ulid": inner_calc.calc_ulid,
        "outer_calc_ulid": outer_calc.calc_ulid,
        "inner_struct_formula": inner_struct.formula,
        "outer_struct_formula": outer_struct.formula,
        "set_root": set_root,
        "tmp_path": tmp_path,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMCPStructureIsolation:
    """MCP list_structures must only return the rooted project's structures."""

    def test_mcp_list_structures_inner_only(self, mcp_nested_projects):
        ctx = mcp_nested_projects
        ctx["set_root"](ctx["inner_root"])

        result = list_structures.fn()
        assert result["status"] == "success"

        structs = result["data"]["structures"]
        assert len(structs) == 1
        assert "Si" in structs[0]["formula"]

    def test_mcp_list_structures_outer_only(self, mcp_nested_projects):
        ctx = mcp_nested_projects
        ctx["set_root"](ctx["outer_root"])

        result = list_structures.fn()
        assert result["status"] == "success"

        structs = result["data"]["structures"]
        assert len(structs) == 1
        assert "Al" in structs[0]["formula"]


class TestMCPCalculationIsolation:
    """MCP create/inspect must bind to the rooted project only."""

    def test_mcp_create_calculation_uses_own_structure(self, mcp_nested_projects):
        ctx = mcp_nested_projects
        ctx["set_root"](ctx["outer_root"])

        result = create_calculation.fn(
            engine="qe",
            workflow="scf",
            structure_selector="Silicon",
            name="Verify Outer",
        )
        assert result["status"] == "success"

        # The new calc must use the outer project's "Silicon" (Al)
        calc_ulid = result["data"]["calc_ulid"]
        svc = QMSService(ctx["outer_root"])
        calc = svc.calculation.get(calc_ulid)
        struct = svc.structure.get(calc.structure_ulid)
        assert "Al" in struct.formula

    def test_mcp_inspect_calculation_cross_project_rejected(self, mcp_nested_projects):
        ctx = mcp_nested_projects
        # Root is outer, but we try to inspect inner's calc
        ctx["set_root"](ctx["outer_root"])

        result = inspect_calculation.fn(calc_ulid=ctx["inner_calc_ulid"])
        assert result["status"] == "error"

    def test_mcp_get_results_cross_project_rejected(self, mcp_nested_projects):
        ctx = mcp_nested_projects
        # Root is outer, but we try to get results for inner's calc
        ctx["set_root"](ctx["outer_root"])

        result = get_results_summary.fn(calc_ulid=ctx["inner_calc_ulid"])
        assert result["status"] == "error"


class TestMCPMutationIsolation:
    """MCP mutations in one project must not affect the other."""

    def test_mcp_import_structure_stays_in_own_project(self, mcp_nested_projects):
        ctx = mcp_nested_projects

        # Import Fe into outer
        ctx["set_root"](ctx["outer_root"])
        fe_poscar = ctx["tmp_path"] / "fe.vasp"
        fe_poscar.write_text(FE_POSCAR)

        result = import_structure.fn(
            file_path=str(fe_poscar), format="poscar", name="Iron",
        )
        assert result["status"] == "success"

        # Outer should now have 2 structures
        outer_result = list_structures.fn()
        assert outer_result["data"]["total"] == 2

        # Switch to inner — still exactly 1
        ctx["set_root"](ctx["inner_root"])
        inner_result = list_structures.fn()
        assert inner_result["data"]["total"] == 1
