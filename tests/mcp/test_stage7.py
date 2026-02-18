"""Stage 7 MCP tests — structure tools (list, import, detail).

Tests that the 3 structure tools correctly wrap the existing
``svc.structure.*`` backend methods and produce standard envelopes.

Shared fixtures (qv_project, qe_available, qe_project_with_si) are in conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.api import QVService


# ===========================================================================
# Minimal CIF for inline import tests
# ===========================================================================

_SI_CIF = """\
data_Si
_symmetry_space_group_name_H-M   'P 1'
_cell_length_a   3.84008480
_cell_length_b   3.84008480
_cell_length_c   3.84008480
_cell_angle_alpha   60.00000000
_cell_angle_beta   60.00000000
_cell_angle_gamma   60.00000000
_symmetry_Int_Tables_number   1
_chemical_formula_structural   Si
_chemical_formula_sum   Si2
_cell_volume   40.04123332
_cell_formula_units_Z   2
loop_
 _symmetry_equiv_pos_site_id
 _symmetry_equiv_pos_as_xyz
  1  'x, y, z'
loop_
 _atom_site_type_symbol
 _atom_site_label
 _atom_site_symmetry_multiplicity
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 _atom_site_occupancy
  Si  Si0  1  0.00000000  0.00000000  0.00000000  1
  Si  Si1  1  0.75000000  0.75000000  0.75000000  1
