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


