"""QE-specific structure I/O functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

if TYPE_CHECKING:
    from pymatgen.core import Lattice
    from pymatgen.core import Structure as PMGStructure

from qmatsuite.drivers.qe.io.model import QECard, QECardType, QEInput

# Constant
BOHR_TO_ANGSTROM = 0.52917721092


def structure_from_qe_input(qe_input: QEInput) -> PMGStructure:
    """
    Build a pymatgen Structure from a QEInput instance, honoring QE's ibrav rules.
    
    If ibrav=12/-12 is specified but required parameters (b, c, cos(angle)) are missing,
    and CELL_PARAMETERS card exists, use CELL_PARAMETERS instead of ibrav parameters.
    """
    system = _get_system_namelist(qe_input)
    cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)

    if system and int(system.get("ibrav", 0) or 0) != 0:
        ibrav = int(system.get("ibrav", 0) or 0)
        # For ibrav=12/-12, check if required parameters are missing
        # If CELL_PARAMETERS exists, prefer it over incomplete ibrav parameters
        if ibrav in (12, -12) and cell_card:
            params = _extract_ibrav_parameters(system)
            b = params.get("b")
            c_val = params.get("c")
            if ibrav == 12:
                cos_angle = params.get("cosab")
            else:
                cos_angle = params.get("cosac")
            # If any required parameter is missing, use CELL_PARAMETERS instead
            if not b or not c_val or cos_angle is None:
                lattice = _lattice_from_cell_card(cell_card, system)
            else:
                lattice = _lattice_from_ibrav(system)
        else:
            lattice = _lattice_from_ibrav(system)
    else:
        lattice = _lattice_from_cell_card(cell_card, system)

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

    if not coords_are_frac:
        scale_factor = 1.0
        if pos_option == "bohr":
            scale_factor = BOHR_TO_ANGSTROM
        elif pos_option == "alat":
            alat_ang = _extract_lattice_parameter_angstrom(system, lattice)
            if alat_ang is None:
                raise ValueError("ATOMIC_POSITIONS alat specified but a is undefined.")
            scale_factor = alat_ang
        coords = [[scale_factor * value for value in row] for row in coords]

    from pymatgen.core import Structure as PMGStructure

    structure = PMGStructure(
        lattice,
        species,
        coords,
        coords_are_cartesian=not coords_are_frac,
    )
    return structure


def _get_system_namelist(qe_input: QEInput) -> Optional[Dict[str, Any]]:
    namelist = qe_input.get_namelist("SYSTEM") or qe_input.get_namelist("system")
    if namelist:
        return {str(k).lower(): v for k, v in namelist.parameters.items()}
    return None


def _get_float_parameter(section: Optional[Dict[str, Any]], keys: Iterable[str]) -> Optional[float]:
    if not section:
        return None
    for key in keys:
        lookup = key.lower()
        if lookup in section:
            try:
                return float(section[lookup])
            except (TypeError, ValueError):
                return None
    return None


def _extract_lattice_parameter_angstrom(
    system: Optional[Dict[str, Any]],
    lattice: Optional[Lattice],
) -> Optional[float]:
    if system:
        celldm1 = _get_float_parameter(system, ("celldm(1)", "celldm1"))
        if celldm1 is not None:
            return celldm1 * BOHR_TO_ANGSTROM
        alat = _get_float_parameter(system, ("a", "alat"))
        if alat is not None:
            return alat
    if lattice is not None:
        vec = lattice.matrix[0]
        return (vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2) ** 0.5
    return None


def _lattice_from_cell_card(
    cell_card: Optional[QECard],
    system: Optional[Dict[str, Any]],
) -> Lattice:
    if not cell_card:
        raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
    data = [
        [float(x) for x in row]
        for row in cell_card.data
        if isinstance(row, (list, tuple)) and len(row) == 3
    ]
    if len(data) != 3:
        raise ValueError("CELL_PARAMETERS must contain three lattice vectors.")

    option = (cell_card.option or "angstrom").lower()
    if option == "bohr":
        data = [[BOHR_TO_ANGSTROM * value for value in row] for row in data]
    elif option == "alat":
        alat_ang = _extract_lattice_parameter_angstrom(system, None)
        if alat_ang is None:
            raise ValueError("CELL_PARAMETERS 'alat' units require celldm(1) or A.")
        data = [[alat_ang * value for value in row] for row in data]
    elif option not in {"angstrom", ""}:
        raise ValueError(f"Unsupported CELL_PARAMETERS unit '{option}'")

    from pymatgen.core import Lattice

    return Lattice(data)


def _lattice_from_ibrav(system: Dict[str, Any]) -> Lattice:
    ibrav = int(_get_float_parameter(system, ("ibrav",)) or 0)
    if ibrav == 0:
        raise ValueError("ibrav == 0 requires CELL_PARAMETERS.")

    params = _extract_ibrav_parameters(system)
    vectors = _ibrav_vectors(ibrav, params)
    from pymatgen.core import Lattice

    return Lattice(vectors)


def _extract_ibrav_parameters(system: Dict[str, Any]) -> Dict[str, float]:
    params: Dict[str, float] = {}
    ibrav = int(_get_float_parameter(system, ("ibrav",)) or 0)
    
    a_val = _get_float_parameter(system, ("celldm(1)", "celldm1"))
    if a_val is not None:
        params["a"] = a_val * BOHR_TO_ANGSTROM
    else:
        params["a"] = _get_float_parameter(system, ("a", "alat")) or 0.0

    b_over_a = _get_float_parameter(system, ("celldm(2)", "celldm2"))
    c_over_a = _get_float_parameter(system, ("celldm(3)", "celldm3"))
    params["b"] = (
        b_over_a * params["a"]
        if b_over_a is not None
        else _get_float_parameter(system, ("b",))
    )
    params["c"] = (
        c_over_a * params["a"]
        if c_over_a is not None
        else _get_float_parameter(system, ("c",))
    )
    
    # celldm mapping depends on ibrav type
    # For ibrav=12: celldm(4) = cos(gamma) = cosab (angle between a and b)
    # For ibrav=-12: celldm(5) = cos(beta) = cosac (angle between a and c)
    # For other ibrav types, use standard mappings
    if ibrav == 12:
        # celldm(4) maps to cosab for ibrav=12
        cosab_from_celldm4 = _get_float_parameter(system, ("celldm(4)", "celldm4"))
        if cosab_from_celldm4 is not None:
            params["cosab"] = cosab_from_celldm4
        else:
            params["cosab"] = _get_float_parameter(system, ("cosab", "celldm(6)", "celldm6"))
    elif ibrav == -12:
        # celldm(5) maps to cosac for ibrav=-12
        cosac_from_celldm5 = _get_float_parameter(system, ("celldm(5)", "celldm5"))
        if cosac_from_celldm5 is not None:
            params["cosac"] = cosac_from_celldm5
        else:
            params["cosac"] = _get_float_parameter(system, ("cosac",))
    else:
        # Standard mappings for other ibrav types
        params["cosbc"] = _get_float_parameter(system, ("celldm(4)", "celldm4", "cosbc"))
        params["cosac"] = _get_float_parameter(system, ("celldm(5)", "celldm5", "cosac"))
        params["cosab"] = _get_float_parameter(system, ("celldm(6)", "celldm6", "cosab"))
    
    return params


def _ibrav_vectors(ibrav: int, params: Dict[str, float]) -> List[List[float]]:
    a = params.get("a")
    if not a:
        raise ValueError("ibrav requires lattice parameter 'a'.")

    def vec(x, y, z):
        return [float(x), float(y), float(z)]

    if ibrav == 1:
        return [vec(a, 0, 0), vec(0, a, 0), vec(0, 0, a)]
    if ibrav == 2:
        half = 0.5 * a
        return [vec(-half, 0, half), vec(0, half, half), vec(-half, half, 0)]
    if ibrav in (3, -3):
        half = 0.5 * a
        if ibrav == 3:
            return [vec(half, half, half), vec(-half, half, half), vec(-half, -half, half)]
        return [vec(-half, half, half), vec(half, -half, half), vec(half, half, -half)]
    if ibrav == 4:
        c_val = params.get("c")
        if not c_val:
            raise ValueError("ibrav=4 requires c/a (celldm(3)) or c.")
        return [
            vec(a, 0, 0),
            vec(-0.5 * a, 0.5 * (3 ** 0.5) * a, 0),
            vec(0, 0, c_val),
        ]
    if ibrav in (5, -5):
        cos_gamma = params.get("cosab") or params.get("cosac") or params.get("cosbc")
        if cos_gamma is None:
            raise ValueError("ibrav=5/-5 requires celldm(4)=cos(gamma).")
        tx = ((1 - cos_gamma) / 2) ** 0.5
        ty = ((1 - cos_gamma) / 6) ** 0.5
        tz = ((1 + 2 * cos_gamma) / 3) ** 0.5
        if ibrav == 5:
            return [
                vec(a * tx, -a * ty, a * tz),
                vec(0, 2 * a * ty, a * tz),
                vec(-a * tx, -a * ty, a * tz),
            ]
        a_prime = a / (3 ** 0.5)
        u = tz - 2 * (2 ** 0.5) * ty
        v = tz + (2 ** 0.5) * ty
        return [
            vec(a_prime * u, a_prime * v, a_prime * v),
            vec(a_prime * v, a_prime * u, a_prime * v),
            vec(a_prime * v, a_prime * v, a_prime * u),
        ]
    if ibrav in (6, 7):
        c_val = params.get("c")
        if not c_val:
            raise ValueError("ibrav=6/7 requires c/a or c.")
        if ibrav == 6:
            return [vec(a, 0, 0), vec(0, a, 0), vec(0, 0, c_val)]
        half = 0.5 * a
        return [
            vec(half, -half, 0.5 * c_val),
            vec(half, half, 0.5 * c_val),
            vec(-half, -half, 0.5 * c_val),
        ]
    if ibrav in (8, 9, -9, 10, 11):
        b = params.get("b")
        c_val = params.get("c")
        if not b or not c_val:
            raise ValueError("ibrav=8/9/10/11 requires b and c.")
        if ibrav == 8:
            return [vec(a, 0, 0), vec(0, b, 0), vec(0, 0, c_val)]
        half_a = 0.5 * a
        half_b = 0.5 * b
        if ibrav == 9:
            return [vec(half_a, half_b, 0), vec(-half_a, half_b, 0), vec(0, 0, c_val)]
        if ibrav == -9:
            return [vec(half_a, -half_b, 0), vec(half_a, half_b, 0), vec(0, 0, c_val)]
        if ibrav == 10:
            half_c = 0.5 * c_val
            return [vec(half_a, 0, half_c), vec(half_a, half_b, 0), vec(0, half_b, half_c)]
        return [
            vec(half_a, half_b, 0.5 * c_val),
            vec(-half_a, half_b, 0.5 * c_val),
            vec(-half_a, -half_b, 0.5 * c_val),
        ]
    if ibrav in (12, -12):
        b = params.get("b")
        c_val = params.get("c")
        # ibrav=12: Monoclinic, unique axis c. Uses cos(gamma) where gamma is angle between a and b.
        # ibrav=-12: Monoclinic, unique axis b. Uses cos(beta) where beta is angle between a and c.
        if ibrav == 12:
            cos_angle = params.get("cosab")  # cos(gamma) = cos(angle between a and b)
        else:
            cos_angle = params.get("cosac")  # cos(beta) = cos(angle between a and c)
        if not b or not c_val or cos_angle is None:
            raise ValueError("ibrav=12/-12 requires b, c, and cos(angle).")
        if ibrav == 12:
            # Monoclinic, unique axis c (gamma != 90°)
            # v1 = (a, 0, 0)
            # v2 = (b*cos(gamma), b*sin(gamma), 0)
            # v3 = (0, 0, c)
            sin_gamma = (1 - cos_angle**2) ** 0.5
            return [
                vec(a, 0, 0),
                vec(b * cos_angle, b * sin_gamma, 0),
                vec(0, 0, c_val),
            ]
        # ibrav=-12: Monoclinic, unique axis b (beta != 90°)
        # v1 = (a, 0, 0)
        # v2 = (0, b, 0)
        # v3 = (c*cos(beta), 0, c*sin(beta))
        sin_beta = (1 - cos_angle**2) ** 0.5
        return [
            vec(a, 0, 0),
            vec(0, b, 0),
            vec(c_val * cos_angle, 0, c_val * sin_beta),
        ]
    if ibrav in (13, -13):
        b = params.get("b")
        c_val = params.get("c")
        if ibrav == 13:
            cos_angle = params.get("cosbc")
        else:
            cos_angle = params.get("cosac")
        if not b or not c_val or cos_angle is None:
            raise ValueError("ibrav=13/-13 requires b, c, and cos(angle).")
        sin_angle = (1 - cos_angle**2) ** 0.5
        if ibrav == 13:
            return [
                vec(0.5 * a, 0, -0.5 * c_val),
                vec(b * cos_angle, b * sin_angle, 0),
                vec(0.5 * a, 0, 0.5 * c_val),
            ]
        return [
            vec(0.5 * a, 0.5 * b, 0),
            vec(-0.5 * a, 0.5 * b, 0),
            vec(c_val * cos_angle, 0, c_val * sin_angle),
        ]
    if ibrav == 14:
        b = params.get("b")
        c_val = params.get("c")
        cosbc = params.get("cosbc")
        cosac = params.get("cosac")
        cosab = params.get("cosab")
        if None in (b, c_val, cosbc, cosac, cosab):
            raise ValueError("ibrav=14 requires b, c, cosbc, cosac, cosab.")
        sin_gamma = (1 - cosab**2) ** 0.5
        v1 = vec(a, 0, 0)
        v2 = vec(b * cosab, b * sin_gamma, 0)
        v3x = c_val * cosac
        v3y = c_val * (cosbc - cosac * cosab) / sin_gamma
        v3z = c_val * (
            1
            + 2 * cosac * cosbc * cosab
            - cosac**2
            - cosbc**2
            - cosab**2
        ) ** 0.5 / sin_gamma
        return [v1, v2, vec(v3x, v3y, v3z)]
    raise ValueError(f"ibrav {ibrav} is not supported.")
