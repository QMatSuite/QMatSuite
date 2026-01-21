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


# Materialization mapping: (engine_family, generalized_step) → engine_specific_step_type | None
# Returns None if the generalized step is not supported by the engine family
MATERIALIZATION_MAP: Dict[Tuple[str, str], Optional[str]] = {
    # QE family mappings
    ("qe", "SCF"): "qe_scf",
    ("qe", "NSCF"): "qe_nscf",
    ("qe", "RELAX"): "qe_relax",
    ("qe", "VC_RELAX"): "qe_relax",  # VC_RELAX now maps to unified qe_relax
    ("qe", "BANDS"): "qe_bands_pw",  # pw.x calculation='bands'
    ("qe", "BANDS_POST"): "qe_bands",  # bands.x post-processing
    ("qe", "DOS"): "qe_dos",
    ("qe", "WANNIER_CONVERT"): "qe_pw2wannier90",
    ("qe", "WANNIER"): "w90_run",  # wannier90 is part of qe family toolchain
    ("qe", "PHONON"): "qe_ph",
    ("qe", "MD"): "qe_md",
    ("qe", "VC_MD"): "qe_vc_md",
    ("qe", "TD"): None,  # Phase 3C: QE TD not yet implemented in registry (TODO: add qe_tddft when needed)
    ("qe", "CUSTOM"): "qe_custom",
    
    # PySCF family mappings
    ("pyscf", "SCF"): "pyscf_scf",
    ("pyscf", "MP2"): "pyscf_mp2",
    ("pyscf", "TD"): "pyscf_td",  # Phase 3C: Generalized "td" key

    # ORCA family mappings
    ("orca", "SCF"): "orca_scf",
    ("orca", "HF"): "orca_hf",
    ("orca", "TD"): "orca_td",  # ORCA TDDFT/CIS

    # VASP family mappings
    ("vasp", "SCF"): "vasp_scf",
    ("vasp", "NSCF"): "vasp_nscf",
    ("vasp", "RELAX"): "vasp_relax",
    ("vasp", "BANDS"): "vasp_bands",
    ("vasp", "BANDS_POST"): None,  # 0-mapping: VASP doesn't need post-processing
    ("vasp", "BANDSPP"): None,     # 0-mapping: VASP doesn't need post-processing (PUBLIC key alias)
    ("vasp", "DOS"): None,          # 0-mapping: VASP DOS integrated in nscf output
    ("vasp", "DOSPP"): None,       # 0-mapping: VASP DOS integrated in nscf output (PUBLIC key alias)

    # LAMMPS family mappings (Classical MD)
    ("lammps", "RELAX"): "lammps_relax",
    ("lammps", "MD"): "lammps_md",
    
    # CP2K family mappings
    ("cp2k", "SCF"): "cp2k_scf",
    ("cp2k", "RELAX"): "cp2k_relax",
    ("cp2k", "VC_RELAX"): "cp2k_relax",
    ("cp2k", "MD"): "cp2k_md",
    ("cp2k", "VC_MD"): "cp2k_md",

    # Wannier90 standalone (if needed in future)
    # ("w90", "WANNIER"): "w90_run",

    # Unsupported combinations return None (materialization will fail)
}