"""

_SI_POSCAR = """\
Si2
1.0
3.840085 0.000000 0.000000
1.920042 3.325610 0.000000
1.920042 1.108537 3.135218
Si
2
Direct
0.000000 0.000000 0.000000
0.750000 0.750000 0.750000
"""


# ===========================================================================
# Import tests
# ===========================================================================


class TestImportStructure:
    """Tests for the import_structure tool."""

    def test_import_cif_string(self, qv_project):
        """Import Si from inline CIF string → success with structure_ulid."""
        from quantumvitas.mcp.tools.import_structure import import_structure

        result = import_structure.fn(
            file_content=_SI_CIF, format="cif", name="Si_from_cif",
        )
        assert result["status"] == "success", f"import failed: {result}"
        data = result["data"]
        assert "structure_ulid" in data
        assert len(data["structure_ulid"]) > 0
        assert data["name"] is not None

    def test_import_cif_file(self, qv_project, tmp_path):
        """Import Si from a CIF file on disk."""
        from quantumvitas.mcp.tools.import_structure import import_structure

        cif_path = tmp_path / "si_test.cif"
        cif_path.write_text(_SI_CIF)

        result = import_structure.fn(file_path=str(cif_path), name="Si_file")
        assert result["status"] == "success"
        assert result["data"]["structure_ulid"]

    def test_import_poscar_string(self, qv_project):
        """Import Si from POSCAR string."""
        from quantumvitas.mcp.tools.import_structure import import_structure

        result = import_structure.fn(
            file_content=_SI_POSCAR, format="poscar", name="Si_poscar",
        )
        assert result["status"] == "success", f"import failed: {result}"
        assert result["data"]["n_atoms"] == 2

    def test_import_invalid_content(self, qv_project):
        """Bad content → error envelope."""
        from quantumvitas.mcp.tools.import_structure import import_structure

        result = import_structure.fn(
            file_content="this is not a valid structure", format="cif",
        )
        assert result["status"] == "error"
        assert result["error_type"] == "import_failed"

    def test_import_returns_formula(self, qv_project):
        """Imported structure response includes correct formula."""
        from quantumvitas.mcp.tools.import_structure import import_structure

        result = import_structure.fn(
            file_content=_SI_CIF, format="cif", name="Si_formula_test",
        )
        assert result["status"] == "success"
        assert "Si" in result["data"]["formula"]

    def test_import_missing_input(self, qv_project):
        """Neither file_path nor file_content → error."""
        from quantumvitas.mcp.tools.import_structure import import_structure

        result = import_structure.fn()
        assert result["status"] == "error"
        assert result["error_type"] == "missing_input"

    def test_import_file_not_found(self, qv_project):
        """Non-existent file_path → not_found error."""
        from quantumvitas.mcp.tools.import_structure import import_structure

        result = import_structure.fn(file_path="/nonexistent/path/file.cif")
        assert result["status"] == "error"
        assert result["error_type"] == "not_found"

    def test_import_context_hint(self, qv_project):
        """Context hint includes structure_ulid and create_calculation."""
        from quantumvitas.mcp.tools.import_structure import import_structure

        result = import_structure.fn(
            file_content=_SI_CIF, format="cif", name="Si_hint_test",
        )
        assert result["status"] == "success"
        hint = result.get("context_hint", "")
        assert result["data"]["structure_ulid"] in hint
        assert "create_calculation" in hint


# ===========================================================================
# List tests
# ===========================================================================


class TestListStructures:
    """Tests for the list_structures tool."""

    def test_list_empty_project(self, tmp_path, monkeypatch):
        """Fresh project with no structures → empty list + helpful hint."""
        from quantumvitas.mcp.tools.list_structures import list_structures
        from quantumvitas.mcp import project as mcp_project

        project_root = QVService.init_project(tmp_path / "empty_project")
        monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

        result = list_structures.fn()
        assert result["status"] == "success"
        assert result["data"]["structures"] == []
        assert result["data"]["total"] == 0
        assert "import_structure" in result.get("context_hint", "")

    def test_list_after_import(self, qv_project):
        """After import → shows the structure with correct fields."""
        from quantumvitas.mcp.tools.list_structures import list_structures

        # qv_project fixture already imports a Si structure
        result = list_structures.fn()
        assert result["status"] == "success"
        structs = result["data"]["structures"]
        assert len(structs) >= 1

        si = structs[0]
        assert "structure_ulid" in si
        assert "name" in si
        assert "formula" in si
        assert "n_atoms" in si
        assert si["n_atoms"] > 0
        assert "Si" in si["formula"]

    def test_list_context_hint_nonempty(self, qv_project):
        """Non-empty list hint mentions get_structure_detail and create_calculation."""
        from quantumvitas.mcp.tools.list_structures import list_structures

        result = list_structures.fn()
        assert result["status"] == "success"
        hint = result.get("context_hint", "")
        assert "get_structure_detail" in hint
        assert "create_calculation" in hint


# ===========================================================================
# Detail tests
# ===========================================================================


class TestGetStructureDetail:
    """Tests for the get_structure_detail tool."""

    def test_structure_detail_si(self, qv_project):
        """Si has correct species, sites, lattice info."""
        from quantumvitas.mcp.tools.list_structures import list_structures
        from quantumvitas.mcp.tools.get_structure_detail import get_structure_detail

        # Get the ULID from listing
        listing = list_structures.fn()
        assert listing["status"] == "success"
        ulid = listing["data"]["structures"][0]["structure_ulid"]

        result = get_structure_detail.fn(structure_ulid=ulid)
        assert result["status"] == "success"
        data = result["data"]

        assert data["structure_ulid"] == ulid
        assert "Si" in data["formula"]
        assert data["n_atoms"] > 0
        assert len(data["species"]) == data["n_atoms"]
        assert len(data["sites"]) == data["n_atoms"]

        # Each site has required fields
        site = data["sites"][0]
        assert "species" in site
        assert "cart_coords" in site
        assert len(site["cart_coords"]) == 3

    def test_structure_detail_lattice_params(self, qv_project):
        """Lattice parameters a, b, c, alpha, beta, gamma present."""
        from quantumvitas.mcp.tools.list_structures import list_structures
        from quantumvitas.mcp.tools.get_structure_detail import get_structure_detail

        listing = list_structures.fn()
        ulid = listing["data"]["structures"][0]["structure_ulid"]

        result = get_structure_detail.fn(structure_ulid=ulid)
        assert result["status"] == "success"
        lp = result["data"]["lattice_parameters"]
        for key in ("a", "b", "c", "alpha", "beta", "gamma"):
            assert key in lp
            assert lp[key] is not None
            assert isinstance(lp[key], (int, float))

        # Lattice vectors (3x3 matrix)
        lv = result["data"]["lattice_vectors"]
        assert lv is not None
        assert len(lv) == 3
        assert len(lv[0]) == 3

    def test_structure_detail_invalid_ulid(self, qv_project):
        """Error for non-existent structure."""
        from quantumvitas.mcp.tools.get_structure_detail import get_structure_detail

        result = get_structure_detail.fn(structure_ulid="NONEXISTENT_ULID")
        assert result["status"] == "error"
        assert result["error_type"] == "not_found"

    def test_structure_detail_context_hint(self, qv_project):
        """Context hint includes structure ULID and create_calculation."""
        from quantumvitas.mcp.tools.list_structures import list_structures
        from quantumvitas.mcp.tools.get_structure_detail import get_structure_detail

        listing = list_structures.fn()
        ulid = listing["data"]["structures"][0]["structure_ulid"]

        result = get_structure_detail.fn(structure_ulid=ulid)
        assert result["status"] == "success"
        hint = result.get("context_hint", "")
        assert ulid in hint
        assert "create_calculation" in hint


# ===========================================================================
# E2E test: import → list → create_calc (no QE needed for basic flow)
# ===========================================================================


class TestImportThenCreateCalc:
    """Full zero-to-calculation flow using only MCP tools."""

    def test_import_list_create(self, tmp_path, monkeypatch):
        """Import → list → detail → create_calculation works end-to-end."""
        from quantumvitas.mcp import project as mcp_project
        from quantumvitas.mcp.tools.import_structure import import_structure
        from quantumvitas.mcp.tools.list_structures import list_structures
        from quantumvitas.mcp.tools.get_structure_detail import get_structure_detail
        from quantumvitas.mcp.tools.create_calculation import create_calculation

        # 1. Fresh project
        project_root = QVService.init_project(tmp_path / "e2e_project")
        monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

        # 2. Import
        imp = import_structure.fn(
            file_content=_SI_CIF, format="cif", name="Si_e2e",
        )
        assert imp["status"] == "success"
        ulid = imp["data"]["structure_ulid"]

        # 3. List
        listing = list_structures.fn()
        assert listing["status"] == "success"
        assert listing["data"]["total"] >= 1
        found = [s for s in listing["data"]["structures"] if s["structure_ulid"] == ulid]
        assert len(found) == 1

        # 4. Detail
        detail = get_structure_detail.fn(structure_ulid=ulid)
        assert detail["status"] == "success"
        assert detail["data"]["n_atoms"] == 2

        # 5. Create calculation using the imported structure
        calc = create_calculation.fn(
            engine="qe", workflow="scf",
            structure_selector=ulid,
        )
        assert calc["status"] == "success"
        assert calc["data"]["calc_ulid"]
        assert calc["data"]["engine"] == "qe"
