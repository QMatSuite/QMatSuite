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
from typing import Any, Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING

from qmatsuite.core.resources import ResourceMeta
# QE-specific imports moved to drivers/qe/io/
# Import QE-specific functions from new location for backward compatibility
# Note: We import private helpers too for functions that still use them (qe_input_has_structure, etc.)
# and for tests that import them directly
from qmatsuite.drivers.qe.io.structure_io import (
    structure_from_qe_input,
    _get_system_namelist,
    _get_float_parameter,
    _extract_lattice_parameter_angstrom,
    _lattice_from_cell_card,
    _lattice_from_ibrav,
    _extract_ibrav_parameters,
    _ibrav_vectors,
    BOHR_TO_ANGSTROM,
)
from qmatsuite.drivers.qe.io.parser import QEInputParser
from qmatsuite.drivers.qe.io.model import QECardType, QEInput, QENamelist, QECard

logger = logging.getLogger(__name__)

# Canonical wrapping tolerance (matches structure canonicalization)
WRAP_TOL = 1e-4


STRUCTURE_META_KEY = "__qms_meta__"
STRUCTURE_DATA_KEY = "structure"

if TYPE_CHECKING:
    from pymatgen.core import Structure as PMGStructure, Molecule as PMGMolecule


def read_structure(filepath: Path, format: Optional[str] = None) -> PMGStructure | PMGMolecule:
    """
    Read atomic structure from file using pymatgen.
    
    Supports both periodic structures (Structure) and molecules (Molecule).
    
    Args:
        filepath: Path to structure file
        format: Optional format hint (e.g., "cif", "qe")
                If None, format is inferred from file extension
        
    Returns:
        pymatgen Structure or Molecule object
    """
    from pymatgen.core import Structure as PMGStructure, Molecule as PMGMolecule

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
        
        # Determine if this is a Structure or Molecule
        # Structures have a 'lattice' key, Molecules do not
        # Also check @class field if present
        if isinstance(structure_payload, dict):
            structure_class = structure_payload.get("@class", "")
            has_lattice = "lattice" in structure_payload
            
            if has_lattice or structure_class == "Structure":
                structure = PMGStructure.from_dict(structure_payload)
            elif structure_class == "Molecule" or (not has_lattice and "sites" in structure_payload):
                # This is a Molecule (no lattice, has sites)
                structure = PMGMolecule.from_dict(structure_payload)
            else:
                # Try Structure first, fallback to Molecule if it fails
                try:
                    structure = PMGStructure.from_dict(structure_payload)
                except (KeyError, TypeError):
                    # If Structure fails (likely missing lattice), try Molecule
                    structure = PMGMolecule.from_dict(structure_payload)
        else:
            # Fallback: try Structure first
            try:
                structure = PMGStructure.from_dict(structure_payload)
            except (KeyError, TypeError):
                structure = PMGMolecule.from_dict(structure_payload)
        
        if metadata is not None:
            setattr(structure, STRUCTURE_META_KEY, metadata)
        return structure

    # Fallback: let pymatgen auto-detect (supports cif, poscar, etc.)
    # This will return Structure for periodic formats
    try:
        return PMGStructure.from_file(str(filepath))
    except Exception as struct_err:
        try:
            return PMGMolecule.from_file(str(filepath))
        except Exception as mol_err:
            raise struct_err from mol_err


def write_structure(
    structure: PMGStructure | PMGMolecule,
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
    from qmatsuite.core.pseudo import make_missing_pseudo_placeholder
    species = unique_species
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

    # ATOMIC_POSITIONS in crystal (fractional) coordinates
    # Always use crystal format for better readability and consistency
    atomic_positions_data: List[list] = []
    for site in structure.sites:
        # Use fractional coordinates directly from structure
        x, y, z = site.frac_coords
        atomic_positions_data.append([site.specie.symbol, x, y, z])

    atomic_positions_card = QECard(
        card_type=QECardType.ATOMIC_POSITIONS,
        option="crystal",
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

