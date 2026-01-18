from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple
import math

from quantumvitas.io import QEInputParser, QECardType
from quantumvitas.io.structure_io import structure_from_qe_input
BOHR_TO_ANGSTROM = 0.52917721092


@dataclass
class QEAtomicPosition:
    label: str
    vector: Tuple[float, float, float]


@dataclass
class QEGeometrySnapshot:
    """
    Geometry snapshot expressed in alat units.

    cell_matrix and atomic_positions are stored as multiples of alat.
    """

    alat_angstrom: float
    cell_matrix: List[List[float]]  # dimensionless multiples of alat
    atomic_positions: List[QEAtomicPosition]  # dimensionless multiples of alat

    def scaled_cell_matrix(self) -> List[List[float]]:
        return [
            [self.alat_angstrom * component for component in row]
            for row in self.cell_matrix
        ]

    def scaled_atomic_positions(self) -> List[QEAtomicPosition]:
        return [
            QEAtomicPosition(
                pos.label,
                (
                    pos.vector[0] * self.alat_angstrom,
                    pos.vector[1] * self.alat_angstrom,
                    pos.vector[2] * self.alat_angstrom,
                ),
            )
            for pos in self.atomic_positions
        ]


def read_geometry_from_input(input_file: Path) -> QEGeometrySnapshot:
    qe_input = QEInputParser.parse_file(input_file)
    system = qe_input.get_namelist("system")
    alat_angstrom = _extract_alat_from_system(system.parameters)

    cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)
    if cell_card and cell_card.data:
        cell_matrix_ang = _parse_cell_parameters(card=cell_card, alat_angstrom=alat_angstrom)

        # When alat is not explicitly defined, use 1.0 angstrom so scaling is a no-op
        if alat_angstrom is None:
            alat_angstrom = 1.0
        cell_matrix = [[value / alat_angstrom for value in row] for row in cell_matrix_ang]

        positions_card = qe_input.get_card(QECardType.ATOMIC_POSITIONS)
        if not positions_card or not positions_card.data:
            raise ValueError(f"ATOMIC_POSITIONS not found in {input_file}")

        atomic_positions_ang = _parse_atomic_positions(
            positions_card,
            cell_matrix_ang,
            alat_angstrom,
        )
        atomic_positions = [
            QEAtomicPosition(
                label=label,
                vector=(
                    coords[0] / alat_angstrom,
                    coords[1] / alat_angstrom,
                    coords[2] / alat_angstrom,
                ),
            )
            for label, coords in atomic_positions_ang
        ]

        return QEGeometrySnapshot(
            alat_angstrom=alat_angstrom,
            cell_matrix=cell_matrix,
            atomic_positions=atomic_positions,
        )

    # Fallback: derive geometry from ibrav parameters via pymatgen structure builder
    structure = structure_from_qe_input(qe_input)
    alat_angstrom = _resolve_alat_or_default(alat_angstrom, structure.lattice.matrix)
    cell_matrix = [
        [component / alat_angstrom for component in vector]
        for vector in structure.lattice.matrix
    ]
    atomic_positions = [
        QEAtomicPosition(
            label=site.species_string,
            vector=(
                site.coords[0] / alat_angstrom,
                site.coords[1] / alat_angstrom,
                site.coords[2] / alat_angstrom,
            ),
        )
        for site in structure.sites
    ]

    return QEGeometrySnapshot(
        alat_angstrom=alat_angstrom,
        cell_matrix=cell_matrix,
        atomic_positions=atomic_positions,
    )


def read_geometry_from_output(output_file: Path) -> QEGeometrySnapshot:
    text = output_file.read_text()
    alat_bohr = _extract_alat_from_output(text)
    if alat_bohr is None:
        raise ValueError(f"Unable to find celldm(1) in {output_file}")
    alat_angstrom = alat_bohr * BOHR_TO_ANGSTROM

    cell_matrix = _extract_cell_matrix_from_output(text)
    atomic_positions = _extract_atomic_positions_from_output(text)

    return QEGeometrySnapshot(
        alat_angstrom=alat_angstrom,
        cell_matrix=cell_matrix,
        atomic_positions=[
            QEAtomicPosition(label=label, vector=tuple(coords))
            for label, coords in atomic_positions
        ],
    )


