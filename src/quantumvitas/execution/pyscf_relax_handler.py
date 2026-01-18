"""
PySCF relax output handler.

Handles PySCF geometry optimization output and writes current.json.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from pymatgen.core import Molecule

logger = logging.getLogger(__name__)


def handle_pyscf_relax_output(
    step_ulid: str,
    step_type: str,
    calc_dir: Path,
    results: Dict[str, Any],
    calculation_ulid: str,
    input_structure_ulid: str,
    run_id: Optional[str] = None,
) -> Path:
    """
    Handle PySCF relax output: convert results to current.json.
    
    Args:
        step_ulid: ULID of the relax step
        step_type: Machine step type (e.g., "pyscf_relax")
        calc_dir: Path to calculation directory
        results: Results dict from run_pyscf_relax (must contain "optimized_atoms")
        calculation_ulid: ULID of the calculation
        input_structure_ulid: ULID of the input structure
        run_id: Optional run ID
        
    Returns:
        Path to written current.json
        
    Raises:
        ValueError: If results don't contain optimized_atoms
    """
    from pymatgen.core import Molecule
    from quantumvitas.execution.relax_artifacts import write_generated_structure
    
    if "optimized_atoms" not in results:
        raise ValueError(f"Results dict missing 'optimized_atoms' key. Got keys: {list(results.keys())}")
    
    atoms = results["optimized_atoms"]
    
    species = [a["element"] for a in atoms]
    coords = [a["xyz"] for a in atoms]
    
    mol = Molecule(
        species=species,
        coords=coords,
        charge=results.get("charge", 0),
        spin_multiplicity=results.get("spin_multiplicity", 1),
    )
    
    # Canonicalize before writing
    from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place
    canonicalize_structure_like_in_place(mol)
    
    artifact_path = write_generated_structure(
        structure=mol,
        calc_dir=calc_dir,
        step_ulid=step_ulid,
        step_type=step_type,
        run_id=run_id,
        calculation_ulid=calculation_ulid,
        input_structure_ulid=input_structure_ulid,
    )
    
    logger.info(f"[PYSCF_RELAX_HANDLER] Wrote generated structure for step {step_ulid} to {artifact_path}")
    
    return artifact_path

