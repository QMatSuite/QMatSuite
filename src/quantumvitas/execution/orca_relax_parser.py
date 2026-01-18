"""
ORCA relax output parser.

Parses ORCA geometry optimization output and writes current.json.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pymatgen.core import Molecule

logger = logging.getLogger(__name__)


def parse_orca_optimized_xyz(xyz_path: Path) -> "Molecule":
    """
    Parse ORCA's optimized structure from basename.xyz.
    
    Args:
        xyz_path: Path to the .xyz file (e.g., chain01_scf.xyz)
        
    Returns:
        pymatgen Molecule with optimized coordinates
        
    Raises:
        FileNotFoundError: If xyz_path doesn't exist
        ValueError: If parsing fails
    """
    from pymatgen.core import Molecule
    
    if not xyz_path.exists():
        raise FileNotFoundError(f"ORCA optimized structure not found: {xyz_path}")
    
    # pymatgen can read xyz files directly
    try:
        mol = Molecule.from_file(xyz_path)
        logger.info(f"[ORCA_RELAX_PARSER] Parsed {len(mol)} atoms from {xyz_path}")
        return mol
    except Exception as e:
        raise ValueError(f"Failed to parse ORCA xyz file {xyz_path}: {e}") from e


def handle_orca_relax_output(
    step_ulid: str,
    step_type: str,
    calc_dir: Path,
    working_dir: Path,
    chain_key: str,
    calculation_ulid: str,
    input_structure_ulid: str,
    run_id: Optional[str] = None,
) -> Path:
    """
    Handle ORCA relax output: find .xyz and write current.json.
    
    Args:
        step_ulid: ULID of the relax step
        step_type: Machine step type (e.g., "orca_relax")
        calc_dir: Path to calculation directory
        working_dir: Path to ORCA working directory (contains .xyz)
        chain_key: Chain key (e.g., "chain01_scf")
        calculation_ulid: ULID of the calculation
        input_structure_ulid: ULID of the input structure
        run_id: Optional run ID
        
    Returns:
        Path to written current.json
        
    Raises:
        FileNotFoundError: If .xyz file doesn't exist
        ValueError: If parsing fails
    """
    from quantumvitas.execution.relax_artifacts import write_generated_structure
    
    # Find optimized xyz file
    xyz_path = working_dir / f"{chain_key}.xyz"
    if not xyz_path.exists():
        raise FileNotFoundError(f"ORCA optimized structure not found: {xyz_path}")
    
    # Parse
    molecule = parse_orca_optimized_xyz(xyz_path)
    
    # Write current.json
    # Note: write_generated_structure accepts any SiteCollection (Structure or Molecule)
    artifact_path = write_generated_structure(
        structure=molecule,  # pymatgen Molecule is a SiteCollection
        calc_dir=calc_dir,
        step_ulid=step_ulid,
        step_type=step_type,
        run_id=run_id,
        calculation_ulid=calculation_ulid,
        input_structure_ulid=input_structure_ulid,
    )
    
    logger.info(f"[ORCA_RELAX_PARSER] Wrote generated structure for step {step_ulid} to {artifact_path}")
    
    return artifact_path

