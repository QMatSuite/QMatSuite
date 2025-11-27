from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

from quantumvitas.io import read_structure
from quantumvitas.io.model import QECardType
from quantumvitas.io.structure_io import qe_input_from_structure, write_structure


def test_write_and_read_structure_json(tmp_path: Path):
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
    json_path = tmp_path / "si.json"
    write_structure(structure, json_path, format="json")

    assert json_path.exists()
    loaded = read_structure(json_path)
    assert loaded.composition.reduced_formula == "Si"
    assert pytest.approx(loaded.lattice.a, rel=1e-6) == structure.lattice.a


def test_qe_input_from_structure_contains_required_cards():
    structure = Structure(Lattice.cubic(5.0), ["Si"], [[0, 0, 0]])
    qe_input = qe_input_from_structure(structure)

    control = qe_input.get_namelist("CONTROL")
    assert control is not None
    assert control.parameters["calculation"] == "scf"

    species_card = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    assert species_card is not None
    assert len(species_card.data) == 1

    positions_card = qe_input.get_card(QECardType.ATOMIC_POSITIONS)
    assert positions_card is not None
    assert len(positions_card.data) == 1

