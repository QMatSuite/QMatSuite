"""
Step Factory: Centralized step creation and writing.

This module provides the single entry point for step creation:
- All steps go through create_step_doc() + save_step_doc()
- All saves go through yaml_io (journaled)
- ULID generation, slug rules, defaults are centralized

Per docs/workflow_refactor_plan.md:
- Replaces scattered yaml.safe_dump calls
- Ensures Journal captures all step writes
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from quantumvitas.core.resources import generate_resource_id, slugify
from quantumvitas.core.yamldoc import StepDoc
from quantumvitas.core.yaml_io import save_yaml_doc


def create_step_doc(
    step_type: str,
    name: str,
    structure_id: Optional[str] = None,
    parent_calculation_id: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> StepDoc:
    """
    Create a new step document (not yet saved).
    
    Args:
        step_type: Step type (e.g., "scf", "nscf", "dos")
        name: Step name (used for display and slug)
        structure_id: Optional structure ULID (for backwards compat, not authoritative)
        parent_calculation_id: Parent calculation ULID
        overrides: Optional parameter overrides to apply
        
    Returns:
        StepDoc instance (in memory, not saved)
    """
    from quantumvitas.workflow.registry import get_registry
    
    registry = get_registry()
    
    # Phase 2: Normalize step_type to machine_type for step.yaml
    # step.yaml stores machine types only (qe_scf, w90_run, etc.)
    spec = registry.get(step_type)  # Accepts both public and machine types
    if spec:
        machine_step_type = spec.machine_type  # Use machine type for step.yaml
    else:
        # Fallback: assume it's already a machine type or unknown
        machine_step_type = step_type
    
    # Get defaults for step type (use original step_type for lookup)
    defaults = registry.get_defaults(step_type)
    
    # Generate meta
    step_id = generate_resource_id()
    slug = slugify(name)
    
    # Build step data
    # step.yaml stores machine_type (qe_scf), not public_type (scf)
    data: Dict[str, Any] = {
        "meta": {
            "id": step_id,
            "name": name,
            "slug": slug,
            "kind": "step",
        },
        "step_type": machine_step_type,  # Machine type goes to step.yaml
    }
    
    # DAG model: Do NOT store structure_id in step YAML
    # Step inherits structure from its parent calculation at runtime
    # structure_id and parent_calculation_id are NOT stored in step.yaml
    # The association is via calculation.yaml's steps array
    
    # Add parameters from defaults
    if defaults.get("parameters"):
        data["parameters"] = defaults["parameters"]
    
    # Add cards from defaults
    if defaults.get("cards"):
        data["cards"] = defaults["cards"]
    
    # Add species_overrides from defaults
    if defaults.get("species_overrides"):
        data["species_overrides"] = defaults["species_overrides"]
    
    # Create StepDoc
    step_doc = StepDoc(data)
    
    # Apply overrides if provided
    if overrides:
        step_doc.apply_patch(overrides)
    
    return step_doc


def save_step_doc(step_doc: StepDoc, path: Path) -> list[str]:
    """
    Save step document to disk (journaled via yaml_io).
    
    Args:
        step_doc: StepDoc to save
        path: Path to save to
        
    Returns:
        List of warning messages (empty if none)
        
    Raises:
        ScanRefNotFoundError: If dangling ScanRef found
        ScanRefValidationError: If ScanRef format or location invalid
    """
    # Compute warnings before saving (pure keyword matching, no engine detection)
    warnings: list[str] = []
    from quantumvitas.calculation.structure_steps import detect_runtime_control_keys
    
    # Get parameters from step_doc
    try:
        # Use export_copy to get parameters dict (StepDoc.get() would raise BranchAccessError)
        parameters = step_doc.export_copy(["parameters"]) or {}
        runtime_keys = detect_runtime_control_keys(parameters)
        if runtime_keys:
            for key in runtime_keys:
                warnings.append(
                    f"CONTROL.{key} looks like a runtime-managed key. "
                    f"For QE it is protected and will be overridden at run time "
                    f"(default outdir=./outdir, pseudo_dir=project/pseudo, prefix is engine-managed). "
                    f"If you are not using QE, you can ignore this warning."
                )
    except Exception:
        # If we can't read parameters, skip warnings (non-blocking)
        pass
    
    # Validate scan refs (mandatory at save)
    try:
        step_doc_dict = step_doc.to_dict()
        from quantumvitas.calculation.scan_validation import (
            validate_step_scan_refs,
            ScanRefNotFoundError,
            ScanRefValidationError,
        )
        import logging
        scan_logger = logging.getLogger(__name__)
        
        scan_errors, scan_warnings = validate_step_scan_refs(step_doc_dict)
        
        # Add scan warnings to warnings list
        warnings.extend(scan_warnings)
        
        # Log scan warnings
        for warning in scan_warnings:
            scan_logger.warning(f"[SCAN_VALIDATION] {warning}")
        
        # Raise on scan errors
        if scan_errors:
            error_msg = "Scan validation errors:\n" + "\n".join(f"  - {e}" for e in scan_errors)
            raise ScanRefValidationError(error_msg)
            
    except (ScanRefNotFoundError, ScanRefValidationError):
        # Re-raise validation errors
        raise
    except Exception as e:
        # If validation fails for other reasons, log but don't block save
        # (for backwards compat with steps that don't have scans)
        import logging
        scan_logger = logging.getLogger(__name__)
        scan_logger.debug(f"Scan validation skipped due to error: {e}")
    
    # Update path in meta
    path = Path(path).resolve()
    
    # INSTRUMENTATION: Log before calling save_yaml_doc
    import logging
    save_logger = logging.getLogger(__name__)
    save_logger.info(f"[save_step_doc] About to call save_yaml_doc for {path}")
    
    # Save through yaml_io (journal hook)
    save_yaml_doc(step_doc, path)
    
    # INSTRUMENTATION: Log after save_yaml_doc
    save_logger.info(f"[save_step_doc] save_yaml_doc completed for {path}")
    
    return warnings


def create_and_save_step(
    step_type: str,
    name: str,
    steps_dir: Path,
    structure_id: Optional[str] = None,
    parent_calculation_id: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Create and save a step in one call.
    
    Convenience function combining create_step_doc() and save_step_doc().
    
    Args:
        step_type: Step type
        name: Step name
        steps_dir: Directory to save step in
        structure_id: Optional structure ULID
        parent_calculation_id: Parent calculation ULID
        overrides: Optional parameter overrides
        
    Returns:
        Path to saved step file
    """
    step_doc = create_step_doc(
        step_type=step_type,
        name=name,
        structure_id=structure_id,
        parent_calculation_id=parent_calculation_id,
        overrides=overrides,
    )
    
    slug = step_doc.get(["meta", "slug"])
    step_path = Path(steps_dir) / f"{slug}.step.yaml"
    
    save_step_doc(step_doc, step_path)
    
    return step_path