def compare_geometries(
    lhs: QEGeometrySnapshot,
    rhs: QEGeometrySnapshot,
    *,
    cell_atol: float = 1e-5,
    position_atol: float = 1e-4,
) -> Tuple[bool, str]:
    lhs_matrix = lhs.scaled_cell_matrix()
    rhs_matrix = rhs.scaled_cell_matrix()
    max_cell_diff = _max_matrix_difference(lhs_matrix, rhs_matrix)
    if max_cell_diff > cell_atol:
        return False, f"Cell matrix mismatch (max diff {max_cell_diff:.2e} Å)"

    lhs_positions = lhs.scaled_atomic_positions()
    rhs_positions = rhs.scaled_atomic_positions()
    if len(lhs_positions) != len(rhs_positions):
        return False, "Atomic position counts differ"

    max_pos_diff = 0.0
    for (lhs_pos, rhs_pos) in zip(lhs_positions, rhs_positions):
        if lhs_pos.label != rhs_pos.label:
            return False, f"Atom labels differ ({lhs_pos.label} vs {rhs_pos.label})"
        diff = max(
            abs(lhs_pos.vector[i] - rhs_pos.vector[i]) for i in range(3)
        )
        if diff > max_pos_diff:
            max_pos_diff = diff
    if max_pos_diff > position_atol:
        return False, f"Atomic positions mismatch (max diff {max_pos_diff:.2e} Å)"

    return True, "Geometries match"


# Helper functions --------------------------------------------------------- #


def _extract_alat_from_system(system: dict) -> float | None:
    celldm = system.get("celldm(1)") or system.get("celldm1")
    if celldm is not None:
        return float(celldm) * BOHR_TO_ANGSTROM
    alat = system.get("alat") or system.get("a")
    return float(alat) if alat is not None else None


def _parse_cell_parameters(card, alat_angstrom: float | None) -> List[List[float]]:
    option = (card.option or "").strip().lower()
    matrix: List[List[float]] = []
    for line in card.data:
        if isinstance(line, str):
            values = [float(value) for value in line.split()]
        else:
            values = [float(value) for value in line]
        if len(values) != 3:
            raise ValueError("CELL_PARAMETERS must have exactly 3 values per line.")
        matrix.append(values)

    if option in ("", "alat"):
        if alat_angstrom is None:
            raise ValueError("alat must be defined when CELL_PARAMETERS are in alat units.")
        return [[value * alat_angstrom for value in row] for row in matrix]
    if option == "bohr":
        return [[value * BOHR_TO_ANGSTROM for value in row] for row in matrix]
    if option == "angstrom":
        return matrix
    raise ValueError(f"Unsupported CELL_PARAMETERS option: {card.option}")


def _parse_atomic_positions(
    card,
    cell_matrix_ang: List[List[float]],
    alat_angstrom: float,
) -> List[Tuple[str, Tuple[float, float, float]]]:
    option = (card.option or "").strip().lower()
    positions: List[Tuple[str, Tuple[float, float, float]]] = []
    for line in card.data:
        if isinstance(line, str):
            parts = line.split()
        else:
            parts = [str(value) for value in line]
        if len(parts) < 4:
            raise ValueError("Invalid ATOMIC_POSITIONS line: {line}")
        label = parts[0]
        coords = [float(value) for value in parts[1:4]]
        if option in ("", "alat"):
            positions.append(
                (
                    label,
                    tuple(value * alat_angstrom for value in coords),
                )
            )
            continue
        if option == "angstrom":
            positions.append((label, tuple(coords)))
        elif option == "bohr":
            positions.append((label, tuple(value * BOHR_TO_ANGSTROM for value in coords)))
        elif option in ("crystal", "crystal_sg"):
            positions.append((label, tuple(_fractional_to_cart(coords, cell_matrix_ang))))
        else:
            raise ValueError(f"Unsupported ATOMIC_POSITIONS option: {card.option}")
    return positions


def _resolve_alat_or_default(
    alat_angstrom: float | None,
    lattice_matrix: Sequence[Sequence[float]],
) -> float:
    if alat_angstrom is not None:
        return alat_angstrom
    if lattice_matrix:
        vec = lattice_matrix[0]
        length = math.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)
        if length > 0:
            return length
    return 1.0


def _fractional_to_cart(fractional: Sequence[float], cell_matrix_ang: List[List[float]]) -> Tuple[float, float, float]:
    return tuple(
        sum(fractional[j] * cell_matrix_ang[j][i] for j in range(3))
        for i in range(3)
    )


def _extract_alat_from_output(text: str) -> float | None:
    import re

    match = re.search(r"celldm\(1\)\s*=\s*([-\d\.Ee+]+)", text)
    if not match:
        return None
    return float(match.group(1))


