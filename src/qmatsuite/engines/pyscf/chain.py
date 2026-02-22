"""
PySCF dependency chain resolution and execution.

Phase 3C: Implements linear dependency model for PySCF steps.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from pathlib import Path

from qmatsuite.workflow.step_type_convert import gen_from, is_spec


def _get_spec_from_registry(registry, step_type_spec: str):
    """Get step type spec from registry using SPEC type.

    Per constitution, registry.get() only accepts GEN types.
    This helper extracts GEN from SPEC and uses get_for_engine() for precise lookup.

    Args:
        registry: StepTypeRegistry instance
        step_type_spec: SPEC step type (e.g., "pyscf_scf", "pyscf_mp2")
    """
    # Extract engine prefix and gen type from SPEC using canonical functions
    from qmatsuite.workflow.step_type_convert import prefix_from, is_spec
    step_type_gen = gen_from(step_type_spec)
    engine_prefix = prefix_from(step_type_spec) if is_spec(step_type_spec) else "pyscf"
    return registry.get_for_engine(step_type_gen, engine_prefix)


def resolve_dependency_chain(
    target_step_ulid: str,
    calculation_steps: List[Tuple[str, str]],  # List of (step_ulid, step_type_spec) tuples
    step_type_registry,
) -> Tuple[List[int], Optional[str]]:
    """
    Resolve dependency chain for a target step using nearest-provider rule.

    Phase 3C: Linear dependency model - scan left for nearest provider.

    Args:
        target_step_ulid: ULID of the target step
        calculation_steps: List of (step_ulid, step_type_spec) tuples in order
        step_type_registry: StepTypeRegistry instance for looking up step specs

    Returns:
        Tuple of (chain_indices, error_message)
        - chain_indices: List of indices in calculation_steps from root to target (inclusive)
        - error_message: None if successful, error message if provider missing

    Example:
        Steps: [("ulid1", "pyscf_scf"), ("ulid2", "pyscf_mp2")]
        Target: "ulid2"
        Returns: ([0, 1], None)  # Both steps in chain

    Raises:
        ValueError: If target step not found or dependency chain cannot be resolved
    """
    # Find target step index
    target_idx = None
    for idx, (step_ulid, _) in enumerate(calculation_steps):
        if step_ulid == target_step_ulid:
            target_idx = idx
            break

    if target_idx is None:
        return ([], f"Target step ULID '{target_step_ulid}' not found in calculation steps")

    # Get target step spec (SPEC type -> registry lookup)
    _, target_spec_type = calculation_steps[target_idx]
    target_spec = _get_spec_from_registry(step_type_registry, target_spec_type)

    if target_spec is None:
        return ([], f"Step type '{target_spec_type}' not found in registry")

    # If target has no dependency, chain is just the target
    if target_spec.consumes_state is None:
        return ([target_idx], None)

    # Find nearest provider by scanning left
    required_state = target_spec.consumes_state
    provider_idx = None

    for idx in range(target_idx - 1, -1, -1):  # Scan left from target
        _, spec_type = calculation_steps[idx]
        spec = _get_spec_from_registry(step_type_registry, spec_type)
        if spec and spec.produces_state == required_state:
            provider_idx = idx
            break

    if provider_idx is None:
        return (
            [],
            f"No provider found for state '{required_state}' required by step '{target_spec_type}' (ULID: {target_step_ulid}). "
            f"Scan left from target step but found no step with produces_state='{required_state}'."
        )

    # Build chain: provider chain (if provider has dependencies) + provider + target
    # Since provider_idx is the nearest provider, and we scan left, the provider
    # should be the root (consumes_state=None) or we recurse to find its provider
    chain_indices = []

    # If provider has dependencies, resolve its chain first
    _, provider_spec_type = calculation_steps[provider_idx]
    provider_spec = _get_spec_from_registry(step_type_registry, provider_spec_type)
    if provider_spec and provider_spec.consumes_state is not None:
        # Provider also has dependencies - recurse
        provider_chain_indices, error = resolve_dependency_chain(
            calculation_steps[provider_idx][0],  # provider step ULID
            calculation_steps[:provider_idx + 1],  # Steps up to and including provider
            step_type_registry,
        )
        if error:
            return ([], error)
        chain_indices.extend(provider_chain_indices)
    else:
        # Provider is root (no dependencies) - just add it
        chain_indices.append(provider_idx)
    
    # Add target step
    chain_indices.append(target_idx)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_chain = []
    for idx in chain_indices:
        if idx not in seen:
            seen.add(idx)
            unique_chain.append(idx)
    
    return (unique_chain, None)

