"""
Structure I/O operations.

This module provides functions for reading and writing atomic structures
using ASE, pymatgen, or other libraries.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from pymatgen.core import Element
from pymatgen.core import Lattice
from pymatgen.core import Structure as PMGStructure

from quantumvitas.io.model import QECard, QECardType, QEInput, QENamelist
from quantumvitas.io.parser.qe_parser import QEInputParser

logger = logging.getLogger(__name__)


def read_structure(filepath: Path, format: Optional[str] = None) -> PMGStructure:
    """
    Read atomic structure from file using pymatgen.
    
    Args:
        filepath: Path to structure file
        format: Optional format hint (e.g., "cif", "qe")
                If None, format is inferred from file extension
        
    Returns:
        pymatgen Structure object
    """
    filepath = Path(filepath)
    if format is None:
        format = detect_format(filepath)
    format = format.lower()

    if format in {"qe", "in"}:
        qe_input = QEInputParser.parse_file(filepath)
        return _structure_from_qe_input(qe_input)
    if format == "json":
        data = json.loads(Path(filepath).read_text())
        return PMGStructure.from_dict(data)

    # Fallback: let pymatgen auto-detect (supports cif, poscar, etc.)
    return PMGStructure.from_file(str(filepath))


def write_structure(
    structure: PMGStructure, filepath: Path, format: Optional[str] = None
) -> None:
    """
    Write atomic structure to file using pymatgen.
    
    Args:
        structure: pymatgen Structure
        filepath: Path to output file
        format: Optional format hint (e.g., "cif", "poscar")
    """
    filepath = Path(filepath)
    if format is None:
        fmt = detect_format(filepath)
        if fmt == "unknown":
            fmt = "json"
    else:
        fmt = format.lower()

    if fmt == "json":
        filepath.write_text(json.dumps(structure.as_dict(), indent=2))
        return

    # pymatgen's Structure.to supports common formats via fmt argument
    structure.to(fmt=fmt, filename=str(filepath))


def detect_format(filepath: Path) -> str:
    """
    Detect structure file format from extension.
    
    Args:
        filepath: Path to structure file
        
    Returns:
        Format string (e.g., "cif", "xyz", "qe")
    """
    suffix = filepath.suffix.lower()
    format_map = {
        ".cif": "cif",
        ".xyz": "xyz",
        ".poscar": "vasp",
        ".vasp": "vasp",
        ".qe": "qe",
        ".in": "qe",
        ".json": "json",
    }
    return format_map.get(suffix, "unknown")


def qe_input_from_structure(structure: PMGStructure) -> QEInput:
    """
    Construct a minimal QEInput (pw.x) from a pymatgen Structure.
    
    This populates:
    - &CONTROL with a default calculation='scf'
    - &SYSTEM / &ELECTRONS as empty shells (to be filled/overwritten by CLI params)
    - ATOMIC_SPECIES, ATOMIC_POSITIONS (angstrom), CELL_PARAMETERS (angstrom),
      and a simple K_POINTS automatic mesh.
    """
    # Namelists – minimal defaults, CLI overrides will fill in details.
    control = QENamelist(name="CONTROL", parameters={"calculation": "scf"})
    system = QENamelist(name="SYSTEM", parameters={})
    electrons = QENamelist(name="ELECTRONS", parameters={})

    # ATOMIC_SPECIES: element symbol, atomic mass, pseudo file name (placeholder).
    species: List[Element] = list(structure.composition.elements)
    atomic_species_data: List[list] = []
    for el in species:
        mass = float(el.atomic_mass)
        pseudo_name = f"{el.symbol}.upf"
        atomic_species_data.append([el.symbol, mass, pseudo_name])

    atomic_species_card = QECard(
        card_type=QECardType.ATOMIC_SPECIES,
        option=None,
        data=atomic_species_data,
    )

    # ATOMIC_POSITIONS in angstrom
    atomic_positions_data: List[list] = []
    for site in structure.sites:
        x, y, z = site.coords
        atomic_positions_data.append([site.specie.symbol, x, y, z])

    atomic_positions_card = QECard(
        card_type=QECardType.ATOMIC_POSITIONS,
        option="angstrom",
        data=atomic_positions_data,
    )

    # CELL_PARAMETERS in angstrom
    cell_matrix = structure.lattice.matrix  # 3x3
    cell_parameters_data = [list(vec) for vec in cell_matrix]
    cell_parameters_card = QECard(
        card_type=QECardType.CELL_PARAMETERS,
        option="angstrom",
        data=cell_parameters_data,
    )

    # Simple default K_POINTS mesh (CLI can override namelist parameters later)
    k_points_card = QECard(
        card_type=QECardType.K_POINTS,
        option="automatic",
        data=[[4, 4, 4, 0, 0, 0]],
    )

    qe_input = QEInput(
        namelists=[control, system, electrons],
        cards=[
            atomic_species_card,
            atomic_positions_card,
            cell_parameters_card,
            k_points_card,
        ],
    )
    return qe_input


def _structure_from_qe_input(qe_input: QEInput) -> PMGStructure:
    """
    Build a pymatgen Structure from a QEInput instance.
    """
    cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)
    if not cell_card:
        raise ValueError("CELL_PARAMETERS card required to reconstruct structure.")

    lattice_matrix = [
        [float(x) for x in row]
        for row in cell_card.data
        if isinstance(row, (list, tuple)) and len(row) == 3
    ]
    if len(lattice_matrix) != 3:
        raise ValueError("CELL_PARAMETERS card must contain three lattice vectors.")

    option = (cell_card.option or "angstrom").lower()
    scale = 1.0
    if option == "bohr":
        scale = 0.52917721092

    lattice = Lattice([[scale * c for c in row] for row in lattice_matrix])

    positions_card = qe_input.get_card(QECardType.ATOMIC_POSITIONS)
    if not positions_card:
        raise ValueError("ATOMIC_POSITIONS card required to reconstruct structure.")

    coords: List[List[float]] = []
    species: List[str] = []

    pos_option = (positions_card.option or "angstrom").lower()
    coords_are_frac = pos_option in {"crystal", "crystal_sg", "crystal_sg_mod"}

    for row in positions_card.data:
        if len(row) < 4:
            continue
        species.append(str(row[0]))
        coords.append([float(row[1]), float(row[2]), float(row[3])])

    if not coords:
        raise ValueError("ATOMIC_POSITIONS card must contain at least one site.")

    structure = PMGStructure(
        lattice,
        species,
        coords,
        coords_are_cartesian=not coords_are_frac,
    )
    return structure

