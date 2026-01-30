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


def parse_orca_optimized_from_out(out_path: Path) -> "Molecule":
    """
    Parse ORCA's optimized structure from .out file.
    
    Looks for "CARTESIAN COORDINATES" section near the end of the file
    (final optimized geometry).
    
    Args:
        out_path: Path to the .out file
        
    Returns:
        pymatgen Molecule with optimized coordinates
        
    Raises:
        FileNotFoundError: If out_path doesn't exist
        ValueError: If parsing fails
    """
    from pymatgen.core import Molecule
    
    if not out_path.exists():
        raise FileNotFoundError(f"ORCA output file not found: {out_path}")
    
    content = out_path.read_text()
    lines = content.split('\n')
    
    # Search backwards for "CARTESIAN COORDINATES" (final geometry)
    # Look in the last 1000 lines
    coords_start = None
    for i in range(len(lines)-1, max(0, len(lines)-1000), -1):
        if "CARTESIAN COORDINATES" in lines[i].upper():
            coords_start = i + 1  # Next line after header
            break
    
    if coords_start is None:
        raise ValueError(f"No 'CARTESIAN COORDINATES' section found in {out_path}")
    
    # Parse coordinates (format: element x y z)
    atoms = []
    coords = []
    for i in range(coords_start, min(len(lines), coords_start + 100)):  # Max 100 atoms
        line = lines[i].strip()
        if not line or line.startswith('*') or line.startswith('#'):
            # End of coordinates section
            if atoms:  # If we found at least one atom, stop
                break
            continue
        
        # Parse: element x y z
        parts = line.split()
        if len(parts) >= 4:
            try:
                element = parts[0]
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                atoms.append(element)
                coords.append([x, y, z])
            except (ValueError, IndexError):
                # Skip invalid lines
                if atoms:  # If we already found atoms, this might be the end
                    break
                continue
    
    if not atoms:
        raise ValueError(f"Could not parse coordinates from {out_path}")
    
    # Create Molecule (charge and spin from input, or defaults)
    # For H2, charge=0, spin_multiplicity=1
    molecule = Molecule(atoms, coords, charge=0, spin_multiplicity=1)
    logger.info(f"[ORCA_RELAX_PARSER] Parsed {len(molecule)} atoms from {out_path}")
    return molecule


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
    run_ulid: Optional[str] = None,
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
        run_ulid: Optional run ULID
        
    Returns:
        Path to written current.json
        
    Raises:
        FileNotFoundError: If .xyz file doesn't exist
        ValueError: If parsing fails
    """
    from quantumvitas.execution.relax_artifacts import write_generated_structure
    
    # Find optimized structure
    # ORCA may generate: {basename}.xyz, {basename}_trj.xyz, or final structure in .out file
    # chain_key is the basename from job.metadata (e.g., "relax")
    # But actual files may have different names (e.g., "chain01_relax.out" where "chain01_relax" is the chain key)
    # We need to find files that match the basename pattern
    
    # First, try to find .xyz file with chain_key
    possible_xyz_paths = [
        working_dir / f"{chain_key}.xyz",  # Primary: basename.xyz
        working_dir / f"{chain_key}_trj.xyz",  # Trajectory file (last frame is final structure)
    ]
    
    xyz_path = None
    for path in possible_xyz_paths:
        if path.exists():
            xyz_path = path
            break
    
    # If still not found, search for any .xyz file in working_dir that contains chain_key
    if xyz_path is None:
        xyz_files = list(working_dir.glob(f"*{chain_key}*.xyz"))
        if not xyz_files:
            # Try any .xyz file
            xyz_files = list(working_dir.glob("*.xyz"))
        
        if xyz_files:
            # Prefer files that don't end with _trj.xyz (those are trajectories)
            non_trj = [f for f in xyz_files if not f.name.endswith("_trj.xyz")]
            if non_trj:
                xyz_path = non_trj[0]
            else:
                # Use trajectory file (last frame is final structure)
                xyz_path = xyz_files[0]
    
    # If no .xyz file found, parse from .out file
    if xyz_path is None or not xyz_path.exists():
        # Look for .out file with chain_key in name
        out_files = list(working_dir.glob(f"*{chain_key}*.out"))
        if not out_files:
            # Try any .out file
            out_files = list(working_dir.glob("*.out"))
        
        if out_files:
            # Parse final geometry from .out file
            molecule = parse_orca_optimized_from_out(out_files[0])
        else:
            # List available files for debugging
            available_files = [f.name for f in working_dir.glob("*") if f.is_file()]
            raise FileNotFoundError(
                f"ORCA optimized structure not found. "
                f"Tried .xyz files: {[str(p) for p in possible_xyz_paths]}. "
                f"No .out file found. "
                f"Available files in {working_dir}: {available_files}."
            )
    else:
        # Parse from .xyz file
        molecule = parse_orca_optimized_xyz(xyz_path)
    
    # Canonicalize before writing
    from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place
    canonicalize_structure_like_in_place(molecule)
    
    # Write current.json
    # Note: write_generated_structure accepts any SiteCollection (Structure or Molecule)
    artifact_path = write_generated_structure(
        structure=molecule,  # pymatgen Molecule is a SiteCollection
        calc_dir=calc_dir,
        step_ulid=step_ulid,
        step_type=step_type,
        run_ulid=run_ulid,
        calculation_ulid=calculation_ulid,
        input_structure_ulid=input_structure_ulid,
    )
    
    logger.info(f"[ORCA_RELAX_PARSER] Wrote generated structure for step {step_ulid} to {artifact_path}")
    
    return artifact_path

