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


class GeneralizedStep(str, Enum):
    """Generalized step identifiers (engine-agnostic physical operations)."""
    
    # Self-consistent field calculations
    SCF = "SCF"
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
    
    # Other
    CUSTOM = "CUSTOM"


# Materialization mapping: (engine_family, generalized_step) → engine_specific_step_type | None
# Returns None if the generalized step is not supported by the engine family
MATERIALIZATION_MAP: Dict[Tuple[str, str], Optional[str]] = {
    # QE family mappings
    ("qe", "SCF"): "qe_scf",
    ("qe", "NSCF"): "qe_nscf",
    ("qe", "RELAX"): "qe_relax",
    ("qe", "VC_RELAX"): "qe_vc_relax",
    ("qe", "BANDS"): "qe_bands_pw",  # pw.x calculation='bands'
    ("qe", "BANDS_POST"): "qe_bands",  # bands.x post-processing
    ("qe", "DOS"): "qe_dos",
    ("qe", "WANNIER_CONVERT"): "qe_pw2wannier90",
    ("qe", "WANNIER"): "w90_run",  # wannier90 is part of qe family toolchain
    ("qe", "PHONON"): "qe_ph",
    ("qe", "MD"): "qe_md",
    ("qe", "VC_MD"): "qe_vc_md",
    ("qe", "CUSTOM"): "qe_custom",
    
    # PySCF family mappings
    ("pyscf", "SCF"): "pyscf_scf",
    # Other PySCF generalized steps not yet supported in v0
    
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
    
    Args:
        generalized_step: Generalized step identifier (e.g., "SCF", "NSCF")
        engine_family: Engine family identifier (e.g., "qe", "pyscf")
    
    Returns:
        Engine-specific step type identifier, or None if not supported
    
    Example:
        >>> materialize_step("SCF", "qe")
        "qe_scf"
        >>> materialize_step("SCF", "pyscf")
        "pyscf_scf"
        >>> materialize_step("SCF", "vasp")
        None
    """
    key = (engine_family.lower(), generalized_step.upper())
    return MATERIALIZATION_MAP.get(key)


def materialize_workflow(
    generalized_steps: list[str],
    engine_family: str,
) -> list[str]:
    """
    Materialize a list of generalized steps to engine-specific step types.
    
    Args:
        generalized_steps: List of generalized step identifiers
        engine_family: Engine family identifier (e.g., "qe", "pyscf")
    
    Returns:
        List of engine-specific step type identifiers
    
    Raises:
        ValueError: If a generalized step is unsupported by the engine family
    
    Example:
        >>> materialize_workflow(["SCF", "NSCF", "DOS"], "qe")
        ["qe_scf", "qe_nscf", "qe_dos"]
        >>> materialize_workflow(["SCF"], "vasp")
        ValueError: Generalized step 'SCF' is not supported by engine family 'vasp'
    """
    result = []
    for gen_step in generalized_steps:
        specific_step = materialize_step(gen_step, engine_family)
        if specific_step is None:
            raise ValueError(
                f"Generalized step '{gen_step}' is not supported by engine family '{engine_family}'"
            )
        result.append(specific_step)
    return result


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
    
    # Try to infer from prefix
    if engine_specific_step.startswith("qe_"):
        engine_family = "qe"
        step_name = engine_specific_step[3:]  # Remove "qe_" prefix
        # Map common step names to generalized steps
        step_to_generalized = {
            "scf": "SCF",
            "nscf": "NSCF",
            "relax": "RELAX",
            "vc_relax": "VC_RELAX",
            "bands_pw": "BANDS",  # pw.x calculation='bands'
            "dos": "DOS",
            "bands": "BANDS_POST",  # bands.x post-processing
            "ph": "PHONON",
            "md": "MD",
            "vc_md": "VC_MD",
            "pw2wannier90": "WANNIER_CONVERT",
        }
        gen_step = step_to_generalized.get(step_name)
        if gen_step:
            return (engine_family, gen_step)
    elif engine_specific_step.startswith("w90_"):
        engine_family = "qe"  # w90 is part of qe family
        if engine_specific_step == "w90_run":
            return (engine_family, "WANNIER")
    elif engine_specific_step.startswith("pyscf_"):
        engine_family = "pyscf"
        step_name = engine_specific_step[6:]  # Remove "pyscf_" prefix
        if step_name == "scf":
            return (engine_family, "SCF")
    
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

