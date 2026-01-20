"""
LAMMPS relax output handler: Parse final.data and write generated structure.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pymatgen.core import Structure

logger = logging.getLogger(__name__)


def handle_lammps_relax_output(
    step_ulid: str,
    step_type: str,
    calc_dir: Path,
    working_dir: Path,
    calculation_ulid: str,
    input_structure_ulid: str,
    run_id: Optional[str] = None,
) -> Path:
    """
    Handle LAMMPS relax step output: parse final.data and write current.json.
    
    Args:
        step_ulid: ULID of the relax step
        step_type: Machine step type (e.g., "lammps_relax")
        calc_dir: Path to calculation directory
        working_dir: Path to step working directory (contains final.data)
        calculation_ulid: ULID of the calculation
        input_structure_ulid: ULID of the input structure
        run_id: Optional run ID for provenance
    
    Returns:
        Path to written current.json
    
    Raises:
        FileNotFoundError: If final.data not found
        ValueError: If parsing fails
    """
    from quantumvitas.io.lammps_data import read_lammps_data
    from quantumvitas.execution.relax_artifacts import write_generated_structure
    from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place
    
    # 1. Read final.data
    final_data = working_dir / "final.data"
    if not final_data.exists():
        raise FileNotFoundError(f"LAMMPS relax output not found: {final_data}")
    
    # 2. Parse LAMMPS data file
    structure = read_lammps_data(final_data)
    
    # 3. Canonicalize before writing (ensure consistent canonicalization)
    canonicalize_structure_like_in_place(structure)
    
    # 4. Write current.json
    artifact_path = write_generated_structure(
        structure=structure,
        calc_dir=calc_dir,
        step_ulid=step_ulid,
        step_type=step_type,
        run_id=run_id,
        calculation_ulid=calculation_ulid,
        input_structure_ulid=input_structure_ulid,
    )
    
    logger.info(f"[LAMMPS_RELAX_HANDLER] Wrote generated structure for step {step_ulid} to {artifact_path}")
    
    return artifact_path

