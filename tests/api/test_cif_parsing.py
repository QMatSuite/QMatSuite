"""P3 hardening: CIF parsing — pin pymatgen behavior for structures.

Documents what CIF formats work and which fail, so we notice if
pymatgen changes its behavior. Also verifies POSCAR always works
as the recommended fallback format.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from qmatsuite.api.service import QMSService


# ── CIF test strings ──────────────────────────────────────────────────

VALID_SI_CIF = """\
data_Si
_cell_length_a   5.431
_cell_length_b   5.431
_cell_length_c   5.431
_cell_angle_alpha   90.0
_cell_angle_beta   90.0
_cell_angle_gamma   90.0
_symmetry_space_group_name_H-M   'F d -3 m'
_symmetry_Int_Tables_number   227

loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Si1 Si 0.0 0.0 0.0 1.0
"""

MINIMAL_AGENT_CIF = """\
data_Si
_cell_length_a   5.43
_cell_length_b   5.43
_cell_length_c   5.43
_cell_angle_alpha   90.0
_cell_angle_beta   90.0
_cell_angle_gamma   90.0
_symmetry_space_group_name_H-M   'F d -3 m'
_symmetry_Int_Tables_number   227

loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Si1 Si 0.0 0.0 0.0
Si2 Si 0.25 0.25 0.25
"""

BROKEN_CIF_NO_ATOMS = """\
data_invalid
_cell_length_a   5.43
"""

SI_POSCAR = """\
Silicon diamond
5.43
1.0 0.0 0.0
0.0 1.0 0.0
0.0 0.0 1.0
Si
2
direct
0.0 0.0 0.0
0.25 0.25 0.25
"""


class TestCIFParsing:
    """Pin pymatgen CIF parsing behavior so we know what works."""

    def test_valid_cif_parses(self):
        """Standard CIF with all required fields parses correctly."""
        from pymatgen.core import Structure

        struct = Structure.from_str(VALID_SI_CIF, fmt="cif")
        assert len(struct) > 0
        species_str = [str(s) for s in struct.species]
        assert "Si" in species_str

    def test_valid_cif_has_correct_symmetry(self):
        """Valid Si CIF with Fd-3m expands to 8 atoms (FCC diamond)."""
        from pymatgen.core import Structure

        struct = Structure.from_str(VALID_SI_CIF, fmt="cif")
        # Fd-3m with one Si at (0,0,0) should expand to 8 atoms
        assert len(struct) == 8, f"Expected 8 atoms from Fd-3m expansion, got {len(struct)}"

    def test_agent_minimal_cif_behavior(self):
        """Document whether agent-style minimal CIF (no _occupancy) parses or fails."""
        from pymatgen.core import Structure

        # This test DOCUMENTS behavior — passes regardless of outcome.
        try:
            struct = Structure.from_str(MINIMAL_AGENT_CIF, fmt="cif")
            assert len(struct) > 0
            print(f"Agent minimal CIF: parsed OK, {len(struct)} atoms")
        except Exception as e:
            print(f"Agent minimal CIF: failed with {type(e).__name__}: {e}")
        # Always passes — documents behavior

    def test_broken_cif_raises(self):
        """CIF with no atom data raises an exception."""
        from pymatgen.core import Structure

        with pytest.raises(Exception):
            Structure.from_str(BROKEN_CIF_NO_ATOMS, fmt="cif")

    def test_poscar_always_works(self):
        """POSCAR format reliably parses for simple structures."""
        from pymatgen.core import Structure

        struct = Structure.from_str(SI_POSCAR, fmt="poscar")
        assert len(struct) == 2
        assert str(struct.species[0]) == "Si"
        assert str(struct.species[1]) == "Si"

    def test_poscar_lattice_correct(self):
        """POSCAR lattice parameters are correct."""
        from pymatgen.core import Structure

        struct = Structure.from_str(SI_POSCAR, fmt="poscar")
        assert abs(struct.lattice.a - 5.43) < 0.01
        assert abs(struct.lattice.b - 5.43) < 0.01
        assert abs(struct.lattice.c - 5.43) < 0.01


class TestImportStructureAPI:
    """Verify structure import via QMSService with various formats."""

    def test_import_valid_cif(self, tmp_path):
        """import_file succeeds with a valid CIF."""
        project_root = QMSService.init_project(tmp_path / "proj")
        svc = QMSService(project_root)

        cif_path = tmp_path / "si.cif"
        cif_path.write_text(VALID_SI_CIF)

        dto = svc.structure.import_file(cif_path, name="Si_from_CIF")
        assert dto.structure_ulid
        assert dto.formula  # Should contain "Si"
        assert dto.num_atoms == 8  # Fd-3m expansion

    def test_import_poscar(self, tmp_path):
        """import_file succeeds with POSCAR format."""
        project_root = QMSService.init_project(tmp_path / "proj")
        svc = QMSService(project_root)

        poscar_path = tmp_path / "POSCAR"
        poscar_path.write_text(SI_POSCAR)

        dto = svc.structure.import_file(poscar_path, name="Si_from_POSCAR")
        assert dto.structure_ulid
        assert dto.num_atoms == 2

    def test_import_broken_cif_raises(self, tmp_path):
        """import_file with broken CIF raises a catchable exception."""
        project_root = QMSService.init_project(tmp_path / "proj")
        svc = QMSService(project_root)

        bad_path = tmp_path / "bad.cif"
        bad_path.write_text(BROKEN_CIF_NO_ATOMS)

        with pytest.raises(Exception):
            svc.structure.import_file(bad_path, name="Bad_CIF")

    def test_import_pymatgen_json(self, tmp_path):
        """import_file succeeds with pymatgen JSON format."""
        project_root = QMSService.init_project(tmp_path / "proj")
        svc = QMSService(project_root)

        json_data = json.dumps({
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {
                "matrix": [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]],
                "a": 5.43, "b": 5.43, "c": 5.43,
                "alpha": 90, "beta": 90, "gamma": 90,
            },
            "sites": [
                {"species": [{"element": "Si", "occu": 1}], "abc": [0, 0, 0], "xyz": [0, 0, 0]},
            ],
        })
        json_path = tmp_path / "si.json"
        json_path.write_text(json_data)

        dto = svc.structure.import_file(json_path, name="Si_from_JSON")
        assert dto.structure_ulid
        assert dto.num_atoms == 1
