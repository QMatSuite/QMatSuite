"""
Generalized Step Taxonomy: Engine-agnostic physical operations.

Generalized steps represent physical operations (SCF, NSCF, WANNIER, etc.)
that are engine-agnostic. They exist only in UI/workflow definitions and
are never written to disk. They are materialized to engine-specific steps
at workflow instantiation time.

Per Phase 2 architecture:
- Generalized steps exist ONLY in-memory
- Each generalized step maps to AT MOST ONE engine-specific step per engine_family (0-1 rule)
- Materialization: (engine_family, generalized_step) → engine_specific_step_type | None
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_exceptions import UnknownMaterializationError, UnknownEngineError

# =============================================================================
# SSOT: DriverRegistry is the single source of truth for step-type mappings.
# Materialization uses pure derivation: {gen: f"{PREFIX}_{gen}"} for supported gens.
# =============================================================================


def materialize_step(
    generalized_step: str,
    engine_family: str,
) -> Optional[str]:
    """
    Materialize a generalized step to an engine-specific step type.

    SSOT: Delegates to DriverRegistry which is the single source of truth.

    Args:
        generalized_step: Generalized step identifier (e.g., "scf", "nscf") - lowercase gen step name
        engine_family: Engine family identifier (e.g., "qe", "pyscf")

    Returns:
        Engine-specific step type identifier, or None if not supported

    Example:
        >>> materialize_step("scf", "qe")
        "qe_scf"
        >>> materialize_step("scf", "pyscf")
        "pyscf_scf"
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers

    # Normalize to lowercase gen step name (remove GEN_ prefix if present for backward compat)
    gen_type_lower = generalized_step.lower()
    if gen_type_lower.startswith("gen_"):
        gen_type_lower = gen_type_lower[4:]

    try:
        return DriverRegistry.materialize_step_type(engine_family, gen_type_lower)
    except (UnknownMaterializationError, UnknownEngineError):
        return None


def _is_zero_mapping(gen_step: str, engine_family: str) -> bool:
    """
    Check if (engine_family, gen_step) is an explicit zero-mapping.

    Zero-mappings are gen steps that have no corresponding spec step for an engine
    because the functionality is integrated into another step (e.g., VASP DOS
    is integrated into NSCF output).

    SSOT: Checks if gen_step is in engine's SUPPORTED_GEN_STEPS.

    Args:
        gen_step: Generalized step identifier (e.g., "bands", "dos")
        engine_family: Engine family identifier (e.g., "vasp")

    Returns:
        True if engine doesn't support this gen step (0-mapping), False otherwise
    """
    import quantumvitas.drivers

    # Normalize to lowercase gen step name
    gen_step_lower = gen_step.lower()
    if gen_step_lower.startswith("gen_"):
        gen_step_lower = gen_step_lower[4:]

    try:
        driver = DriverRegistry.get_driver(engine_family)
        # Check if gen_step is in engine's SUPPORTED_GEN_STEPS
        if hasattr(driver, 'SUPPORTED_GEN_STEPS'):
            return gen_step_lower not in driver.SUPPORTED_GEN_STEPS
        return False
    except UnknownEngineError:
        return False


def materialize_workflow(
    generalized_steps: list[str],
    engine_family: str,
) -> list[str]:
    """
    Materialize a list of generalized steps to engine-specific step types.
    
    Accepts gen step keys (like "scf", "bandspw") from workflow templates.
    
    Per VASP integration plan v2.0:
    - 0-mapping steps (engine doesn't support that gen step) are silently omitted (no error)
    - Unsupported family/step combinations raise ValueError
    
    Args:
        generalized_steps: List of gen step identifiers (e.g., "scf", "bandspw")
        engine_family: Engine family identifier (e.g., "qe", "pyscf", "vasp")
    
    Returns:
        List of engine-specific step type identifiers (spec types like "qe_scf")
        Steps with 0-mapping are silently omitted.
    
    Raises:
        ValueError: If any step is not supported by the engine family (not a 0-mapping)
    
    Example:
        >>> materialize_workflow(["scf", "nscf", "dos"], "qe")
        ["qe_scf", "qe_nscf", "qe_dos"]
        >>> materialize_workflow(["scf", "nscf", "bands"], "vasp")  # bands has 0-mapping for VASP
        ["vasp_scf", "vasp_nscf"]  # bands silently omitted
    """
    result = []
    unsupported_steps = []
    
    for gen_step in generalized_steps:
        # Use materialize_public_step_key which handles both PUBLIC keys and enum values
        specific_step = materialize_public_step_key(gen_step, engine_family)
        
        if specific_step is None:
            # Distinguish 0-mapping from unsupported
            if _is_zero_mapping(gen_step, engine_family):
                # Explicit 0-mapping: silently omit (per v2.0 spec)
                continue
            else:
                # Truly unsupported: collect for error
                unsupported_steps.append(gen_step)
        else:
            result.append(specific_step)
    
    if unsupported_steps:
        raise ValueError(
            f"Steps {unsupported_steps} are not supported by engine family '{engine_family}'"
        )
    
    return result


