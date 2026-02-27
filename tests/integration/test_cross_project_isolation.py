"""Cross-project isolation tests — API layer.

Proves that two QMatSuite projects (one nested inside the other, with
intentionally adversarial naming) cannot leak structures, calculations,
or ULIDs across project boundaries.

Background
----------
``ResourceIndex`` is strictly project-scoped — it only scans
``calculations/``, ``structures/``, and ``steps/`` under a given
``project_root``.  ``init_project()`` has a nesting guard
(``detect_enclosing_project``) that walks **upward** only, so
inner-first → outer-second creation succeeds.

Strategy: import Si (2 atoms, formula "Si2") in the inner project and
Al (1 atom, formula "Al1") in the outer project — both under the name
"Silicon".  Formula is the distinguishing invariant.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from qmatsuite.api import QMSService
from qmatsuite.api.errors import NotFoundError
from qmatsuite.core.project_utils import find_project_root

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

# ---------------------------------------------------------------------------
# Fixture: nested projects with adversarial naming
# ---------------------------------------------------------------------------


@pytest.fixture
def nested_projects(tmp_path):
    """Create inner-first, outer-second nested projects.

    Both projects are named "My Project", both structures named "Silicon",
    both calculations named "Si SCF".  Only the formula distinguishes them.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # 1. Inner project FIRST (avoids nesting guard)
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

    # 2. Outer project SECOND (wraps inner — same name on purpose)
    outer_root = QMSService.init_project(workspace, name="My Project")
    svc_outer = QMSService(outer_root)

    al_poscar = tmp_path / "al.vasp"
    al_poscar.write_text(AL_POSCAR)
    outer_struct = svc_outer.structure.import_file(al_poscar, name="Silicon")

    outer_calc = svc_outer.calculation.create(
        engine="qe", name="Si SCF", structure_selector="Silicon",
    )

    return {
        "svc_inner": svc_inner,
        "svc_outer": svc_outer,
        "inner_struct": inner_struct,
        "outer_struct": outer_struct,
        "inner_calc": inner_calc,
        "outer_calc": outer_calc,
        "inner_root": inner_root,
        "outer_root": outer_root,
        "workspace": workspace,
        "tmp_path": tmp_path,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStructureIsolation:
    """Structures from one project must never appear in the other."""

    def test_list_structures_isolated(self, nested_projects):
        svc_inner = nested_projects["svc_inner"]
        svc_outer = nested_projects["svc_outer"]

        inner_structs = svc_inner.structure.list()
        outer_structs = svc_outer.structure.list()

        assert len(inner_structs) == 1
        assert len(outer_structs) == 1
        assert "Si" in inner_structs[0].formula
        assert "Al" in outer_structs[0].formula

    def test_structure_count_exactly_one_each(self, nested_projects):
        svc_inner = nested_projects["svc_inner"]
        svc_outer = nested_projects["svc_outer"]

        assert len(svc_inner.structure.list()) == 1
        assert len(svc_outer.structure.list()) == 1

    def test_resolve_structure_by_name_returns_own(self, nested_projects):
        svc_inner = nested_projects["svc_inner"]
        svc_outer = nested_projects["svc_outer"]

        inner_si = svc_inner.structure.get("Silicon")
        outer_si = svc_outer.structure.get("Silicon")

        assert "Si" in inner_si.formula
        assert "Al" in outer_si.formula

    def test_inner_structure_ulid_not_found_in_outer(self, nested_projects):
        svc_outer = nested_projects["svc_outer"]
        inner_struct = nested_projects["inner_struct"]

        with pytest.raises(NotFoundError):
            svc_outer.structure.get(inner_struct.structure_ulid)

    def test_outer_structure_ulid_not_found_in_inner(self, nested_projects):
        svc_inner = nested_projects["svc_inner"]
        outer_struct = nested_projects["outer_struct"]

        with pytest.raises(NotFoundError):
            svc_inner.structure.get(outer_struct.structure_ulid)


class TestCalculationIsolation:
    """Calculations from one project must never appear in the other."""

    def test_list_calculations_isolated(self, nested_projects):
        svc_inner = nested_projects["svc_inner"]
        svc_outer = nested_projects["svc_outer"]

        inner_calcs = svc_inner.calculation.list()
        outer_calcs = svc_outer.calculation.list()

        assert len(inner_calcs) == 1
        assert len(outer_calcs) == 1
        assert inner_calcs[0].calc_ulid != outer_calcs[0].calc_ulid

    def test_resolve_calculation_by_slug_returns_own(self, nested_projects):
        svc_inner = nested_projects["svc_inner"]
        svc_outer = nested_projects["svc_outer"]

        inner_calc = svc_inner.calculation.get("si-scf")
        outer_calc = svc_outer.calculation.get("si-scf")

        assert inner_calc.calc_ulid != outer_calc.calc_ulid

    def test_inner_ulid_not_found_in_outer(self, nested_projects):
        svc_outer = nested_projects["svc_outer"]
        inner_calc = nested_projects["inner_calc"]

        with pytest.raises(NotFoundError):
            svc_outer.calculation.get(inner_calc.calc_ulid)

    def test_outer_ulid_not_found_in_inner(self, nested_projects):
        svc_inner = nested_projects["svc_inner"]
        outer_calc = nested_projects["outer_calc"]

        with pytest.raises(NotFoundError):
            svc_inner.calculation.get(outer_calc.calc_ulid)


class TestCrossReferences:
    """Calculations must reference their own project's structures."""

    def test_calculation_references_own_structure(self, nested_projects):
        inner_calc = nested_projects["inner_calc"]
        inner_struct = nested_projects["inner_struct"]
        outer_calc = nested_projects["outer_calc"]
        outer_struct = nested_projects["outer_struct"]

        assert inner_calc.structure_ulid == inner_struct.structure_ulid
        assert outer_calc.structure_ulid == outer_struct.structure_ulid

    def test_calculation_structure_content_correct(self, nested_projects):
        svc_inner = nested_projects["svc_inner"]
        svc_outer = nested_projects["svc_outer"]
        inner_calc = nested_projects["inner_calc"]
        outer_calc = nested_projects["outer_calc"]

        inner_struct = svc_inner.structure.get(inner_calc.structure_ulid)
        outer_struct = svc_outer.structure.get(outer_calc.structure_ulid)

        assert "Si" in inner_struct.formula
        assert "Al" in outer_struct.formula


class TestProjectDiscovery:
    """find_project_root must resolve to the correct (nearest) project."""

    def test_find_project_root_from_inner(self, nested_projects):
        inner_root = nested_projects["inner_root"]
        tmp_path = nested_projects["tmp_path"]

        found = find_project_root(inner_root, stop_at=tmp_path)
        assert found is not None
        assert found.resolve() == inner_root.resolve()

    def test_find_project_root_from_outer(self, nested_projects):
        outer_root = nested_projects["outer_root"]
        tmp_path = nested_projects["tmp_path"]

        found = find_project_root(outer_root, stop_at=tmp_path)
        assert found is not None
        assert found.resolve() == outer_root.resolve()


class TestULIDUniqueness:
    """All ULIDs across both projects must be globally unique."""

    def test_same_name_same_slug_different_ulids(self, nested_projects):
        inner_struct = nested_projects["inner_struct"]
        outer_struct = nested_projects["outer_struct"]
        inner_calc = nested_projects["inner_calc"]
        outer_calc = nested_projects["outer_calc"]

        all_ulids = {
            inner_struct.structure_ulid,
            outer_struct.structure_ulid,
            inner_calc.calc_ulid,
            outer_calc.calc_ulid,
        }
        assert len(all_ulids) == 4, "All 4 ULIDs must be distinct"


class TestMutationIsolation:
    """Operations in one project must not affect the other."""

    def test_no_cross_contamination_after_operations(self, nested_projects):
        svc_inner = nested_projects["svc_inner"]
        svc_outer = nested_projects["svc_outer"]

        # Snapshot inner state
        inner_struct_count = len(svc_inner.structure.list())
        inner_calc_count = len(svc_inner.calculation.list())

        # Mutate outer: create another calculation
        svc_outer.calculation.create(
            engine="qe", name="Extra Calc", structure_selector="Silicon",
        )

        # Inner must be unchanged
        assert len(svc_inner.structure.list()) == inner_struct_count
        assert len(svc_inner.calculation.list()) == inner_calc_count

        # Outer gained one calc
        assert len(svc_outer.calculation.list()) == 2
