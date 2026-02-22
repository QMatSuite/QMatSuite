"""
ParamSpace Registry: Single source of truth for all preset dimensions.

Per Constitution 10.7:
- All preset dimensions must declare a ParamSpace
- All compilation and detection must go through this registry
- No dimension-specific logic outside ParamSpace declarations

This module provides:
- SPACES registry: dict mapping dimension name -> ParamSpace
- detect_dimension(): Registry-driven detection API
- compile_dimension_patch(): Registry-driven compilation API
- Profile <-> Enum mappings (centralized)
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union, Tuple
from pathlib import Path

from qmatsuite.presets.paramspace import (
    ParamSpace,
    get_occupations_scheme_paramspace,
    get_magnetism_paramspace,
    get_precision_paramspace,
    get_convergence_paramspace,
    match_profile,
    compile_profile_patch,
    match_precision_profile,
)
from qmatsuite.presets.qc_precision import get_qc_precision_paramspace
from qmatsuite.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    PrecisionOption,
    ConvergenceOption,
    CUSTOM,
)


# ============================================================================
# ParamSpace Registry (Single Source of Truth)
# ============================================================================

# Import all ParamSpace singletons
OCCUPATIONS_SCHEME_SPACE = get_occupations_scheme_paramspace()
MAGNETISM_SPACE = get_magnetism_paramspace()
PRECISION_SPACE = get_precision_paramspace()
QC_PRECISION_SPACE = get_qc_precision_paramspace()
CONVERGENCE_SPACE = get_convergence_paramspace()

# Registry: dimension name -> ParamSpace
SPACES: Dict[str, ParamSpace] = {
    "occupations_scheme": OCCUPATIONS_SCHEME_SPACE,
    "magnetism": MAGNETISM_SPACE,
    "precision": PRECISION_SPACE,
    "qc_precision": QC_PRECISION_SPACE,
    "convergence": CONVERGENCE_SPACE,
}


# ============================================================================
# Profile <-> Enum Mappings (Centralized)
# ============================================================================

# OccupationsScheme: profile_name -> enum
OCCUPATIONS_SCHEME_PROFILE_TO_ENUM = {
    "FIXED": OccupationsSchemeOption.FIXED,
    "TETRAHEDRA": OccupationsSchemeOption.TETRAHEDRA,
    "SMEARING_GAUSSIAN": OccupationsSchemeOption.SMEARING_GAUSSIAN,
}

OCCUPATIONS_SCHEME_ENUM_TO_PROFILE = {
    OccupationsSchemeOption.FIXED: "FIXED",
    OccupationsSchemeOption.TETRAHEDRA: "TETRAHEDRA",
    OccupationsSchemeOption.SMEARING_GAUSSIAN: "SMEARING_GAUSSIAN",
}

# Magnetism: profile_name -> enum
# Multiple profiles can map to the same enum (for detect tolerance)
MAGNETISM_PROFILE_TO_ENUM = {
    "NM": MagnetismOption.NONMAGNETIC,
    "COL": MagnetismOption.COLLINEAR_LSDA,
    "NC_CANONICAL": MagnetismOption.NONCOLLINEAR,
    "NC_WITH_NSPIN4": MagnetismOption.NONCOLLINEAR,
    "SOC_CANONICAL": MagnetismOption.NONCOLLINEAR_SOC,
    "SOC_WITH_NSPIN4": MagnetismOption.NONCOLLINEAR_SOC,
}

# Enum -> profile (for apply - use canonical profiles)
MAGNETISM_ENUM_TO_PROFILE = {
    MagnetismOption.NONMAGNETIC: "NM",
    MagnetismOption.COLLINEAR_LSDA: "COL",
    MagnetismOption.NONCOLLINEAR: "NC_CANONICAL",  # Use canonical for apply
    MagnetismOption.NONCOLLINEAR_SOC: "SOC_CANONICAL",  # Use canonical for apply
}

# Precision: profile_name -> enum
PRECISION_PROFILE_TO_ENUM = {
    "LOW": PrecisionOption.LOW,
    "MED": PrecisionOption.MED,
    "HIGH": PrecisionOption.HIGH,
}

PRECISION_ENUM_TO_PROFILE = {
    PrecisionOption.LOW: "LOW",
    PrecisionOption.MED: "MED",
    PrecisionOption.HIGH: "HIGH",
}

# QC Precision: profile_name -> enum (reuses PrecisionOption)
QC_PRECISION_PROFILE_TO_ENUM = {
    "LOW": PrecisionOption.LOW,
    "MED": PrecisionOption.MED,
    "HIGH": PrecisionOption.HIGH,
}

QC_PRECISION_ENUM_TO_PROFILE = {
    PrecisionOption.LOW: "LOW",
    PrecisionOption.MED: "MED",
    PrecisionOption.HIGH: "HIGH",
}

# Convergence: profile_name -> enum
CONVERGENCE_PROFILE_TO_ENUM = {
    "FAST": ConvergenceOption.FAST,
    "NORMAL": ConvergenceOption.NORMAL,
    "ROBUST": ConvergenceOption.ROBUST,
    "VERY_ROBUST": ConvergenceOption.VERY_ROBUST,
}

CONVERGENCE_ENUM_TO_PROFILE = {
    ConvergenceOption.FAST: "FAST",
    ConvergenceOption.NORMAL: "NORMAL",
    ConvergenceOption.ROBUST: "ROBUST",
    ConvergenceOption.VERY_ROBUST: "VERY_ROBUST",
}

# Combined mappings per dimension
PROFILE_TO_ENUM: Dict[str, Dict[str, Any]] = {
    "occupations_scheme": OCCUPATIONS_SCHEME_PROFILE_TO_ENUM,
    "magnetism": MAGNETISM_PROFILE_TO_ENUM,
    "precision": PRECISION_PROFILE_TO_ENUM,
    "qc_precision": QC_PRECISION_PROFILE_TO_ENUM,
    "convergence": CONVERGENCE_PROFILE_TO_ENUM,
}

ENUM_TO_PROFILE: Dict[str, Dict[Any, str]] = {
    "occupations_scheme": OCCUPATIONS_SCHEME_ENUM_TO_PROFILE,
    "magnetism": MAGNETISM_ENUM_TO_PROFILE,
    "precision": PRECISION_ENUM_TO_PROFILE,
    "qc_precision": QC_PRECISION_ENUM_TO_PROFILE,
    "convergence": CONVERGENCE_ENUM_TO_PROFILE,
}


# ============================================================================
# Registry-Driven Detection API
# ============================================================================

def detect_dimension(
    dimension: str,
    step_yaml: Dict[str, Dict[str, Any]],
    *,
    # Precision-specific context (only used for precision)
    lattice_matrix: Optional[list[list[float]]] = None,
    base_ecutwfc: Optional[float] = None,
    base_ecutrho: Optional[float] = None,
) -> Union[MagnetismOption, OccupationsSchemeOption, PrecisionOption, ConvergenceOption, type[CUSTOM]]:
    """
    Detect a preset dimension from step YAML using ParamSpace registry.
    
    This is the ONLY allowed way to call ParamSpace detection engine.
    All dimension-specific detection must go through this function.
    
    Args:
        dimension: Dimension name (must be in SPACES registry
        step_yaml: Step YAML dict (section -> params structure)
        lattice_matrix: Optional lattice matrix (required for precision)
        base_ecutwfc: Optional base ecutwfc (required for precision)
        base_ecutrho: Optional base ecutrho (required for precision)
        
    Returns:
        Detected enum option or CUSTOM if no match
        
    Raises:
        ValueError: If dimension not in registry
    """
    if dimension not in SPACES:
        raise ValueError(
            f"Unknown dimension: {dimension}. "
            f"Must be one of: {list(SPACES.keys())}"
        )
    
    space = SPACES[dimension]
    profile_to_enum = PROFILE_TO_ENUM[dimension]
    
    # Special handling for precision (uses computed canonical values)
    if dimension == "precision":
        if lattice_matrix is None or base_ecutwfc is None or base_ecutrho is None:
            return CUSTOM
        
        from qmatsuite.presets.precision import (
            PRECISION_CONSTANTS,
            compute_kmesh,
            round_cutoff_integer,
        )
        # ParamSpace operates on IR YAML (IR is SSOT in v0, IR keys == QE keys due to 1:1 mapping)
        # step_yaml is already IR YAML structure (in v0, step.yaml parameters are IR-compatible)
        
        # Try matching against each precision level
        for level, constants in PRECISION_CONSTANTS.items():
            canonical_ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
            canonical_ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
            canonical_conv_thr = constants.conv_thr
            canonical_kmesh = compute_kmesh(lattice_matrix, constants.delta_k)
            
            canonical_values = {
                "ecutwfc": canonical_ecutwfc,
                "ecutrho": canonical_ecutrho,
                "conv_thr": canonical_conv_thr,
                "kmesh": canonical_kmesh,
                "profile_name": level.value.upper(),  # "LOW", "MED", "HIGH"
            }
            
            matched_profile = match_precision_profile(step_yaml, canonical_values)
            
            if matched_profile is not None:
                if matched_profile in profile_to_enum:
                    return profile_to_enum[matched_profile]
        
        return CUSTOM
    
    # Standard ParamSpace matching for other dimensions
    # ParamSpace operates on IR YAML (IR is SSOT in v0, IR keys == QE keys due to 1:1 mapping)
    # step_yaml is already IR YAML structure (in v0, step.yaml parameters are IR-compatible)
    
    matched_profile = match_profile(space, step_yaml)
    
    if matched_profile is None:
        return CUSTOM
    
    if matched_profile not in profile_to_enum:
        return CUSTOM
    
    return profile_to_enum[matched_profile]


# ============================================================================
# Registry-Driven Compilation API
# ============================================================================

def compile_dimension_patch(
    dimension: str,
    option_enum: Union[MagnetismOption, OccupationsSchemeOption, PrecisionOption, ConvergenceOption],
    step_yaml: Dict[str, Dict[str, Any]],
    *,
    explicit_defaults: bool = True,
    # Precision-specific: computed values (only used for precision)
    ecutwfc: Optional[float] = None,
    ecutrho: Optional[float] = None,
    conv_thr: Optional[float] = None,
    nk1: Optional[int] = None,
    nk2: Optional[int] = None,
    nk3: Optional[int] = None,
    sk1: int = 0,
    sk2: int = 0,
    sk3: int = 0,
) -> Tuple[Dict[str, Dict[str, Any]], set[Tuple[str, str]]]:
    """
    Compile a preset dimension to YAML patch using ParamSpace registry.
    
    This is the ONLY allowed way to call ParamSpace compilation engine.
    All dimension-specific compilation must go through this function.
    
    Args:
        dimension: Dimension name (must be in SPACES registry)
        option_enum: Enum option value (MagnetismOption, OccupationsSchemeOption, etc.)
        step_yaml: Current step YAML dict (for checking existing values)
        explicit_defaults: If True, always write VALUE cells; if False, skip if value == default
        ecutwfc: Optional ecutwfc (required for precision)
        ecutrho: Optional ecutrho (required for precision)
        conv_thr: Optional conv_thr (required for precision)
        nk1, nk2, nk3: Optional k-mesh (required for precision)
        sk1, sk2, sk3: Optional k-mesh shifts (for precision)
        
    Returns:
        Tuple of (patch_dict, deletions_set)
        - patch_dict: Nested dict to merge into YAML
        - deletions_set: Set of (section, key) tuples to delete
        
    Raises:
        ValueError: If dimension not in registry or option not supported
    """
    if dimension not in SPACES:
        raise ValueError(
            f"Unknown dimension: {dimension}. "
            f"Must be one of: {list(SPACES.keys())}"
        )
    
    space = SPACES[dimension]
    enum_to_profile = ENUM_TO_PROFILE[dimension]
    
    if option_enum not in enum_to_profile:
        raise ValueError(
            f"Unknown option for dimension {dimension}: {option_enum}"
        )
    
    profile_name = enum_to_profile[option_enum]
    
    # Special handling for precision (values are computed, not in profiles)
    if dimension == "precision":
        # Validate required parameters
        if ecutwfc is None or ecutrho is None or conv_thr is None:
            from qmatsuite.presets.compiler import PresetCompilationError
            raise PresetCompilationError(
                f"Precision preset compilation requires ecutwfc, ecutrho, and conv_thr. "
                f"Use PrecisionAdvisor to compute these from structure and pseudos."
            )
        
        if nk1 is None or nk2 is None or nk3 is None:
            from qmatsuite.presets.compiler import PresetCompilationError
            raise PresetCompilationError(
                f"Precision preset compilation requires k-mesh (nk1, nk2, nk3). "
                f"Use PrecisionAdvisor to compute these from structure."
            )
        
        # Manually construct IR patch for precision (values come from advisor)
        # IR is SSOT; QE writer will convert IR to QE input later
        ir_patch: Dict[str, Dict[str, Any]] = {
            "SYSTEM": {
                "ecutwfc": int(ecutwfc),  # Integer-rounded
                "ecutrho": int(ecutrho),  # Integer-rounded
            },
            "ELECTRONS": {
                "conv_thr": conv_thr,
            },
            "cards": {  # K_POINTS is in cards section
                "K_POINTS": {
                    "option": "automatic",
                    "data": [[nk1, nk2, nk3, sk1, sk2, sk3]],
                },
            },
        }
        
        deletions: set[Tuple[str, str]] = set()
        
        return (ir_patch, deletions)
    
    # Standard ParamSpace compilation for other dimensions
    # ParamSpace operates on IR YAML (IR is SSOT in v0, IR keys == QE keys due to 1:1 mapping)
    # step_yaml is already IR YAML structure (in v0, step.yaml parameters are IR-compatible)
    
    ir_patch, deletions = compile_profile_patch(
        space, profile_name, step_yaml, explicit_defaults=explicit_defaults
    )
    
    # Return IR patch directly (IR is SSOT; QE writer will convert IR to QE input later)
    return (ir_patch, deletions)

