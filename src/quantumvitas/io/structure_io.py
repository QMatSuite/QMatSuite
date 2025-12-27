"""
Structure I/O operations.

This module provides functions for reading and writing atomic structures
using ASE, pymatgen, or other libraries.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pymatgen.core import Element
from pymatgen.core import Lattice
from pymatgen.core import Structure as PMGStructure

from quantumvitas.core.resources import ResourceMeta
from quantumvitas.io.model import QECard, QECardType, QEInput, QENamelist
from quantumvitas.io.parser.qe_parser import QEInputParser

logger = logging.getLogger(__name__)

# Canonical wrapping tolerance (matches structure canonicalization)
WRAP_TOL = 1e-4


STRUCTURE_META_KEY = "__qv_meta__"
STRUCTURE_DATA_KEY = "structure"


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
        return structure_from_qe_input(qe_input)
    if format == "json":
        data = json.loads(Path(filepath).read_text())
        metadata = None
        structure_payload = data
        if STRUCTURE_META_KEY in data and STRUCTURE_DATA_KEY in data:
            metadata = data.get(STRUCTURE_META_KEY)
            structure_payload = data.get(STRUCTURE_DATA_KEY)
        structure = PMGStructure.from_dict(structure_payload)
        if metadata is not None:
            setattr(structure, STRUCTURE_META_KEY, metadata)
        return structure

    # Fallback: let pymatgen auto-detect (supports cif, poscar, etc.)
    return PMGStructure.from_file(str(filepath))


def write_structure(
    structure: PMGStructure,
    filepath: Path,
    format: Optional[str] = None,
    metadata: Optional[Dict[str, Any] | ResourceMeta] = None,
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
        if metadata is None:
            metadata = getattr(structure, STRUCTURE_META_KEY, None)
        payload = structure.as_dict()
        if metadata is not None:
            meta_dict = metadata.to_dict() if isinstance(metadata, ResourceMeta) else metadata
            serializable = {
                STRUCTURE_META_KEY: meta_dict,
                STRUCTURE_DATA_KEY: payload,
            }
        else:
            serializable = payload
        filepath.write_text(json.dumps(serializable, indent=2))
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
    # Since we always generate CELL_PARAMETERS, we must set ibrav=0
    control = QENamelist(name="CONTROL", parameters={"calculation": "scf"})
    unique_species = list(structure.composition.elements)
    system = QENamelist(
        name="SYSTEM",
        parameters={
            "ibrav": 0,
            "nat": len(structure.sites),
            "ntyp": len(unique_species),
        },
    )
    electrons = QENamelist(name="ELECTRONS", parameters={})

    # ATOMIC_SPECIES: element symbol, atomic mass, pseudo file name (placeholder).
    # Use obvious placeholder to indicate missing configuration (not a real file)
    from quantumvitas.core.pseudo import make_missing_pseudo_placeholder
    species: List[Element] = unique_species
    atomic_species_data: List[list] = []
    for el in species:
        mass = float(el.atomic_mass)
        # Use placeholder to clearly indicate missing configuration
        pseudo_name = make_missing_pseudo_placeholder(el.symbol)
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


def qe_input_has_structure(qe_input: QEInput) -> bool:
    """
    Check if a QE input file contains structure information.
    
    Returns True if any of the following are present:
    - ATOMIC_POSITIONS card
    - CELL_PARAMETERS card
    - SYSTEM namelist with ibrav != 0 (can infer lattice via ibrav/celldm)
    - SYSTEM namelist with ibrav == 0 and CELL_PARAMETERS (explicit cell)
    
    Returns False for post-processing inputs (LR, DOS, bands, etc.) that don't need structure.
    
    Args:
        qe_input: QEInput object to check
        
    Returns:
        True if input contains structure information, False otherwise
    """
    # Check for ATOMIC_POSITIONS card (strongest indicator)
    if qe_input.get_card(QECardType.ATOMIC_POSITIONS):
        return True
    
    # Check for CELL_PARAMETERS card
    if qe_input.get_card(QECardType.CELL_PARAMETERS):
        return True
    
    # Check SYSTEM namelist for ibrav-based structure
    system = _get_system_namelist(qe_input)
    if system:
        ibrav = int(system.get("ibrav", 0) or 0)
        if ibrav != 0:
            # ibrav != 0 means structure can be inferred from parameters
            # Check if required parameters exist
            if ibrav in [12, -12]:
                # Hexagonal: need b (or a), c, and cosab
                param_keys_lower = {str(k).lower(): k for k in system.parameters.keys()}
                has_b = "b" in param_keys_lower or "a" in param_keys_lower
                has_c = "c" in param_keys_lower
                has_cosab = any(k in param_keys_lower for k in ["cosab", "cos(ab)", "cos(angle)"])
                if has_b and has_c and has_cosab:
                    return True
            else:
                # Other ibrav: need celldm(1) or a
                has_celldm1 = any(str(k).lower() == "celldm(1)" for k in system.parameters.keys())
                has_a = any(str(k).lower() == "a" for k in system.parameters.keys())
                if has_celldm1 or has_a:
                    return True
        elif ibrav == 0:
            # ibrav == 0 requires CELL_PARAMETERS (checked above)
            # If we reach here, ibrav=0 but no CELL_PARAMETERS, so no structure
            pass
    
    # No structure information found
    return False


def qe_input_has_explicit_structure(qe_input: QEInput) -> bool:
    """
    Check if a QE input contains enough explicit information to build a structure with our parser.
    
    This is stricter than qe_input_has_structure() - it requires:
    - ATOMIC_POSITIONS card (mandatory for structure parsing)
    - AND either:
      - CELL_PARAMETERS card (for ibrav=0), OR
      - SYSTEM namelist with ibrav != 0 and required parameters (for ibrav-based lattice)
    
    LR/TDDFT-style inputs (no SYSTEM, no structure cards) return False.
    
    Args:
        qe_input: QEInput object to check
        
    Returns:
        True if input has explicit structure information that can be parsed, False otherwise
    """
    # Must have ATOMIC_POSITIONS to build structure
    if not qe_input.get_card(QECardType.ATOMIC_POSITIONS):
        return False
    
    # Must have either CELL_PARAMETERS (for ibrav=0) or ibrav != 0 with required params
    cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)
    if cell_card:
        return True
    
    # Check SYSTEM namelist for ibrav-based structure
    # Note: _get_system_namelist returns a dict with lowercase keys
    system = _get_system_namelist(qe_input)
    if system:
        ibrav = int(system.get("ibrav", 0) or 0)
        if ibrav != 0:
            # ibrav != 0 means structure can be inferred from parameters
            # Check if required parameters exist (system dict already has lowercase keys)
            if ibrav in [12, -12]:
                # Monoclinic: need b (or a), c, and cosab/cosbc
                has_b = "b" in system or "a" in system
                has_c = "c" in system
                has_cos = any(k in system for k in ["cosab", "cosbc", "cos(ab)"])
                if has_b and has_c and has_cos:
                    return True
            else:
                # Other ibrav: need celldm(1) or a
                has_celldm1 = "celldm(1)" in system
                has_a = "a" in system
                if has_celldm1 or has_a:
                    return True
    
    # No explicit structure information found
    return False


def structure_from_qe_input(qe_input: QEInput) -> PMGStructure:
    """
    Build a pymatgen Structure from a QEInput instance, honoring QE's ibrav rules.
    """
    system = _get_system_namelist(qe_input)
    cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)

    if system and int(system.get("ibrav", 0) or 0) != 0:
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

    structure = PMGStructure(
        lattice,
        species,
        coords,
        coords_are_cartesian=not coords_are_frac,
    )
    return structure


BOHR_TO_ANGSTROM = 0.52917721092


def structure_fingerprint(structure: PMGStructure, tol: float = 1e-5) -> str:
    """
    Generate a deterministic fingerprint for a structure.
    
    This is a "good enough" fingerprint for demo import splitting and diagnostics,
    not perfect crystallography. It uses:
    - Quantized lattice parameters (Å) by tol
    - Quantized fractional coordinates by tol
    - Deterministic ordering
    - SHA256 hash of the quantized data
    
    The fingerprint is stable for perturbations < tol and different for perturbations > tol.
    It does NOT implement symmetry/basis-change equivalence.
    
    Uses the canonical wrapping convention (WRAP_TOL=1e-4) for consistency.
    
    Args:
        structure: pymatgen Structure to fingerprint
        tol: Quantization tolerance (default 1e-5)
        
    Returns:
        Hex string of SHA256 hash (64 characters)
    """
    import numpy as np
    
    # Quantize lattice matrix (3x3, in Angstrom)
    lattice_matrix = structure.lattice.matrix
    quantized_lattice = np.round(lattice_matrix / tol) * tol
    
    # Get fractional coordinates and wrap to [0, 1) using canonical wrapping
    frac_coords = structure.frac_coords
    # Wrap using canonical tolerance
    wrapped_coords = frac_coords % 1.0
    # Further quantize by tol
    quantized_coords = np.round(wrapped_coords / tol) * tol
    
    # Get species symbols in deterministic order (by site index)
    species = [str(site.specie.symbol) for site in structure.sites]
    
    # Build deterministic payload: lattice + coords + species
    # Format: lattice rows, then coords rows, then species
    payload_parts = []
    
    # Lattice (9 values: 3x3 matrix flattened row-wise)
    for row in quantized_lattice:
        payload_parts.append(f"{row[0]:.10f},{row[1]:.10f},{row[2]:.10f}")
    
    # Coordinates (N values: fractional coords)
    for coord in quantized_coords:
        payload_parts.append(f"{coord[0]:.10f},{coord[1]:.10f},{coord[2]:.10f}")
    
    # Species (N symbols)
    payload_parts.extend(species)
    
    # Create deterministic string representation
    payload = "\n".join(payload_parts)
    
    # Hash with SHA256
    hash_obj = hashlib.sha256(payload.encode('utf-8'))
    return hash_obj.hexdigest()


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

    return Lattice(data)


def _lattice_from_ibrav(system: Dict[str, Any]) -> Lattice:
    ibrav = int(_get_float_parameter(system, ("ibrav",)) or 0)
    if ibrav == 0:
        raise ValueError("ibrav == 0 requires CELL_PARAMETERS.")

    params = _extract_ibrav_parameters(system)
    vectors = _ibrav_vectors(ibrav, params)
    return Lattice(vectors)


def _extract_ibrav_parameters(system: Dict[str, Any]) -> Dict[str, float]:
    params: Dict[str, float] = {}
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
        if ibrav == 12:
            cos_angle = params.get("cosbc")
        else:
            cos_angle = params.get("cosac")
        if not b or not c_val or cos_angle is None:
            raise ValueError("ibrav=12/-12 requires b, c, and cos(angle).")
        if ibrav == 12:
            sin_gamma = (1 - cos_angle**2) ** 0.5
            return [
                vec(a, 0, 0),
                vec(b * cos_angle, b * sin_gamma, 0),
                vec(0, 0, c_val),
            ]
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

