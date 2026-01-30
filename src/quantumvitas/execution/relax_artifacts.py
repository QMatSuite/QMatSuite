"""
Relax artifacts: Generated structure write/read utilities.

This module provides utilities for writing and reading generated structures
from relax steps. These are artifacts (not ULID resources) stored at:
  calculations/<calc>/generated_structures/step_<relax_ulid>/current.json

Architecture: Capability-based approach
=======================================
Instead of engine-specific branching in executor, we use a registry of
artifact handlers keyed by "artifact_type". Each handler produces step_results
with an optional "relax_artifact_spec" dict that describes how to post-process
the outputs into current.json.

Supported artifact_types:
- "qe_output": Parse QE .out file for final geometry
- "pyscf_results": Read PySCF results.json
- "orca_xyz": Parse ORCA .xyz or .out file
- "lammps_data": Parse LAMMPS final.data file
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union

if TYPE_CHECKING:
    from pymatgen.core import Structure as PMGStructure
    from pymatgen.core import Molecule as PMGMolecule

logger = logging.getLogger(__name__)


# ============================================================================
# Relax Artifact Spec: Capability-based artifact description
# ============================================================================

@dataclass
class RelaxArtifactSpec:
    """
    Describes a relax artifact to be processed.
    
    This is returned by handlers in step_results["relax_artifact_spec"] and
    processed by the executor using the RELAX_ARTIFACT_HANDLERS registry.
    
    Attributes:
        artifact_type: Type key for handler lookup (e.g., "lammps_data", "qe_output")
        artifact_path: Path to the artifact file (e.g., final.data, .out file)
        step_ulid: ULID of the step that produced the artifact
        step_type_spec: Step type spec (e.g., "lammps_relax", "qe_relax")
        extra: Additional context needed by the handler (e.g., chain_key for ORCA)
    """
    artifact_type: str
    artifact_path: Path
    step_ulid: str
    step_type_spec: str
    extra: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra is None:
            self.extra = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict for step_results."""
        return {
            "artifact_type": self.artifact_type,
            "artifact_path": str(self.artifact_path),
            "step_ulid": self.step_ulid,
            "step_type_spec": self.step_type_spec,
            "extra": self.extra,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelaxArtifactSpec":
        """Create from dict (deserialization)."""
        return cls(
            artifact_type=data["artifact_type"],
            artifact_path=Path(data["artifact_path"]),
            step_ulid=data["step_ulid"],
            step_type_spec=data["step_type_spec"],
            extra=data.get("extra", {}),
        )


# Type for artifact handler functions
# Handler signature: (spec, calc_dir, run_context) -> Path to current.json
RelaxArtifactHandler = Callable[
    ["RelaxArtifactSpec", Path, Dict[str, Any]],
    Path
]


def _handle_qe_output(
    spec: RelaxArtifactSpec,
    calc_dir: Path,
    run_context: Dict[str, Any],
) -> Path:
    """Handle QE relax output: parse .out file and write current.json."""
    from quantumvitas.calculation.geometry import (
        read_final_geometry_from_output_text,
        structure_from_qe_geometry_snapshot,
    )
    from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place
    
    output_path = spec.artifact_path
    if not output_path.exists():
        raise FileNotFoundError(f"QE output file not found: {output_path}")
    
    output_text = output_path.read_text()
    snapshot, species = read_final_geometry_from_output_text(output_text)
    structure = structure_from_qe_geometry_snapshot(snapshot, species)
    canonicalize_structure_like_in_place(structure)
    
    artifact_path = write_generated_structure(
        structure=structure,
        calc_dir=calc_dir,
        step_ulid=spec.step_ulid,
        step_type=spec.step_type_spec,
        run_id=run_context.get("run_id"),
        calculation_ulid=run_context.get("calculation_ulid", ""),
        input_structure_ulid=run_context.get("input_structure_ulid", ""),
    )
    logger.info(f"[RELAX_ARTIFACT] Processed QE output for step {spec.step_ulid}")
    return artifact_path


def _handle_pyscf_results(
    spec: RelaxArtifactSpec,
    calc_dir: Path,
    run_context: Dict[str, Any],
) -> Path:
    """Handle PySCF relax output: read results.json and write current.json."""
    from pymatgen.core import Molecule
    from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place
    
    results_path = spec.artifact_path
    if not results_path.exists():
        raise FileNotFoundError(f"PySCF results file not found: {results_path}")
    
    results = json.loads(results_path.read_text())
    
    if "optimized_atoms" not in results:
        raise ValueError(f"Results dict missing 'optimized_atoms'. Keys: {list(results.keys())}")
    
    atoms = results["optimized_atoms"]
    species = [a["element"] for a in atoms]
    coords = [a["xyz"] for a in atoms]
    
    mol = Molecule(
        species=species,
        coords=coords,
        charge=results.get("charge", 0),
        spin_multiplicity=results.get("spin_multiplicity", 1),
    )
    canonicalize_structure_like_in_place(mol)
    
    artifact_path = write_generated_structure(
        structure=mol,
        calc_dir=calc_dir,
        step_ulid=spec.step_ulid,
        step_type=spec.step_type_spec,
        run_id=run_context.get("run_id"),
        calculation_ulid=run_context.get("calculation_ulid", ""),
        input_structure_ulid=run_context.get("input_structure_ulid", ""),
    )
    logger.info(f"[RELAX_ARTIFACT] Processed PySCF results for step {spec.step_ulid}")
    return artifact_path


def _handle_orca_xyz(
    spec: RelaxArtifactSpec,
    calc_dir: Path,
    run_context: Dict[str, Any],
) -> Path:
    """Handle ORCA relax output: parse .xyz or .out and write current.json."""
    from quantumvitas.execution.orca_relax_parser import (
        parse_orca_optimized_xyz,
        parse_orca_optimized_from_out,
    )
    from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place
    
    working_dir = spec.artifact_path
    chain_key = spec.extra.get("chain_key", "")
    
    # Try to find .xyz file
    possible_xyz_paths = [
        working_dir / f"{chain_key}.xyz",
        working_dir / f"{chain_key}_trj.xyz",
    ]
    
    xyz_path = None
    for path in possible_xyz_paths:
        if path.exists():
            xyz_path = path
            break
    
    # Search for any matching .xyz file
    if xyz_path is None:
        xyz_files = list(working_dir.glob(f"*{chain_key}*.xyz")) if chain_key else []
        if not xyz_files:
            xyz_files = list(working_dir.glob("*.xyz"))
        
        if xyz_files:
            non_trj = [f for f in xyz_files if not f.name.endswith("_trj.xyz")]
            xyz_path = non_trj[0] if non_trj else xyz_files[0]
    
    # Parse structure
    if xyz_path and xyz_path.exists():
        molecule = parse_orca_optimized_xyz(xyz_path)
    else:
        # Try .out file
        out_files = list(working_dir.glob(f"*{chain_key}*.out")) if chain_key else []
        if not out_files:
            out_files = list(working_dir.glob("*.out"))
        
        if out_files:
            molecule = parse_orca_optimized_from_out(out_files[0])
        else:
            available = [f.name for f in working_dir.glob("*") if f.is_file()]
            raise FileNotFoundError(
                f"ORCA output not found in {working_dir}. Available: {available}"
            )
    
    canonicalize_structure_like_in_place(molecule)
    
    artifact_path = write_generated_structure(
        structure=molecule,
        calc_dir=calc_dir,
        step_ulid=spec.step_ulid,
        step_type=spec.step_type_spec,
        run_id=run_context.get("run_id"),
        calculation_ulid=run_context.get("calculation_ulid", ""),
        input_structure_ulid=run_context.get("input_structure_ulid", ""),
    )
    logger.info(f"[RELAX_ARTIFACT] Processed ORCA output for step {spec.step_ulid}")
    return artifact_path


def _handle_lammps_data(
    spec: RelaxArtifactSpec,
    calc_dir: Path,
    run_context: Dict[str, Any],
) -> Path:
    """Handle LAMMPS relax output: parse final.data and write current.json."""
    from quantumvitas.io.lammps_data import read_lammps_data
    from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place
    
    final_data = spec.artifact_path
    if not final_data.exists():
        raise FileNotFoundError(f"LAMMPS final.data not found: {final_data}")
    
    structure = read_lammps_data(final_data)
    canonicalize_structure_like_in_place(structure)
    
    artifact_path = write_generated_structure(
        structure=structure,
        calc_dir=calc_dir,
        step_ulid=spec.step_ulid,
        step_type=spec.step_type_spec,
        run_id=run_context.get("run_id"),
        calculation_ulid=run_context.get("calculation_ulid", ""),
        input_structure_ulid=run_context.get("input_structure_ulid", ""),
    )
    logger.info(f"[RELAX_ARTIFACT] Processed LAMMPS output for step {spec.step_ulid}")
    return artifact_path


# ============================================================================
# RELAX_ARTIFACT_HANDLERS: Registry of artifact type -> handler
# ============================================================================

def _handle_cp2k_trajectory_artifact(
    spec: RelaxArtifactSpec,
    calc_dir: Path,
    run_context: Dict[str, Any],
) -> Path:
    """
    Handle CP2K trajectory artifact -> current.json.

    Args:
        spec: RelaxArtifactSpec with artifact_path and optional cell_path in extra
        calc_dir: Calculation directory
        run_context: Context with initial_structure, run_id, etc.

    Returns:
        Path to current.json
    """
    from quantumvitas.engine.cp2k_parser import extract_final_structure
    from quantumvitas.execution.latest_selector import find_latest_by_mtime
    from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place

    artifact_path = spec.artifact_path
    if not artifact_path.exists():
        raise FileNotFoundError(f"CP2K trajectory file not found: {artifact_path}")

    # Find cell file in same directory (from extra or by searching)
    workdir = artifact_path.parent
    cell_path = None
    if spec.extra and "cell_path" in spec.extra:
        cell_path = Path(spec.extra["cell_path"])
    else:
        # Fallback: search for cell file
        cell_path = find_latest_by_mtime(workdir, "cp2k_calc-*.cell")

    # Get initial structure for fallback cell
    initial_structure = run_context.get("initial_structure")

    # Extract final structure from trajectory with cell
    structure = extract_final_structure(
        xyz_path=artifact_path,
        cell_path=cell_path,
        initial_structure=initial_structure,
    )

    # Canonicalize
    canonicalize_structure_like_in_place(structure)

    # Write current.json
    return write_generated_structure(
        structure=structure,
        calc_dir=calc_dir,
        step_ulid=spec.step_ulid,
        step_type=spec.step_type_spec,
        run_id=run_context.get("run_id"),
        calculation_ulid=run_context.get("calculation_ulid", ""),
        input_structure_ulid=run_context.get("input_structure_ulid", ""),
    )


RELAX_ARTIFACT_HANDLERS: Dict[str, RelaxArtifactHandler] = {
    "qe_output": _handle_qe_output,
    "pyscf_results": _handle_pyscf_results,
    "orca_xyz": _handle_orca_xyz,
    "lammps_data": _handle_lammps_data,
    "cp2k_trajectory": _handle_cp2k_trajectory_artifact,
}


def process_relax_artifact(
    spec: Union[RelaxArtifactSpec, Dict[str, Any]],
    calc_dir: Path,
    run_context: Dict[str, Any],
) -> Optional[Path]:
    """
    Process a relax artifact using the appropriate handler.
    
    This is the main entry point for capability-based relax artifact processing.
    Called by executor after job execution.
    
    Args:
        spec: RelaxArtifactSpec or dict representation
        calc_dir: Calculation directory
        run_context: Context with run_id, calculation_ulid, input_structure_ulid
        
    Returns:
        Path to current.json if processed, None if no handler found
    """
    if isinstance(spec, dict):
        spec = RelaxArtifactSpec.from_dict(spec)
    
    handler = RELAX_ARTIFACT_HANDLERS.get(spec.artifact_type)
    if handler is None:
        logger.warning(f"[RELAX_ARTIFACT] No handler for artifact_type: {spec.artifact_type}")
        return None
    
    try:
        return handler(spec, calc_dir, run_context)
    except Exception as e:
        logger.error(f"[RELAX_ARTIFACT] Failed to process {spec.artifact_type}: {e}", exc_info=True)
        raise


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
        "step_type_gen": "generated_structure",
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
) -> Optional["PMGStructure"] | Optional["PMGMolecule"]:
    """
    Read a generated structure from current.json.
    
    Supports both Structure (for periodic systems) and Molecule (for molecular systems).
    
    Args:
        calc_dir: Path to calculation directory
        step_ulid: ULID of the relax step
        
    Returns:
        pymatgen Structure or Molecule, or None if file doesn't exist
    """
    artifact_path = get_generated_structure_path(calc_dir, step_ulid)
    if not artifact_path.exists():
        return None
    
    structure_dict = json.loads(artifact_path.read_text())
    # Remove our metadata before parsing
    structure_dict.pop("__qv_meta__", None)
    
    # Try to determine if it's a Structure or Molecule
    # Structure has "lattice" key, Molecule doesn't
    if "lattice" in structure_dict:
        from pymatgen.core import Structure
        return Structure.from_dict(structure_dict)
    else:
        from pymatgen.core import Molecule
        return Molecule.from_dict(structure_dict)


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
    Normalizes deprecated step types (vc-relax, qe_vc_relax, opt, geomopt) first.
    """
    from quantumvitas.workflow.registry import get_registry, normalize_step_type
    
    # Normalize deprecated types (vc-relax, qe_vc_relax, opt, geomopt) to unified types
    normalized = normalize_step_type(step_type)
    
    registry = get_registry()
    spec = registry.get(normalized)
    if spec is None:
        return False
    return getattr(spec, 'is_structure_transform', False)

