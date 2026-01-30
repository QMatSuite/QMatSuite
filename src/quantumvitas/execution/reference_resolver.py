"""Reference SCF resolver for VASP (and other PBC engines).

Finds the most recent SCF step that can serve as a reference for non-SCF steps.
Implements relax barrier: SCF steps before a relax step cannot be used as reference.
"""
from __future__ import annotations

from typing import Optional, Tuple, List, Any, TYPE_CHECKING

from quantumvitas.workflow.registry import get_registry, StepTypeRegistry

if TYPE_CHECKING:
    from quantumvitas.calculation.step import Step


def find_reference_scf(
    steps: List[Any],
    current_step_idx: int,
    registry: Optional[StepTypeRegistry] = None,
) -> Optional[Tuple[int, Any]]:
    """
    Find the most recent SCF step that can serve as reference.
    
    Walk backwards from current_step_idx in the step topology.
    Return the first step where gen_type == 'scf'.
    Stop if we hit a relax step (barrier).
    
    Args:
        steps: List of Step objects
        current_step_idx: Index of current step (0-based)
        registry: Optional StepTypeRegistry (uses global if not provided)
    
    Returns:
        Tuple of (step_index, step) if found, None otherwise
    
    Examples:
        >>> # Topology: scf_1 → relax → scf_2 → bands
        >>> # For bands (idx=3): returns (2, scf_2) - scf_1 blocked by relax
        >>> 
        >>> # Topology: scf_1 → bands → dos
        >>> # For dos (idx=2): returns (0, scf_1) - same reference
    """
    if registry is None:
        registry = get_registry()
    
    # Walk backwards from current step
    for i in range(current_step_idx - 1, -1, -1):
        step = steps[i]
        
        # Get step type
        step_type = getattr(step, 'step_type_spec', None)
        if not step_type:
            continue

        # Look up spec to get step_type_gen
        spec = registry.get(str(step_type))
        if spec:
            step_gen_type = spec.step_type_gen
        else:
            # Fallback: assume step_type is already gen type
            step_gen_type = str(step_type)

        # Check if this is a relax step (barrier)
        if step_gen_type == "relax":
            return None  # Barrier - no valid reference beyond this point

        # Check if this is an SCF step
        if step_gen_type == "scf":
            return (i, step)
    
    # No SCF found
    return None


def get_gen_type(step: Any, registry: Optional[StepTypeRegistry] = None) -> Optional[str]:
    """
    Get generalized step type for a step.
    
    Args:
        step: Step object
        registry: Optional StepTypeRegistry
    
    Returns:
        Public type (e.g., "scf", "relax", "bands") or None
    """
    if registry is None:
        registry = get_registry()
    
    step_type = getattr(step, 'step_type_spec', None)
    if not step_type:
        return None

    spec = registry.get(str(step_type))
    if spec:
        return spec.step_type_gen
    
    return str(step_type)

