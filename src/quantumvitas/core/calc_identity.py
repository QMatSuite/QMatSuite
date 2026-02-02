"""
Calculation Identity Inference and Recovery.

Phase 3A: Provides best-effort inference and recovery of calculation identity
(structure_kind and engine_family) from existing step data.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from quantumvitas.core.models import CalculationStepEntry
from quantumvitas.core.driver_registry import DriverRegistry


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
            # Look for step_type_spec (SPEC type, SSOT) first, then step_type_gen (GEN type)
            step_type = step_data.get("step_type_spec") or step_data.get("step_type_gen")
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


def _infer_engine_family_from_spec_types(spec_types: List[str]) -> Optional[str]:
    """
    Infer engine_family from step_type_spec values using registry.

    Uses DriverRegistry to look up engine for each step type.
    Returns a single family if all steps belong to one engine, None if mixed/unknown.

    Args:
        spec_types: List of step_type_spec identifiers (e.g., ["qe_scf", "qe_nscf"])

    Returns:
        Engine family identifier ("qe", "pyscf", etc.) if all steps share one family,
        None if mixed or unknown
    """
    if not spec_types:
        return None

    # Ensure drivers are loaded
    import quantumvitas.drivers

    families = set()
    for step_type in spec_types:
        if DriverRegistry.is_step_type_registered(step_type):
            engine = DriverRegistry.get_engine_for_step_type(step_type)
            families.add(engine)
        # Unknown step types are ignored - will fail at handler dispatch
    
    # Return single family if all steps belong to one family
    if len(families) == 1:
        return families.pop()
    
    # Mixed engines or no recognized step types
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
    Infer calculation identity from step type strings.

    Helper function for ensure_calculation_identity that works with raw step types
    from YAML data without requiring CalculationStepEntry objects.

    Args:
        calc_dir: Calculation directory path
        step_types: List of step type strings from calculation.yaml

    Returns:
        Tuple of (structure_kind, engine_family) or (None, None) if inference fails
    """
    from quantumvitas.workflow.registry import get_registry

    # Strategy 1: Use step types from calculation.yaml
    # Convert gen types to spec types via registry or DriverRegistry materialization
    spec_types = []
    if step_types:
        registry = get_registry()
        # Ensure drivers are loaded for materialization
        import quantumvitas.drivers
        from quantumvitas.core.driver_registry import DriverRegistry

        for step_type in step_types:
            # First try workflow registry lookup
            spec = registry.get(step_type)
            if spec:
                spec_types.append(spec.step_type_spec)
                continue

            # If registry lookup fails, try DriverRegistry materialization
            # Try common engine families (qe is most common for legacy imports)
            # Normalize step_type to lowercase gen step name (remove GEN_ prefix if present for backward compat)
            gen_step = step_type.lower()
            if gen_step.startswith("gen_"):
                gen_step = gen_step[4:]
            
            for engine_family in ["qe", "vasp", "orca", "pyscf", "cp2k", "lammps", "w90"]:
                try:
                    materialized = DriverRegistry.materialize_step_type(
                        engine_family,
                        gen_step
                    )
                    if materialized:
                        spec_types.append(materialized)
                        break
                except Exception:
                    continue

            # If still no match, check if step_type is already a spec type
            if DriverRegistry.is_step_type_registered(step_type):
                spec_types.append(step_type)

    # Strategy 2: Fallback to step.yaml files if calculation.yaml steps empty
    if not spec_types:
        steps_dir = calc_dir / "steps"
        if steps_dir.exists():
            for step_file in steps_dir.glob("*.step.yaml"):
                try:
                    import yaml
                    step_data = yaml.safe_load(step_file.read_text()) or {}
                    spec_type = step_data.get("step_type_spec")
                    if spec_type:
                        spec_types.append(spec_type)
                except Exception:
                    # Best-effort: skip files that can't be read
                    continue

    # Infer engine_family from spec types
    engine_family = _infer_engine_family_from_spec_types(spec_types)
    
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
    step_types = [step.step_type_spec for step in steps if step.step_type_spec]
    
    # Use the helper function that works with step type strings
    return _infer_identity_from_step_types(calc_dir, step_types)

