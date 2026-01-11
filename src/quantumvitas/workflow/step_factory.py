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
    
    # Add structure_id if provided (legacy field, kept for backwards compat)
    if structure_id:
        data["structure"] = structure_id
    
    # Add parent calculation id
    if parent_calculation_id:
        data["parent_calculation_id"] = parent_calculation_id
    
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


def save_step_doc(step_doc: StepDoc, path: Path) -> None:
    """
    Save step document to disk (journaled via yaml_io).
    
    Args:
        step_doc: StepDoc to save
        path: Path to save to
    """
    # Update path in meta
    path = Path(path).resolve()
    
    # Save through yaml_io (journal hook)
    save_yaml_doc(step_doc, path)


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

