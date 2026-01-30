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

from enum import Enum
from typing import Dict, Optional, Tuple

from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_exceptions import UnknownMaterializationError, UnknownEngineError


class GeneralizedStep(str, Enum):
    """Generalized step identifiers (engine-agnostic physical operations)."""

    # Self-consistent field calculations
    SCF = "SCF"
    HF = "HF"  # Hartree-Fock (explicit, primarily for molecular codes)
    NSCF = "NSCF"
    
    # Structural optimization
    RELAX = "RELAX"
    VC_RELAX = "VC_RELAX"
    
    # Electronic structure analysis
    BANDS = "BANDS"  # Band structure calculation (pw.x with calculation='bands')
    BANDS_POST = "BANDS_POST"  # Band structure post-processing (bands.x)
    DOS = "DOS"
    
    # Wannierization
    WANNIER_CONVERT = "WANNIER_CONVERT"  # pw2wannier90 conversion
    WANNIER = "WANNIER"  # wannier90 MLWF optimization
    
    # Phonon calculations
    PHONON = "PHONON"
    
    # Molecular dynamics
    MD = "MD"
    VC_MD = "VC_MD"
    
    # Post-Hartree-Fock (molecular)
    MP2 = "MP2"  # MP2 correlation energy calculation
    
    # Excited states (generalized, engine-specific backend)
    TD = "TD"  # Time-dependent calculation (TDDFT/TDHF, backend depends on engine)
    
    # Other
    CUSTOM = "CUSTOM"


# =============================================================================
# SSOT: DriverRegistry is the single source of truth for step-type mappings.
# Each driver defines its own get_materialization_map() method.
# The static MATERIALIZATION_MAP has been removed to eliminate drift.
# =============================================================================


def materialize_step(
    generalized_step: str,
    engine_family: str,
) -> Optional[str]:
    """
    Materialize a generalized step to an engine-specific step type.

    SSOT: Delegates to DriverRegistry which is the single source of truth.
    Each driver defines its own get_materialization_map() method.

    Args:
        generalized_step: Generalized step identifier (e.g., "SCF", "NSCF", "GEN_SCF")
        engine_family: Engine family identifier (e.g., "qe", "pyscf")

    Returns:
        Engine-specific step type identifier, or None if not supported

    Example:
        >>> materialize_step("SCF", "qe")
        "qe_scf"
        >>> materialize_step("GEN_SCF", "qe")
        "qe_scf"
        >>> materialize_step("SCF", "pyscf")
        "pyscf_scf"
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers

    # Normalize to GEN_ format
    gen_type_upper = generalized_step.upper()
    if not gen_type_upper.startswith("GEN_"):
        gen_type_upper = f"GEN_{gen_type_upper}"

    try:
        return DriverRegistry.materialize_step_type(engine_family, gen_type_upper)
    except (UnknownMaterializationError, UnknownEngineError):
        return None


def _is_zero_mapping(gen_step: str, engine_family: str) -> bool:
    """
    Check if (engine_family, gen_step) is an explicit zero-mapping.

    Zero-mappings are GEN types that have no corresponding step for an engine
    because the functionality is integrated into another step (e.g., VASP DOS
    is integrated into NSCF output).

    SSOT: Queries driver's _get_zero_mappings() method if available.

    Args:
        gen_step: Generalized step identifier (e.g., "BANDS_POST", "DOS")
        engine_family: Engine family identifier (e.g., "vasp")

    Returns:
        True if this is an explicit 0-mapping, False otherwise
    """
    import quantumvitas.drivers

    # Normalize to GEN_ format
    gen_type_upper = gen_step.upper()
    if not gen_type_upper.startswith("GEN_"):
        gen_type_upper = f"GEN_{gen_type_upper}"

    try:
        driver = DriverRegistry.get_driver(engine_family)
        # Check if driver has _get_zero_mappings method
        if hasattr(driver, "_get_zero_mappings"):
            zero_mappings = driver._get_zero_mappings()
            return gen_type_upper in zero_mappings
        return False
    except UnknownEngineError:
        return False


def materialize_workflow(
    generalized_steps: list[str],
    engine_family: str,
) -> list[str]:
    """
    Materialize a list of generalized steps to engine-specific step types.
    
    Phase 3B: Accepts PUBLIC step keys (like "scf", "bands_pw") from workflow templates.
    Also supports GeneralizedStep enum values (uppercase like "SCF") for backward compatibility.
    
    Per VASP integration plan v2.0:
    - 0-mapping steps (explicit None in MATERIALIZATION_MAP) are silently omitted (no error)
    - Unsupported family/step combinations raise ValueError
    
    Args:
        generalized_steps: List of step identifiers (PUBLIC keys like "scf" or enum values like "SCF")
        engine_family: Engine family identifier (e.g., "qe", "pyscf", "vasp")
    
    Returns:
        List of engine-specific step type identifiers (MACHINE types like "qe_scf")
        Steps with 0-mapping are silently omitted.
    
    Raises:
        ValueError: If any step is not supported by the engine family (not a 0-mapping)
    
    Example:
        >>> materialize_workflow(["scf", "nscf", "dos"], "qe")  # PUBLIC keys (preferred)
        ["qe_scf", "qe_nscf", "qe_dos"]
        >>> materialize_workflow(["scf", "nscf", "bands_post"], "vasp")  # bands_post has 0-mapping
        ["vasp_scf", "vasp_nscf"]  # bands_post silently omitted
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
    Materialize a PUBLIC step key (like "scf", "bands_pw", "td") to MACHINE step type.

    Phase 3B/3C: Helper for materializing PUBLIC step keys from workflow templates.

    SSOT: Uses DriverRegistry via materialize_step() for all mappings.

    Strategy:
    1. First try StepTypeRegistry lookup for PUBLIC keys (handles "scf", "td", etc.)
    2. If that fails, try DriverRegistry via materialize_step()
    3. Verify the machine type's engine matches engine_family

    Args:
        public_step_key: PUBLIC step key (e.g., "scf", "bands_pw", "td", "mp2")
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
    # This ensures PUBLIC keys like "bands" map correctly (qe_bands, not qe_bands_pw)
    from quantumvitas.workflow.registry import get_registry
    registry = get_registry()
    spec = registry.get(public_step_key)  # Lookup by PUBLIC key (also accepts machine types)
    if spec:
        # Check if the spec's engine matches the requested engine_family
        spec_engine_family = spec.engine
        if spec_engine_family == engine_family:
            return spec.step_type_spec

    # Fallback: Try DriverRegistry via materialize_step()
    # This handles GeneralizedStep enum values like "SCF", "TD"
    result = materialize_step(public_step_key.upper(), engine_family)
    if result is not None:
        return result

    return None


