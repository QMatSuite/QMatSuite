"""
Compiler: Forward generation of step parameters from preset options.

This module implements the Compiler per Constitution Chapter 10.3:
- Compiler is a pure function mapping options → step parameters (10.3.1)
- Must use canonical encoding - explicit all key parameters (10.3.4)
- Must be overwrite-only, not merge/append (10.3.3)
- Must not depend on structure, pseudo, workflow, step topology (10.3.2)

Compiler is a "canonical writer" - it explicitly writes all key parameters
without relying on QE defaults. This ensures:
- Reproducibility across QE versions
- Detector B can always recover the original intent
- No "hidden" parameter dependencies

Key functions:
- compile_magnetism(option) -> Dict: Generate magnetism-related SYSTEM params (merged spin + SOC)
- compile_occupations_scheme(option) -> Dict: Generate occupations_scheme-related SYSTEM params
- compile_presets(options) -> Dict: Generate all preset params combined
"""

from typing import Any, Dict, Optional

from quantumvitas.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    PrecisionOption,
    DIMENSION_MAGNETISM,
    DIMENSION_OCCUPATIONS_SCHEME,
    DIMENSION_PRECISION,
)


class PresetCompilationError(Exception):
    """Raised when preset compilation fails due to invalid combinations."""
    pass


def compile_magnetism(
    option: MagnetismOption,
    *,
    explicit_defaults: bool = True,
) -> Dict[str, Any]:
    """
    Compile magnetism preset option to QE SYSTEM parameters.
    
    Thin wrapper around registry-driven ParamSpace compilation.
    
    Args:
        option: MagnetismOption value (NONMAGNETIC, COLLINEAR_LSDA, NONCOLLINEAR, NONCOLLINEAR_SOC)
        explicit_defaults: If True, always write VALUE cells; if False, skip if value == default
        
    Returns:
        Dict with nested structure: {"SYSTEM": {...parameters...}}
    """
    from quantumvitas.presets.spaces_registry import compile_dimension_patch
    
    patch, deletions = compile_dimension_patch(
        "magnetism", option, {}, explicit_defaults=explicit_defaults
    )
    
    # Return full patch structure (nested {SECTION: {key: value}})
    # Deletions handled by integration layer
    return patch


def compile_occupations_scheme(
    option: OccupationsSchemeOption,
    *,
    explicit_defaults: bool = True,
) -> Dict[str, Any]:
    """
    Compile occupations_scheme preset option to QE SYSTEM parameters.
    
    Thin wrapper around registry-driven ParamSpace compilation.
    
    Args:
        option: OccupationsSchemeOption value (FIXED, SMEARING_GAUSSIAN, TETRAHEDRA)
        explicit_defaults: If True, always write VALUE cells; if False, skip if value == default
        
    Returns:
        Dict with nested structure: {"SYSTEM": {...parameters...}}
    """
    from quantumvitas.presets.spaces_registry import compile_dimension_patch
    
    patch, deletions = compile_dimension_patch(
        "occupations_scheme", option, {}, explicit_defaults=explicit_defaults
    )
    
    # Return full patch structure (nested {SECTION: {key: value}})
    # Deletions handled by integration layer
    return patch


def compile_precision(
    option: PrecisionOption,
    *,
    ecutwfc: Optional[float] = None,
    ecutrho: Optional[float] = None,
    conv_thr: Optional[float] = None,
    nk1: Optional[int] = None,
    nk2: Optional[int] = None,
    nk3: Optional[int] = None,
    sk1: int = 0,
    sk2: int = 0,
    sk3: int = 0,
    explicit_defaults: bool = True,
) -> Dict[str, Any]:
    """
    Compile precision preset option to QE parameters.
    
    Thin wrapper around registry-driven ParamSpace compilation.
    
    This function requires pre-computed values from PrecisionAdvisor.
    The advisor uses structure + pseudo info to compute actual values.
    
    Args:
        option: PrecisionOption value (LOW, MED, HIGH)
        ecutwfc: Plane-wave cutoff in Ry (required)
        ecutrho: Charge density cutoff in Ry (required)
        conv_thr: SCF convergence threshold (required)
        nk1, nk2, nk3: K-point mesh divisions (required)
        sk1, sk2, sk3: K-point mesh shifts (default 0)
        explicit_defaults: If True, always write VALUE cells; if False, skip if value == default
        
    Returns:
        Dict with SYSTEM, ELECTRONS params and K_POINTS_CARD data
        
    Raises:
        PresetCompilationError: If required values not provided
    """
    from quantumvitas.presets.spaces_registry import compile_dimension_patch
    
    patch, deletions = compile_dimension_patch(
        "precision",
        option,
        {},
        explicit_defaults=explicit_defaults,
        ecutwfc=ecutwfc,
        ecutrho=ecutrho,
        conv_thr=conv_thr,
        nk1=nk1,
        nk2=nk2,
        nk3=nk3,
        sk1=sk1,
        sk2=sk2,
        sk3=sk3,
    )
    
    return patch