def _extract_cell_matrix_from_output(text: str) -> List[List[float]]:
    import re

    matrix: List[List[float]] = []
    for index in (1, 2, 3):
        pattern = rf"a\({index}\)\s*=\s*\(\s*([^\)]+)\)"
        match = re.search(pattern, text)
        if not match:
            raise ValueError(f"a({index}) vector not found in output.")
        values = [float(value) for value in match.group(1).split()]
        if len(values) != 3:
            raise ValueError(f"a({index}) must contain 3 components.")
        matrix.append(values)
    return matrix


def _extract_atomic_positions_from_output(text: str) -> List[Tuple[str, Tuple[float, float, float]]]:
    import re

    positions: List[Tuple[str, Tuple[float, float, float]]] = []
    capture = False
    for line in text.splitlines():
        stripped = line.strip().lower()
        if "site n." in stripped:
            capture = True
            continue
        if capture:
            if not stripped:
                if positions:
                    break
                continue
            if "positions" in stripped:
                continue
            if "tau(" not in stripped:
                continue
            match = re.search(
                r"^\s*\d+\s+([A-Za-z0-9_@#\-\+]+).*?=\s*\(\s*([-\d\.Ee+]+)\s+([-\d\.Ee+]+)\s+([-\d\.Ee+]+)\s*\)",
                line,
            )
            if not match:
                raise ValueError(f"Invalid atomic position line: {line}")
            label = match.group(1)
            coords = [float(match.group(i)) for i in range(2, 5)]
            positions.append((label, tuple(coords)))
    if not positions:
        raise ValueError("Atomic positions section not found in output.")
    return positions


