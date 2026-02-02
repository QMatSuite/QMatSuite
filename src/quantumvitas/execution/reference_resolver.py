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

    from quantumvitas.workflow.step_type_convert import is_spec
    from quantumvitas.execution.step_type_unpack import unpack_step_type, unpack_step_type_safe

    # Walk backwards from current step
    for i in range(current_step_idx - 1, -1, -1):
        step = steps[i]

        # Get step type (SPEC type like "vasp_scf")
        step_type_spec = getattr(step, 'step_type_spec', None)
        if not step_type_spec:
            continue

        step_type_str = str(step_type_spec)

        # Convert SPEC to GEN and look up in registry via centralized choke point (Constitution §4.3)
        # Per constitution, registry.get() only accepts GEN types
        if is_spec(step_type_str):
            # Unpack SPEC to (prefix, gen) via centralized choke point
            unpacked = unpack_step_type(step_type_str)
            spec = registry.get_for_engine(unpacked.gen, unpacked.prefix)
        else:
            # Already GEN type
            spec = registry.get(step_type_str)

        if spec:
            step_gen_type = spec.step_type_gen
        else:
            # Fallback: use unpack_step_type_safe for either SPEC or GEN
            unpacked = unpack_step_type_safe(step_type_str)
            step_gen_type = unpacked.gen

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

    # First try step_type_gen if available (preferred)
    step_type_gen = getattr(step, 'step_type_gen', None)
    if step_type_gen:
        return str(step_type_gen)

    # Fallback: extract GEN from step_type_spec
    step_type_spec = getattr(step, 'step_type_spec', None)
    if not step_type_spec:
        return None

    # Convert SPEC to GEN (registry expects GEN)
    from quantumvitas.workflow.step_type_convert import gen_from, is_spec
    step_type_spec_str = str(step_type_spec)
    if is_spec(step_type_spec_str):
        gen_type = gen_from(step_type_spec_str)
    else:
        gen_type = step_type_spec_str

    # Verify in registry
    spec = registry.get(gen_type)
    if spec:
        return spec.step_type_gen

    return gen_type