def compile_precision_from_advice(advice: "PrecisionAdvice") -> Dict[str, Any]:
    """
    Compile precision preset from PrecisionAdvice object.
    
    Convenience wrapper around compile_precision.
    
    Args:
        advice: PrecisionAdvice from PrecisionAdvisor
        
    Returns:
        Dict with SYSTEM params and K_POINTS card data
    """
    # Import here to avoid circular import
    from quantumvitas.presets.precision import PrecisionAdvice
    
    return compile_precision(
        advice.precision,
        ecutwfc=advice.ecutwfc,
        ecutrho=advice.ecutrho,
        conv_thr=advice.conv_thr,
        nk1=advice.nk1,
        nk2=advice.nk2,
        nk3=advice.nk3,
        sk1=advice.sk1,
        sk2=advice.sk2,
        sk3=advice.sk3,
    )


def compile_presets(
    options: Dict[str, Any],
    *,
    validate_physics: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """
    Compile all preset options to QE parameters.
    
    This is the main Compiler entry point per Constitution §10.3.1:
    compile_one(step_type, options) -> full_parameter_dict
    
    Note: This implementation is step_type-agnostic for v0.
    Future versions may have step_type-specific compilation.
    
    Args:
        options: Dict with preset dimension keys:
            - 'magnetism': MagnetismOption or string value
            - 'occupations_scheme': OccupationsSchemeOption or string value
        validate_physics: If True, validate physics constraints (default True)
        
    Returns:
        Dict with section -> params structure:
        {"SYSTEM": {...all compiled params...}}
        
    Raises:
        PresetCompilationError: If invalid option combinations
        
    Example:
        >>> options = {'magnetism': MagnetismOption.COLLINEAR_LSDA, 'occupations_scheme': OccupationsSchemeOption.SMEARING_GAUSSIAN}
        >>> compile_presets(options)
        {'SYSTEM': {'nspin': 2, 'noncolin': '.false.', 'lspinorb': '.false.', 'occupations': 'smearing', ...}}
    """
    # Normalize options to enum values
    magnetism = _normalize_option(
        options.get(DIMENSION_MAGNETISM),
        MagnetismOption,
        MagnetismOption.NONMAGNETIC,
    )
    occupations_scheme = _normalize_option(
        options.get(DIMENSION_OCCUPATIONS_SCHEME),
        OccupationsSchemeOption,
        OccupationsSchemeOption.FIXED,
    )
    
    # Compile each dimension
    system_params: Dict[str, Any] = {}
    
    # Magnetism params (merged spin + SOC)
    magnetism_patch = compile_magnetism(magnetism)
    if "SYSTEM" in magnetism_patch:
        system_params.update(magnetism_patch["SYSTEM"])
    
    # Occupations scheme params
    occ_patch = compile_occupations_scheme(occupations_scheme)
    if "SYSTEM" in occ_patch:
        system_params.update(occ_patch["SYSTEM"])
    
    return {"SYSTEM": system_params}


def compile_presets_for_step(
    step_type: str,
    options: Dict[str, Any],
    *,
    validate_physics: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """
    Compile preset options for a specific step type.
    
    Currently step_type-agnostic for v0 preset dimensions.
    Post-processing steps (dos, bands, etc.) don't use SYSTEM params
    from presets - they inherit from the preceding PW calculation.
    
    Args:
        step_type: The step type (scf, nscf, relax, etc.)
        options: Preset options dict
        validate_physics: If True, validate physics constraints
        
    Returns:
        Dict with section -> params structure
    """
    # For v0, all step types use the same preset compilation
    # Post-processing steps don't need preset params (they use preceding calc's settings)
    POST_PROCESSING_TYPES = {"dos", "bands", "projwfc", "pp", "q2r", "matdyn", "dynmat"}
    
    step_type_lower = step_type.lower() if step_type else ""
    
    if step_type_lower in POST_PROCESSING_TYPES:
        # Post-processing steps don't have their own SYSTEM params
        # They use the preceding PW calculation's settings
        return {}
    
    return compile_presets(options, validate_physics=validate_physics)


def _normalize_option(
    value: Any,
    enum_class: type,
    default: Any,
) -> Any:
    """
    Normalize an option value to its enum type.
    
    Handles:
    - Already an enum instance → return as-is
    - String value → convert to enum by value
    - None → return default
    """
    if value is None:
        return default
    
    if isinstance(value, enum_class):
        return value
    
    if isinstance(value, str):
        # Try to match by value
        for member in enum_class:
            if member.value == value.lower():
                return member
        raise ValueError(f"Unknown {enum_class.__name__} value: {value}")
    
    raise ValueError(f"Cannot normalize {value} to {enum_class.__name__}")


# Convenience functions for single-dimension compilation

def compile_one_dimension(
    dimension: str,
    value: Any,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compile a single preset dimension to SYSTEM parameters.
    
    Args:
        dimension: Dimension name ('spin', 'soc', 'material')
        value: Dimension value (enum or string)
        context: Optional context for dimension interactions (e.g., spin for SOC)
        
    Returns:
        Dict of SYSTEM parameters for this dimension
    """
    if dimension == DIMENSION_MAGNETISM:
        option = _normalize_option(value, MagnetismOption, MagnetismOption.NONMAGNETIC)
        return compile_magnetism(option)
    
    elif dimension == DIMENSION_MATERIAL:
        option = _normalize_option(value, OccupationsSchemeOption, OccupationsSchemeOption.FIXED)
        return compile_occupations_scheme(option)
    
    else:
        raise ValueError(f"Unknown preset dimension: {dimension}")