def read_final_geometry_from_output_text(text: str) -> Tuple[QEGeometrySnapshot, List[str]]:
    """
    Parse the final coordinates block from QE relax/vc-relax output.
    
    Extracts the LAST "Begin final coordinates ... End final coordinates" block,
    which contains the final relaxed structure.
    
    Args:
        text: Full QE output text
        
    Returns:
        Tuple of (QEGeometrySnapshot, species_list)
        - QEGeometrySnapshot with alat-scaled cell and positions
        - List of species symbols in order
        
    Raises:
        ValueError: If no valid final coordinates block is found
    """
    import re
    
    # Find all "Begin final coordinates" blocks
    begin_pattern = r"Begin final coordinates"
    end_pattern = r"End final coordinates"
    
    # Find all matches
    begin_matches = list(re.finditer(begin_pattern, text, re.IGNORECASE))
    end_matches = list(re.finditer(end_pattern, text, re.IGNORECASE))
    
    if not begin_matches or not end_matches:
        raise ValueError("No 'Begin final coordinates' block found in output")
    
    # Find the last complete block (begin before end)
    last_block_start = None
    last_block_end = None
    
    for begin_match in reversed(begin_matches):
        # Find the first end after this begin
        for end_match in end_matches:
            if end_match.start() > begin_match.start():
                last_block_start = begin_match.start()
                last_block_end = end_match.end()
                break
        if last_block_start is not None:
            break
    
    if last_block_start is None or last_block_end is None:
        raise ValueError("No complete 'Begin final coordinates ... End final coordinates' block found")
    
    # Extract the block text
    block_text = text[last_block_start:last_block_end]
    
    # Parse CELL_PARAMETERS
    cell_pattern = r"CELL_PARAMETERS\s*\(alat\s*=\s*([-\d\.Ee+]+)\)"
    cell_match = re.search(cell_pattern, block_text, re.IGNORECASE)
    if not cell_match:
        # Try without explicit alat value
        cell_pattern_alt = r"CELL_PARAMETERS\s*\(alat\)"
        cell_match_alt = re.search(cell_pattern_alt, block_text, re.IGNORECASE)
        if not cell_match_alt:
            # CELL_PARAMETERS not found - this can happen for ibrav=0 relax (not vc-relax)
            # In this case, QE only outputs ATOMIC_POSITIONS (crystal) and we need to
            # extract the cell from the beginning of the output
            # Extract alat from earlier in output
            alat_match_global = re.search(r"celldm\(1\)\s*=\s*([-\d\.Ee+]+)", text[:last_block_start], re.IGNORECASE)
            if not alat_match_global:
                # Try alternative pattern
                alat_match_global = re.search(r"lattice parameter \(alat\)\s*=\s*([-\d\.Ee+]+)", text[:last_block_start], re.IGNORECASE)
            if not alat_match_global:
                raise ValueError(
                    "CELL_PARAMETERS not found in final coordinates block and cannot determine alat. "
                    "This may indicate the QE output format is not supported."
                )
            alat_bohr = float(alat_match_global.group(1))
            
            # Extract crystal axes from beginning of output (in units of alat)
            # Pattern: "crystal axes: (cart. coord. in units of alat)"
            #          "a(1) = (   x   y   z  )"
            crystal_axes_pattern = r"crystal axes:\s*\(cart\.\s*coord\.\s*in\s*units\s*of\s*alat\)"
            axes_match = re.search(crystal_axes_pattern, text[:last_block_start], re.IGNORECASE)
            if not axes_match:
                raise ValueError(
                    "CELL_PARAMETERS not found and cannot extract crystal axes from output. "
                    "This may indicate the QE output format is not supported."
                )
            
            # Extract the 3 crystal axis vectors after the match
            axes_start = axes_match.end()
            axes_section = text[axes_start:last_block_start]
            cell_lines = []
            for line in axes_section.split('\n')[:10]:
                # Pattern: "a(1) = (   x   y   z  )"
                axis_match = re.search(r"a\(\d+\)\s*=\s*\(\s*([-\d\.Ee+]+)\s+([-\d\.Ee+]+)\s+([-\d\.Ee+]+)\s*\)", line)
                if axis_match:
                    row = [float(axis_match.group(i)) for i in range(1, 4)]
                    cell_lines.append(row)
                    if len(cell_lines) == 3:
                        break
            
            if len(cell_lines) != 3:
                raise ValueError(
                    f"CELL_PARAMETERS not found and could not extract 3 crystal axes from output. "
                    f"Found {len(cell_lines)} axes."
                )
            
            cell_matrix = cell_lines  # Already dimensionless (multiples of alat)
            alat_angstrom = alat_bohr * BOHR_TO_ANGSTROM
            # Skip to ATOMIC_POSITIONS parsing (cell_matrix and alat_angstrom already set)
        else:
            # CELL_PARAMETERS (alat) without explicit value
            # Extract alat from elsewhere in the block or use default
            alat_match = re.search(r"lattice parameter \(alat\)\s*=\s*([-\d\.Ee+]+)", block_text, re.IGNORECASE)
            if alat_match:
                alat_bohr = float(alat_match.group(1))
            else:
                # Try to extract from earlier in output
                alat_match_global = re.search(r"celldm\(1\)\s*=\s*([-\d\.Ee+]+)", text[:last_block_start], re.IGNORECASE)
                if not alat_match_global:
                    raise ValueError("Cannot determine alat value")
                alat_bohr = float(alat_match_global.group(1))
            cell_start_pos = cell_match_alt.end()
            
            alat_angstrom = alat_bohr * BOHR_TO_ANGSTROM
            
            # Extract cell matrix (3 lines after CELL_PARAMETERS)
            cell_lines = []
            cell_section = block_text[cell_start_pos:].split('\n')
            for line in cell_section[:10]:  # Look at first 10 lines
                line = line.strip()
                if not line:
                    continue
                if line.startswith('ATOMIC_POSITIONS'):
                    break
                # Try to parse as 3 floats
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        row = [float(x) for x in parts[:3]]
                        cell_lines.append(row)
                        if len(cell_lines) == 3:
                            break
                    except ValueError:
                        continue
            
            if len(cell_lines) != 3:
                raise ValueError(f"Expected 3 cell parameter lines, found {len(cell_lines)}")
            
            cell_matrix = cell_lines  # Already dimensionless (multiples of alat)
    else:
        alat_bohr = float(cell_match.group(1))
        cell_start_pos = cell_match.end()
        
        alat_angstrom = alat_bohr * BOHR_TO_ANGSTROM
        
        # Extract cell matrix (3 lines after CELL_PARAMETERS)
        cell_lines = []
        cell_section = block_text[cell_start_pos:].split('\n')
        for line in cell_section[:10]:  # Look at first 10 lines
            line = line.strip()
            if not line:
                continue
            if line.startswith('ATOMIC_POSITIONS'):
                break
            # Try to parse as 3 floats
            parts = line.split()
            if len(parts) >= 3:
                try:
                    row = [float(x) for x in parts[:3]]
                    cell_lines.append(row)
                    if len(cell_lines) == 3:
                        break
                except ValueError:
                    continue
        
        if len(cell_lines) != 3:
            raise ValueError(f"Expected 3 cell parameter lines, found {len(cell_lines)}")
        
        cell_matrix = cell_lines  # Already dimensionless (multiples of alat)
    
    # Parse ATOMIC_POSITIONS
    # Can be in different formats: (alat), (crystal), (angstrom), etc.
    pos_patterns = [
        (r"ATOMIC_POSITIONS\s*\(alat\)", "alat"),
        (r"ATOMIC_POSITIONS\s*\(crystal\)", "crystal"),
        (r"ATOMIC_POSITIONS\s*\(angstrom\)", "angstrom"),
        (r"ATOMIC_POSITIONS\s*\(bohr\)", "bohr"),
    ]
    
    pos_match = None
    pos_format = None
    for pattern, fmt in pos_patterns:
        pos_match = re.search(pattern, block_text, re.IGNORECASE)
        if pos_match:
            pos_format = fmt
            break
    
    if not pos_match:
        raise ValueError("ATOMIC_POSITIONS not found in final coordinates block")
    
    pos_lines = []
    pos_start = pos_match.end()
    pos_section = block_text[pos_start:].split('\n')
    species = []
    
    for line in pos_section[:100]:  # Look at first 100 lines
        line = line.strip()
        if not line:
            if pos_lines:
                break  # Empty line after positions means we're done
            continue
        if "End final coordinates" in line:
            break
        # Parse: "Si  x y z  [flags]"
        parts = line.split()
        if len(parts) >= 4:
            try:
                label = parts[0]
                coords = [float(parts[1]), float(parts[2]), float(parts[3])]
                species.append(label)
                
                # Convert coordinates to alat units if needed
                if pos_format == "crystal":
                    # Fractional coordinates: convert to Cartesian in alat units
                    # coords_cart = cell_matrix @ coords_frac
                    coords_cart = [
                        sum(cell_matrix[i][j] * coords[j] for j in range(3))
                        for i in range(3)
                    ]
                    pos_lines.append(QEAtomicPosition(label, tuple(coords_cart)))
                elif pos_format == "angstrom":
                    # Convert from Angstrom to alat units
                    coords_alat = [c / alat_angstrom for c in coords]
                    pos_lines.append(QEAtomicPosition(label, tuple(coords_alat)))
                elif pos_format == "bohr":
                    # Convert from Bohr to alat units
                    coords_alat = [c / alat_bohr for c in coords]
                    pos_lines.append(QEAtomicPosition(label, tuple(coords_alat)))
                else:  # alat or default
                    # Already in alat units
                    pos_lines.append(QEAtomicPosition(label, tuple(coords)))
            except (ValueError, IndexError):
                continue
    
    if not pos_lines:
        raise ValueError("No atomic positions found in final coordinates block")
    
    return QEGeometrySnapshot(
        alat_angstrom=alat_angstrom,
        cell_matrix=cell_matrix,
        atomic_positions=pos_lines,
    ), species


