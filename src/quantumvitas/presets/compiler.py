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
- compile_spin(option) -> Dict: Generate spin-related SYSTEM params
- compile_soc(option, spin) -> Dict: Generate SOC-related SYSTEM params
- compile_material(option) -> Dict: Generate material-related SYSTEM params
- compile_presets(options) -> Dict: Generate all preset params combined
"""

from typing import Any, Dict, Optional

from quantumvitas.presets.dimensions import (
    SpinOption,
    SOCOption,
    MaterialOption,
    PrecisionOption,
    DIMENSION_SPIN,
    DIMENSION_SOC,
    DIMENSION_MATERIAL,
    DIMENSION_PRECISION,
)


class PresetCompilationError(Exception):
    """Raised when preset compilation fails due to invalid combinations."""
    pass


def compile_spin(option: SpinOption) -> Dict[str, Any]:
    """
    Compile spin preset option to QE SYSTEM parameters.
    
    Per Constitution §10.3.4 (Canonical Encoding):
    - All key semantics must be explicitly written
    - Do not rely on QE defaults
    
    Args:
        option: SpinOption value (NONSPIN, COLLINEAR, NONCOLLINEAR)
        
    Returns:
        Dict of SYSTEM parameters for spin treatment
        
    Mapping:
        NONSPIN → nspin=1
        COLLINEAR → nspin=2
        NONCOLLINEAR → noncolin=.true. (QE internally uses nspin=4)
    """
    if option == SpinOption.NONSPIN:
        return {"nspin": 1}
    
    elif option == SpinOption.COLLINEAR:
        return {"nspin": 2}
    
    elif option == SpinOption.NONCOLLINEAR:
        # For noncollinear, we set noncolin=.true.
        # QE internally treats this as nspin=4, but we don't explicitly write nspin
        # because QE docs say "DO NOT specify nspin in this case"
        return {"noncolin": ".true."}
    
    else:
        raise ValueError(f"Unknown spin option: {option}")


def compile_soc(option: SOCOption, spin: Optional[SpinOption] = None) -> Dict[str, Any]:
    """
    Compile SOC preset option to QE SYSTEM parameters.
    
    Per Constitution §10.3.4 (Canonical Encoding):
    - Explicitly write lspinorb even when false
    
    Physics constraint:
    - SOC requires noncollinear calculation (noncolin=.true.)
    - If with_soc is requested with non-noncollinear spin, raise error
    
    Args:
        option: SOCOption value (NO_SOC, WITH_SOC)
        spin: Optional SpinOption for validation (required if WITH_SOC)
        
    Returns:
        Dict of SYSTEM parameters for SOC
        
    Raises:
        PresetCompilationError: If WITH_SOC requested with incompatible spin
    """
    if option == SOCOption.NO_SOC:
        return {"lspinorb": ".false."}
    
    elif option == SOCOption.WITH_SOC:
        # Physics constraint: SOC requires noncollinear
        if spin is not None and spin != SpinOption.NONCOLLINEAR:
            raise PresetCompilationError(
                f"Spin-orbit coupling (SOC) requires noncollinear spin treatment. "
                f"Got spin={spin.value}, but WITH_SOC requires spin=noncollinear. "
                f"Either change spin to 'noncollinear' or SOC to 'no_soc'."
            )
        return {"lspinorb": ".true."}
    
    else:
        raise ValueError(f"Unknown SOC option: {option}")


def compile_material(option: MaterialOption) -> Dict[str, Any]:
    """
    Compile material preset option to QE SYSTEM parameters.
    
    Per Constitution §10.3.4 (Canonical Encoding):
    - Explicitly write all relevant parameters
    - For metals: include smearing type and degauss
    
    Args:
        option: MaterialOption value (INSULATOR, METAL)
        
    Returns:
        Dict of SYSTEM parameters for material type
        
    Mapping:
        INSULATOR → occupations='fixed'
        METAL → occupations='smearing', smearing='gaussian', degauss=0.01
    """
    if option == MaterialOption.INSULATOR:
        return {"occupations": "'fixed'"}
    
    elif option == MaterialOption.METAL:
        # Provide canonical smearing parameters for metals
        # Users can override via step params if needed
        return {
            "occupations": "'smearing'",
            "smearing": "'gaussian'",
            "degauss": 0.01,
        }
    
    else:
        raise ValueError(f"Unknown material option: {option}")


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
) -> Dict[str, Any]:
    """
    Compile precision preset option to QE parameters.
    
    This function requires pre-computed values from PrecisionAdvisor.
    The advisor uses structure + pseudo info to compute actual values.
    
    Per Constitution §10.3.4 (Canonical Encoding):
    - Explicitly write ecutwfc, ecutrho, conv_thr
    - Write K_POINTS automatic with computed mesh
    
    Args:
        option: PrecisionOption value (LOW, MED, HIGH)
        ecutwfc: Plane-wave cutoff in Ry (required)
        ecutrho: Charge density cutoff in Ry (required)
        conv_thr: SCF convergence threshold (required)
        nk1, nk2, nk3: K-point mesh divisions (required)
        sk1, sk2, sk3: K-point mesh shifts (default 0)
        
    Returns:
        Dict with SYSTEM params and K_POINTS card data
        
    Raises:
        PresetCompilationError: If required values not provided
    """
    # Validate required parameters
    if ecutwfc is None or ecutrho is None or conv_thr is None:
        raise PresetCompilationError(
            f"Precision preset compilation requires ecutwfc, ecutrho, and conv_thr. "
            f"Use PrecisionAdvisor to compute these from structure and pseudos."
        )
    
    if nk1 is None or nk2 is None or nk3 is None:
        raise PresetCompilationError(
            f"Precision preset compilation requires k-mesh (nk1, nk2, nk3). "
            f"Use PrecisionAdvisor to compute these from structure."
        )
    
    # Return K_POINTS in cards format (canonical)
    # Format: {"option": "automatic", "data": [[nk1, nk2, nk3, sk1, sk2, sk3]]}
    return {
        "SYSTEM": {
            "ecutwfc": ecutwfc,
            "ecutrho": ecutrho,
        },
        "ELECTRONS": {
            "conv_thr": conv_thr,
        },
        "K_POINTS_CARD": {
            "option": "automatic",
            "data": [[nk1, nk2, nk3, sk1, sk2, sk3]],
        },
    }


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
            - 'spin': SpinOption or string value
            - 'soc': SOCOption or string value  
            - 'material': MaterialOption or string value
        validate_physics: If True, validate physics constraints (default True)
        
    Returns:
        Dict with section -> params structure:
        {"SYSTEM": {...all compiled params...}}
        
    Raises:
        PresetCompilationError: If invalid option combinations
        
    Example:
        >>> options = {'spin': SpinOption.COLLINEAR, 'soc': SOCOption.NO_SOC, 'material': MaterialOption.METAL}
        >>> compile_presets(options)
        {'SYSTEM': {'nspin': 2, 'lspinorb': '.false.', 'occupations': "'smearing'", ...}}
    """
    # Normalize options to enum values
    spin = _normalize_option(options.get(DIMENSION_SPIN), SpinOption, SpinOption.NONSPIN)
    soc = _normalize_option(options.get(DIMENSION_SOC), SOCOption, SOCOption.NO_SOC)
    material = _normalize_option(options.get(DIMENSION_MATERIAL), MaterialOption, MaterialOption.INSULATOR)
    
    # Compile each dimension
    system_params: Dict[str, Any] = {}
    
    # Spin params
    system_params.update(compile_spin(spin))
    
    # SOC params (with physics validation)
    if validate_physics:
        system_params.update(compile_soc(soc, spin=spin))
    else:
        system_params.update(compile_soc(soc, spin=None))
    
    # Material params
    system_params.update(compile_material(material))
    
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
    if dimension == DIMENSION_SPIN:
        option = _normalize_option(value, SpinOption, SpinOption.NONSPIN)
        return compile_spin(option)
    
    elif dimension == DIMENSION_SOC:
        option = _normalize_option(value, SOCOption, SOCOption.NO_SOC)
        spin = None
        if context and DIMENSION_SPIN in context:
            spin = _normalize_option(context[DIMENSION_SPIN], SpinOption, None)
        return compile_soc(option, spin=spin)
    
    elif dimension == DIMENSION_MATERIAL:
        option = _normalize_option(value, MaterialOption, MaterialOption.INSULATOR)
        return compile_material(option)
    
    else:
        raise ValueError(f"Unknown preset dimension: {dimension}")