def get_supported_generalized_steps(engine_family: str) -> list[str]:
    """
    Get list of generalized steps supported by an engine family.

    SSOT: Queries driver's get_materialization_map() method.

    Args:
        engine_family: Engine family identifier (e.g., "qe", "pyscf")

    Returns:
        List of generalized step identifiers supported by the family
        (with GEN_ prefix stripped for backward compatibility)

    Example:
        >>> get_supported_generalized_steps("qe")
        ["BANDS", "BANDS_POST", "CUSTOM", "DOS", "MD", "NSCF", "PHONON", ...]
    """
    import quantumvitas.drivers

    try:
        driver = DriverRegistry.get_driver(engine_family)
        mat_map = driver.get_materialization_map()
        # Strip GEN_ prefix for backward compatibility
        supported = [
            gen_type[4:] if gen_type.startswith("GEN_") else gen_type
            for gen_type in mat_map.keys()
        ]
        return sorted(supported)
    except UnknownEngineError:
        return []


def get_engine_families_for_step(generalized_step: str) -> list[str]:
    """
    Get list of engine families that support a given generalized step.

    SSOT: Queries all drivers' get_materialization_map() methods.

    Args:
        generalized_step: Generalized step identifier (e.g., "SCF", "NSCF")

    Returns:
        List of engine family identifiers that support the step

    Example:
        >>> get_engine_families_for_step("SCF")
        ["cp2k", "orca", "pyscf", "qe", "vasp"]
    """
    import quantumvitas.drivers

    # Normalize to GEN_ format
    gen_step_upper = generalized_step.upper()
    if not gen_step_upper.startswith("GEN_"):
        gen_step_upper = f"GEN_{gen_step_upper}"

    families = []
    for engine_family in DriverRegistry.get_all_engines():
        try:
            driver = DriverRegistry.get_driver(engine_family)
            mat_map = driver.get_materialization_map()
            if gen_step_upper in mat_map:
                families.append(engine_family)
        except UnknownEngineError:
            continue

    return sorted(families)


def dematerialize_step(
    engine_specific_step: str,
) -> Optional[Tuple[str, str]]:
    """
    Reverse materialization: map engine-specific step to (engine_family, generalized_step).

    SSOT: Queries DriverRegistry to find the mapping.

    Args:
        engine_specific_step: Engine-specific step type identifier (e.g., "qe_scf", "pyscf_scf")

    Returns:
        Tuple of (engine_family, generalized_step), or None if not found
        The generalized_step is returned WITH GEN_ prefix (e.g., "GEN_SCF")

    Example:
        >>> dematerialize_step("qe_scf")
        ("qe", "GEN_SCF")
        >>> dematerialize_step("pyscf_scf")
        ("pyscf", "GEN_SCF")
        >>> dematerialize_step("unknown_step")
        None
    """
    import quantumvitas.drivers

    if DriverRegistry.is_step_type_registered(engine_specific_step):
        engine = DriverRegistry.get_engine_for_step_type(engine_specific_step)
        # Check this engine's materialization map
        driver = DriverRegistry.get_driver(engine)
        mat_map = driver.get_materialization_map()
        # Reverse lookup in this engine's materialization map
        for gen_type, spec_type in mat_map.items():
            if spec_type == engine_specific_step:
                return (engine, gen_type)

    return None


def dematerialize_to_generalized_step(
    engine_specific_step: str,
) -> Optional[str]:
    """
    Reverse materialization: map engine-specific step to generalized step only.

    Args:
        engine_specific_step: Engine-specific step type identifier (e.g., "qe_scf", "pyscf_scf")

    Returns:
        Generalized step identifier (without GEN_ prefix for backward compat), or None

    Example:
        >>> dematerialize_to_generalized_step("qe_scf")
        "SCF"
        >>> dematerialize_to_generalized_step("pyscf_scf")
        "SCF"
    """
    result = dematerialize_step(engine_specific_step)
    if result:
        gen_step = result[1]
        # Strip GEN_ prefix for backward compatibility
        if gen_step.startswith("GEN_"):
            return gen_step[4:]
        return gen_step
    return None