def structure_from_qe_geometry_snapshot(
    snapshot: QEGeometrySnapshot,
    species: List[str],
) -> "PMGStructure":
    """
    Convert QEGeometrySnapshot to pymatgen Structure with canonization.
    
    CRITICAL: This function applies canonization exactly once, following the
    same path as structures loaded from JSON. The structure is canonized
    before being returned, ensuring fractional coordinates are in the
    canonical interval [-wrap_tol, 1 - wrap_tol).
    
    Args:
        snapshot: QEGeometrySnapshot with alat-scaled geometry
        species: List of species symbols (must match positions length)
        
    Returns:
        Canonicalized pymatgen Structure
    """
    from pymatgen.core import Structure as PMGStructure, Lattice
    
    if len(species) != len(snapshot.atomic_positions):
        raise ValueError(f"Species count ({len(species)}) != positions count ({len(snapshot.atomic_positions)})")
    
    # Convert alat-scaled cell to Angstrom
    cell_matrix_ang = snapshot.scaled_cell_matrix()
    lattice = Lattice(cell_matrix_ang)
    
    # Convert alat-scaled positions to Angstrom (Cartesian)
    positions_cart = []
    for pos in snapshot.scaled_atomic_positions():
        positions_cart.append(pos.vector)
    
    # Create structure with Cartesian coordinates
    structure = PMGStructure(
        lattice,
        species,
        positions_cart,
        coords_are_cartesian=True,
    )
    
    # CRITICAL: Canonicalize exactly once (same as visualization entry point)
    from quantumvitas.analysis.structure_viz import canonicalize_structure_in_place
    canonicalize_structure_in_place(structure)
    
    return structure


def _max_matrix_difference(a: List[List[float]], b: List[List[float]]) -> float:
    if len(a) != len(b):
        return math.inf
    max_diff = 0.0
    for row_a, row_b in zip(a, b):
        if len(row_a) != len(row_b):
            return math.inf
        for value_a, value_b in zip(row_a, row_b):
            diff = abs(value_a - value_b)
            if diff > max_diff:
                max_diff = diff
    return max_diff