def materialize_public_step_key(
    public_step_key: str,
    engine_family: str,
) -> Optional[str]:
    """
    Materialize a PUBLIC step key (like "scf", "bandspw", "td") to MACHINE step type.

    Phase 3B/3C: Helper for materializing PUBLIC step keys from workflow templates.

    SSOT: Uses DriverRegistry via materialize_step() for all mappings.

    Strategy:
    1. First try StepTypeRegistry lookup for PUBLIC keys (handles "scf", "td", etc.)
    2. If that fails, try DriverRegistry via materialize_step()
    3. Verify the machine type's engine matches engine_family

    Args:
        public_step_key: PUBLIC step key (e.g., "scf", "bandspw", "td", "mp2")
        engine_family: Engine family identifier (e.g., "qe", "pyscf")

    Returns:
        MACHINE step type (e.g., "qe_scf", "pyscf_td"), or None if unsupported

    Example:
        >>> materialize_public_step_key("scf", "qe")
        "qe_scf"
        >>> materialize_public_step_key("td", "pyscf")
        "pyscf_td"
    """
    # Strategy: Prioritize StepTypeRegistry lookup for PUBLIC keys
    # This ensures PUBLIC keys like "bands" map correctly (qe_bands, not qe_bandspw)
    from quantumvitas.workflow.registry import get_registry
    registry = get_registry()
    spec = registry.get(public_step_key)  # Lookup by PUBLIC key (also accepts machine types)
    if spec:
        # Check if the spec's engine matches the requested engine_family
        spec_engine_family = spec.engine
        if spec_engine_family == engine_family:
            return spec.step_type_spec

    # Fallback: Try DriverRegistry via materialize_step()
    # Normalize to lowercase gen step name
    result = materialize_step(public_step_key.lower(), engine_family)
    if result is not None:
        return result

    return None


def get_supported_generalized_steps(engine_family: str) -> list[str]:
    """
    Get list of generalized steps supported by an engine family.

    SSOT: Queries driver's SUPPORTED_GEN_STEPS.

    Args:
        engine_family: Engine family identifier (e.g., "qe", "pyscf")

    Returns:
        List of gen step identifiers supported by the family (lowercase)

    Example:
        >>> get_supported_generalized_steps("qe")
        ["bandspw", "bands", "custom", "dos", "md", "nscf", "ph", ...]
    """
    import quantumvitas.drivers

    try:
        driver = DriverRegistry.get_driver(engine_family)
        if hasattr(driver, 'SUPPORTED_GEN_STEPS'):
            return sorted(list(driver.SUPPORTED_GEN_STEPS))
        return []
    except UnknownEngineError:
        return []


def get_engine_families_for_step(generalized_step: str) -> list[str]:
    """
    Get list of engine families that support a given generalized step.

    SSOT: Queries all drivers' SUPPORTED_GEN_STEPS.

    Args:
        generalized_step: Generalized step identifier (e.g., "scf", "nscf")

    Returns:
        List of engine family identifiers that support the step

    Example:
        >>> get_engine_families_for_step("scf")
        ["cp2k", "orca", "pyscf", "qe", "vasp"]
    """
    import quantumvitas.drivers

    # Normalize to lowercase gen step name
    gen_step_lower = generalized_step.lower()
    if gen_step_lower.startswith("gen_"):
        gen_step_lower = gen_step_lower[4:]

    families = []
    for engine_family in DriverRegistry.get_all_engines():
        try:
            driver = DriverRegistry.get_driver(engine_family)
            if hasattr(driver, 'SUPPORTED_GEN_STEPS'):
                if gen_step_lower in driver.SUPPORTED_GEN_STEPS:
                    families.append(engine_family)
        except UnknownEngineError:
            continue

    return sorted(families)


def dematerialize_step(
    engine_specific_step: str,
) -> Optional[Tuple[str, str]]:
    """
    Reverse materialization: map engine-specific step to (engine_family, generalized_step).

    SSOT: Uses gen_from() to extract gen step from spec step.

    Args:
        engine_specific_step: Engine-specific step type identifier (e.g., "qe_scf", "pyscf_scf")

    Returns:
        Tuple of (engine_family, generalized_step), or None if not found
        The generalized_step is returned as lowercase gen step name (e.g., "scf")

    Example:
        >>> dematerialize_step("qe_scf")
        ("qe", "scf")
        >>> dematerialize_step("pyscf_scf")
        ("pyscf", "scf")
        >>> dematerialize_step("unknown_step")
        None
    """
    import quantumvitas.drivers
    from quantumvitas.workflow.step_type_convert import gen_from, prefix_from

    if DriverRegistry.is_step_type_registered(engine_specific_step):
        try:
            engine = DriverRegistry.get_engine_for_step_type(engine_specific_step)
            # Extract gen step from spec step using pure derivation
            gen_step = gen_from(engine_specific_step)
            return (engine, gen_step)
        except (ValueError, UnknownEngineError):
            return None

    return None


def dematerialize_to_generalized_step(
    engine_specific_step: str,
) -> Optional[str]:
    """
    Reverse materialization: map engine-specific step to generalized step only.

    Args:
        engine_specific_step: Engine-specific step type identifier (e.g., "qe_scf", "pyscf_scf")

    Returns:
        Generalized step identifier (lowercase gen step name), or None

    Example:
        >>> dematerialize_to_generalized_step("qe_scf")
        "scf"
        >>> dematerialize_to_generalized_step("pyscf_scf")
        "scf"
    """
    result = dematerialize_step(engine_specific_step)
    if result:
        return result[1]  # Already lowercase gen step name
    return None