def materialize_step(
    generalized_step: str,
    engine_family: str,
) -> Optional[str]:
    """
    Materialize a generalized step to an engine-specific step type.
    
    This now delegates to DriverRegistry for registered engines.
    Falls back to legacy MATERIALIZATION_MAP for backward compatibility.
    
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
        >>> materialize_step("SCF", "vasp")
        None
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers
    
    # Try registry first (supports "GEN_SCF" format)
    gen_type_upper = generalized_step.upper()
    if gen_type_upper.startswith("GEN_"):
        try:
            return DriverRegistry.materialize_step_type(engine_family, gen_type_upper)
        except (UnknownMaterializationError, UnknownEngineError):
            pass
    
    # Try with "GEN_" prefix if not already present
    if not gen_type_upper.startswith("GEN_"):
        try:
            gen_type_with_prefix = f"GEN_{gen_type_upper}"
            return DriverRegistry.materialize_step_type(engine_family, gen_type_with_prefix)
        except (UnknownMaterializationError, UnknownEngineError):
            pass
    
    # Fallback to legacy MATERIALIZATION_MAP (for backward compatibility)
    key = (engine_family.lower(), gen_type_upper)
    return MATERIALIZATION_MAP.get(key)


def _is_zero_mapping(gen_step: str, engine_family: str) -> bool:
    """
    Check if (engine_family, gen_step) is explicitly mapped to None.
    
    Returns True only if the key exists in MATERIALIZATION_MAP with value None.
    Returns False if the key is not in the map at all.
    
    Args:
        gen_step: Generalized step identifier (e.g., "BANDS_POST", "DOS")
        engine_family: Engine family identifier (e.g., "vasp")
    
    Returns:
        True if this is an explicit 0-mapping, False otherwise
    """
    key = (engine_family.lower(), gen_step.upper())
    return key in MATERIALIZATION_MAP and MATERIALIZATION_MAP[key] is None


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
    
    Strategy:
    1. First try registry lookup for PUBLIC keys (handles "scf", "td", etc.)
    2. If that fails, try MATERIALIZATION_MAP (for GeneralizedStep enum values like "SCF", "TD")
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
        >>> materialize_public_step_key("scf", "vasp")
        None
    """
    # Strategy: Prioritize registry lookup for PUBLIC keys
    # This ensures PUBLIC keys like "bands" map correctly (qe_bands, not qe_bands_pw)
    from quantumvitas.workflow.registry import get_registry
    registry = get_registry()
    spec = registry.get(public_step_key)  # Lookup by PUBLIC key (also accepts machine types)
    if spec:
        # Check if the spec's engine matches the requested engine_family
        spec_engine_family = spec.engine
        if spec_engine_family == engine_family:
            return spec.machine_type

    # No special cases - each driver is responsible for its own step types
    # W90 is a separate driver; its step types are registered with engine="w90"
    
    # Fallback: Try MATERIALIZATION_MAP (for GeneralizedStep enum values like "SCF", "TD")
    # This handles backward compatibility with enum values
    # Phase 3C: Also handles "td" -> "TD" enum mapping
    result = materialize_step(public_step_key.upper(), engine_family)
    if result is not None:
        return result
    
    return None


def get_supported_generalized_steps(engine_family: str) -> list[str]:
    """
    Get list of generalized steps supported by an engine family.
    
    Args:
        engine_family: Engine family identifier (e.g., "qe", "pyscf")
    
    Returns:
        List of generalized step identifiers supported by the family
    
    Example:
        >>> get_supported_generalized_steps("qe")
        ["SCF", "NSCF", "RELAX", "VC_RELAX", "BANDS", "DOS", ...]
    """
    engine_family_lower = engine_family.lower()
    supported = [
        gen_step
        for (family, gen_step), specific_step in MATERIALIZATION_MAP.items()
        if family == engine_family_lower and specific_step is not None
    ]
    return sorted(supported)


def get_engine_families_for_step(generalized_step: str) -> list[str]:
    """
    Get list of engine families that support a given generalized step.
    
    Args:
        generalized_step: Generalized step identifier (e.g., "SCF", "NSCF")
    
    Returns:
        List of engine family identifiers that support the step
    
    Example:
        >>> get_engine_families_for_step("SCF")
        ["qe", "pyscf"]
    """
    gen_step_upper = generalized_step.upper()
    families = [
        family
        for (family, gen_step), specific_step in MATERIALIZATION_MAP.items()
        if gen_step == gen_step_upper and specific_step is not None
    ]
    # Remove duplicates while preserving order
    return sorted(list(set(families)))


def dematerialize_step(
    engine_specific_step: str,
) -> Optional[Tuple[str, str]]:
    """
    Reverse materialization: map engine-specific step to (engine_family, generalized_step).
    
    Args:
        engine_specific_step: Engine-specific step type identifier (e.g., "qe_scf", "pyscf_scf")
    
    Returns:
        Tuple of (engine_family, generalized_step), or None if not found
    
    Example:
        >>> dematerialize_step("qe_scf")
        ("qe", "SCF")
        >>> dematerialize_step("pyscf_scf")
        ("pyscf", "SCF")
        >>> dematerialize_step("unknown_step")
        None
    """
    # Build reverse mapping from MATERIALIZATION_MAP
    for (family, gen_step), specific_step in MATERIALIZATION_MAP.items():
        if specific_step == engine_specific_step:
            return (family, gen_step)

    # Use registry to get engine family for this step type
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers  # Ensure loaded

    if DriverRegistry.is_step_type_registered(engine_specific_step):
        engine = DriverRegistry.get_engine_for_step_type(engine_specific_step)
        # Check all materialization maps to find the generalized step
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
        Generalized step identifier, or None if not found
    
    Example:
        >>> dematerialize_to_generalized_step("qe_scf")
        "SCF"
        >>> dematerialize_to_generalized_step("pyscf_scf")
        "SCF"
    """
    result = dematerialize_step(engine_specific_step)
    if result:
        return result[1]  # Return generalized step only
    return None

