"""
Relax artifacts: Generated structure write/read utilities.

This module provides utilities for writing and reading generated structures
from relax steps. These are artifacts (not ULID resources) stored at:
  calculations/<calc>/generated_structures/step_<relax_ulid>/current.json
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pymatgen.core import Structure as PMGStructure

logger = logging.getLogger(__name__)


def get_generated_structure_path(calc_dir: Path, step_ulid: str) -> Path:
    """
    Get the canonical path for a relax step's generated structure.
    
    Args:
        calc_dir: Path to calculation directory (parent of calculation.yaml)
        step_ulid: ULID of the relax step
        
    Returns:
        Path to current.json (may not exist)
    """
    return calc_dir / "generated_structures" / f"step_{step_ulid}" / "current.json"


def write_generated_structure(
    structure: "PMGStructure",
    calc_dir: Path,
    step_ulid: str,
    step_type: str,
    run_id: Optional[str] = None,
    calculation_ulid: Optional[str] = None,
    input_structure_ulid: Optional[str] = None,
) -> Path:
    """
    Write a relaxed structure to generated_structures directory.
    
    Args:
        structure: pymatgen Structure to write
        calc_dir: Path to calculation directory
        step_ulid: ULID of the relax step
        step_type: Step type (e.g., "qe_relax", "qe_vc_relax")
        run_id: Optional run ID for provenance
        calculation_ulid: Optional calculation ULID for provenance
        input_structure_ulid: Optional input structure ULID for provenance
        
    Returns:
        Path to written current.json
    """
    artifact_path = get_generated_structure_path(calc_dir, step_ulid)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build structure dict with metadata
    structure_dict = structure.as_dict()
    structure_dict["__qv_meta__"] = {
        "type": "generated_structure",
        "source_step_ulid": step_ulid,
        "source_run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "method": step_type,
            "input_structure_ulid": input_structure_ulid,
            "calculation_ulid": calculation_ulid,
        },
    }
    
    artifact_path.write_text(json.dumps(structure_dict, indent=2))
    logger.info(f"[RELAX_ARTIFACTS] Wrote generated structure to {artifact_path}")
    
    return artifact_path


def read_generated_structure(
    calc_dir: Path,
    step_ulid: str,
) -> Optional["PMGStructure"]:
    """
    Read a generated structure from current.json.
    
    Args:
        calc_dir: Path to calculation directory
        step_ulid: ULID of the relax step
        
    Returns:
        pymatgen Structure, or None if file doesn't exist
    """
    artifact_path = get_generated_structure_path(calc_dir, step_ulid)
    if not artifact_path.exists():
        return None
    
    structure_dict = json.loads(artifact_path.read_text())
    # Remove our metadata before parsing
    structure_dict.pop("__qv_meta__", None)
    
    from pymatgen.core import Structure
    return Structure.from_dict(structure_dict)


def clean_generated_structure(calc_dir: Path, step_ulid: str) -> bool:
    """
    Delete a generated structure's current.json.
    
    Args:
        calc_dir: Path to calculation directory
        step_ulid: ULID of the relax step
        
    Returns:
        True if file was deleted, False if it didn't exist
    """
    artifact_path = get_generated_structure_path(calc_dir, step_ulid)
    if artifact_path.exists():
        artifact_path.unlink()
        logger.info(f"[RELAX_ARTIFACTS] Cleaned {artifact_path}")
        return True
    return False


def is_relax_step_type(step_type: str) -> bool:
    """
    Check if a step type is a relax type.
    
    Uses registry lookup to check is_structure_transform flag.
    """
    from quantumvitas.workflow.registry import get_registry
    
    registry = get_registry()
    spec = registry.get(step_type)
    if spec is None:
        return False
    return getattr(spec, 'is_structure_transform', False)

