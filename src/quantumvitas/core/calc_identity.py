"""
Calculation Identity Inference and Recovery.

Phase 3A: Provides best-effort inference and recovery of calculation identity
(structure_kind and engine_family) from existing step data.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from quantumvitas.core.models import CalculationStepEntry


def ensure_calculation_identity(calc_dir: Path, project_root: Optional[Path] = None) -> None:
    """
    Ensure calculation identity (structure_kind, engine_family) is set in calculation.yaml.
    
    Phase 3A: Best-effort recovery that infers identity from steps and writes back
    to calculation.yaml if fields are missing.
    
    This function:
    1. Loads calculation.yaml if it exists
    2. If structure_kind/engine_family missing, infers from steps
    3. Writes inferred values back to calculation.yaml (only if file exists and is writable)
    
    Must not crash on errors (best-effort recovery).
    
    Args:
        calc_dir: Calculation directory path
        project_root: Optional project root (for error messages only)
    """
    calc_yaml = calc_dir / "calculation.yaml"
    if not calc_yaml.exists():
        # No calculation.yaml - nothing to do
        return
    
    try:
        import yaml
        data = yaml.safe_load(calc_yaml.read_text()) or {}
        
        structure_kind = data.get("structure_kind")
        engine_family = data.get("engine_family")
        
        # If both are set, nothing to do
        if structure_kind is not None and engine_family is not None:
            return
        
        # Extract step types directly from YAML data (best-effort, don't require ULIDs)
        # For inference, we only need step types, not full CalculationStepEntry objects
        step_types = []
        for step_data in data.get("steps", []):
            step_type = step_data.get("type")
            if step_type:
                step_types.append(step_type)
        
        # Infer identity from step types (public types from calculation.yaml)
        inferred_kind, inferred_family = _infer_identity_from_step_types(calc_dir, step_types)
        
        # Update data if inferred values available
        updated = False
        if structure_kind is None and inferred_kind is not None:
            data["structure_kind"] = inferred_kind
            updated = True
        if engine_family is None and inferred_family is not None:
            data["engine_family"] = inferred_family
            updated = True
        
        # Write back if updated
        if updated:
            calc_yaml.write_text(yaml.safe_dump(data, sort_keys=False))
    except Exception:
        # Best-effort: if anything fails, silently return (don't crash)
        pass


def _infer_engine_family_from_machine_types(machine_types: List[str]) -> Optional[str]:
    """
    Infer engine_family from machine step type prefixes.
    
    Analyzes step type prefixes (qe_, pyscf_, w90_) to determine engine family.
    Returns a single family if all steps share one prefix, None if mixed/unknown.
    
    Args:
        machine_types: List of machine step type identifiers (e.g., ["qe_scf", "qe_nscf"])
    
    Returns:
        Engine family identifier ("qe", "pyscf", etc.) if all steps share one family,
        None if mixed or unknown
    """
    if not machine_types:
        return None
    
    families = set()
    for machine_type in machine_types:
        if machine_type.startswith("qe_") or machine_type in ("w90_preproc", "w90_run"):
            # w90 steps are part of qe family toolchain
            families.add("qe")
        elif machine_type.startswith("pyscf_"):
            families.add("pyscf")
        elif machine_type.startswith("w90_"):
            # Standalone w90 (if exists in future)
            families.add("w90")
        else:
            # Unknown prefix - could be legacy step type
            # Assume QE for backward compatibility
            families.add("qe")
    
    # Return single family if all steps belong to one family
    if len(families) == 1:
        return families.pop()
    
    # Mixed families - return None (caller will use default)
    return None


def _infer_structure_kind_from_engine_family(engine_family: str) -> str:
    """
    Infer structure_kind from engine_family.
    
    Args:
        engine_family: Engine family identifier (e.g., "qe", "pyscf")
    
    Returns:
        Structure kind: "molecule" for pyscf, "periodic" otherwise
    """
    if engine_family == "pyscf":
        return "molecule"
    else:
        return "periodic"  # Default for qe, w90, etc.


def _infer_identity_from_step_types(
    calc_dir: Path,
    step_types: List[str],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Infer calculation identity from step type strings (public types).
    
    Helper function for ensure_calculation_identity that works with raw step types
    from YAML data without requiring CalculationStepEntry objects.
    
    Args:
        calc_dir: Calculation directory path
        step_types: List of step type strings (public types from calculation.yaml)
    
    Returns:
        Tuple of (structure_kind, engine_family) or (None, None) if inference fails
    """
    from quantumvitas.workflow.registry import get_registry
    
    # Strategy 1: Use step types from calculation.yaml (public types)
    # Convert public types to machine types via registry
    machine_types = []
    if step_types:
        registry = get_registry()
        for step_type in step_types:
            # Look up spec to get machine type (accepts both public and machine types)
            spec = registry.get(step_type)
            if spec:
                machine_types.append(spec.machine_type)
    
    # Strategy 2: Fallback to step.yaml files if calculation.yaml steps empty
    if not machine_types:
        steps_dir = calc_dir / "steps"
        if steps_dir.exists():
            for step_file in steps_dir.glob("*.step.yaml"):
                try:
                    import yaml
                    step_data = yaml.safe_load(step_file.read_text()) or {}
                    machine_type = step_data.get("step_type")
                    if machine_type:
                        machine_types.append(machine_type)
                except Exception:
                    # Best-effort: skip files that can't be read
                    continue
    
    # Infer engine_family from machine types
    engine_family = _infer_engine_family_from_machine_types(machine_types)
    
    # Infer structure_kind from engine_family
    structure_kind = None
    if engine_family:
        structure_kind = _infer_structure_kind_from_engine_family(engine_family)
    
    return (structure_kind, engine_family)


def infer_calculation_identity(
    calc_dir: Path,
    steps: List[CalculationStepEntry],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Infer calculation identity (structure_kind, engine_family) from steps.
    
    Phase 3A: Best-effort recovery for legacy calculations missing identity fields.
    
    Strategy:
    1. Prefer calculation.yaml step list (public types) - convert to machine types
    2. Fallback to step.yaml files (machine types directly)
    3. Infer engine_family from machine type prefixes
    4. Infer structure_kind from engine_family (pyscf → molecule, else → periodic)
    
    Args:
        calc_dir: Calculation directory path
        steps: List of CalculationStepEntry from calculation.yaml
    
    Returns:
        Tuple of (structure_kind, engine_family) or (None, None) if inference fails
    """
    # Extract step types from CalculationStepEntry objects
    step_types = [step.step_type for step in steps if step.step_type]
    
    # Use the helper function that works with step type strings
    return _infer_identity_from_step_types(calc_dir, step_types)

