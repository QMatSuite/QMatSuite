"""
Detector B: Reverse detection of presets from step parameters.

This module implements Detector B per Constitution Chapter 10.4-10.5:
- Detector B is the sole legitimate source for preset/option state (10.4.1)
- No "Selected vs Detected" dual-track model (10.4.2)
- Supports implicit default semantics (10.5.3)

Detector B is a "semantic interpreter" - it tolerantly infers user intent
from step parameters, including handling implicit QE defaults.

Key functions:
- detect_spin(params) -> SpinOption: Detect spin treatment from step params
- detect_soc(params) -> SOCOption: Detect SOC from step params
- detect_material(params) -> MaterialOption: Detect material type from step params
- detect_all_presets(steps) -> Dict: Aggregate detection across all steps
"""

from typing import Any, Dict, List, Union

from quantumvitas.presets.dimensions import (
    SpinOption,
    SOCOption,
    MaterialOption,
    CUSTOM,
    DIMENSION_SPIN,
    DIMENSION_SOC,
    DIMENSION_MATERIAL,
    V0_DIMENSIONS,
    _CustomType,
)


def _get_system_param(
    params: Dict[str, Dict[str, Any]],
    key: str,
    default: Any = None,
) -> Any:
    """
    Get a parameter from the SYSTEM namelist (case-insensitive).
    
    Args:
        params: Step parameters dict (section -> params)
        key: Parameter name to find
        default: Default value if not found
        
    Returns:
        Parameter value or default
    """
    # Try both cases for section name
    system = params.get("SYSTEM") or params.get("system") or {}
    
    # Try exact key first, then lowercase
    if key in system:
        return system[key]
    if key.lower() in system:
        return system[key.lower()]
    
    # Also check for key variations (QE allows case-insensitive params)
    for k, v in system.items():
        if k.lower() == key.lower():
            return v
    
    return default


def _parse_bool(value: Any) -> bool:
    """
    Parse a QE boolean value (handles Fortran .true./.false. strings).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in (".true.", "true", "t", ".t."):
            return True
        if lower in (".false.", "false", "f", ".f."):
            return False
    # Numeric: 0 = False, non-zero = True
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _parse_int(value: Any, default: int = 0) -> int:
    """
    Parse a QE integer value.
    """
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def detect_spin(params: Dict[str, Dict[str, Any]]) -> SpinOption:
    """
    Detect spin treatment from step parameters.
    
    Detection logic (per QE documentation):
    1. If noncolin = .true. → NONCOLLINEAR (nspin=4 internally)
    2. If nspin = 2 → COLLINEAR (LSDA)
    3. If nspin = 1 or absent → NONSPIN (default)
    
    Implicit defaults (per Constitution 10.5.3):
    - Missing nspin → 1 (nonspin)
    - Missing noncolin → .false.
    
    Args:
        params: Step parameters dict with section -> params structure
        
    Returns:
        Detected SpinOption
    """
    # Check noncolin first (takes precedence)
    noncolin = _get_system_param(params, "noncolin")
    if noncolin is not None and _parse_bool(noncolin):
        return SpinOption.NONCOLLINEAR
    
    # Check nspin
    nspin = _get_system_param(params, "nspin")
    nspin_val = _parse_int(nspin, default=1)  # QE default is 1
    
    if nspin_val == 2:
        return SpinOption.COLLINEAR
    elif nspin_val == 4:
        # nspin=4 implies noncollinear, but noncolin should be set
        # This handles edge case where nspin=4 is set without noncolin
        return SpinOption.NONCOLLINEAR
    else:
        # nspin=1 or implicit default
        return SpinOption.NONSPIN


def detect_soc(params: Dict[str, Dict[str, Any]]) -> SOCOption:
    """
    Detect spin-orbit coupling from step parameters.
    
    Detection logic:
    - If lspinorb = .true. → WITH_SOC
    - Otherwise → NO_SOC
    
    Implicit defaults (per Constitution 10.5.3):
    - Missing lspinorb → .false. (no SOC)
    
    Note: WITH_SOC physically requires noncolin=.true., but detector
    only reports what parameters say, not physics validity.
    
    Args:
        params: Step parameters dict with section -> params structure
        
    Returns:
        Detected SOCOption
    """
    lspinorb = _get_system_param(params, "lspinorb")
    
    if lspinorb is not None and _parse_bool(lspinorb):
        return SOCOption.WITH_SOC
    
    # Implicit default: no SOC
    return SOCOption.NO_SOC


def detect_material(params: Dict[str, Dict[str, Any]]) -> MaterialOption:
    """
    Detect material type (insulator/metal) from step parameters.
    
    Detection logic (based on occupations parameter):
    - If occupations = 'smearing' → METAL
    - If occupations = 'tetrahedra*' → INSULATOR (requires uniform k-grid)
    - If occupations = 'fixed' → INSULATOR (explicit gap)
    - If occupations absent → INSULATOR (QE defaults assume insulating)
    
    Note: 'from_input' is ambiguous; we treat it as INSULATOR since
    it's typically used for specialized cases, not metallic smearing.
    
    Args:
        params: Step parameters dict with section -> params structure
        
    Returns:
        Detected MaterialOption
    """
    occupations = _get_system_param(params, "occupations")
    
    if occupations is None:
        # Implicit default: insulator (fixed occupations)
        return MaterialOption.INSULATOR
    
    # Normalize string value
    occ_str = str(occupations).lower().strip().strip("'\"")
    
    if occ_str == "smearing":
        return MaterialOption.METAL
    
    # Tetrahedra variants are for insulators
    if occ_str.startswith("tetrahedra"):
        return MaterialOption.INSULATOR
    
    if occ_str == "fixed":
        return MaterialOption.INSULATOR
    
    if occ_str == "from_input":
        # Ambiguous, but typically insulating behavior
        return MaterialOption.INSULATOR
    
    # Unknown value - default to insulator
    return MaterialOption.INSULATOR


def _detect_dimension(
    params: Dict[str, Dict[str, Any]],
    dimension: str,
) -> Union[SpinOption, SOCOption, MaterialOption]:
    """
    Detect a single dimension value from step parameters.
    
    Args:
        params: Step parameters dict
        dimension: Dimension name (spin, soc, material)
        
    Returns:
        Detected value for the dimension
        
    Raises:
        ValueError: If dimension is not recognized
    """
    if dimension == DIMENSION_SPIN:
        return detect_spin(params)
    elif dimension == DIMENSION_SOC:
        return detect_soc(params)
    elif dimension == DIMENSION_MATERIAL:
        return detect_material(params)
    else:
        raise ValueError(f"Unknown preset dimension: {dimension}")


def detect_dimension_from_steps(
    steps: List[Dict[str, Dict[str, Any]]],
    dimension: str,
) -> Union[SpinOption, SOCOption, MaterialOption, _CustomType]:
    """
    Detect a preset dimension value aggregated across multiple steps.
    
    Per Constitution 10.5.1:
    - If all steps have the same value → return that value
    - If steps have different values → return CUSTOM
    - Single step is valid (returns its value, not CUSTOM)
    
    Args:
        steps: List of step parameters dicts
        dimension: Dimension name to detect
        
    Returns:
        Detected value or CUSTOM if heterogeneous
    """
    if not steps:
        # No steps - return default for dimension
        # This handles edge case of empty step list
        return _detect_dimension({}, dimension)
    
    # Collect unique values across all steps
    values = set()
    for step_params in steps:
        value = _detect_dimension(step_params, dimension)
        values.add(value)
    
    # Per Constitution 10.5.1: single unique value or Custom
    if len(values) == 1:
        return values.pop()
    else:
        return CUSTOM


def detect_all_presets(
    steps: List[Dict[str, Dict[str, Any]]],
) -> Dict[str, Union[SpinOption, SOCOption, MaterialOption, _CustomType]]:
    """
    Detect all v0 preset dimensions from a list of steps.
    
    This is the main entry point for Detector B. It returns the detected
    value for each dimension, aggregated across all steps.
    
    Per Constitution 10.4.1: This is the sole legitimate source for
    preset/option state. UI should derive all state from this function.
    
    Args:
        steps: List of step parameters dicts (section -> params)
        
    Returns:
        Dict mapping dimension name to detected value (or CUSTOM)
        
    Example:
        >>> steps = [{"SYSTEM": {"nspin": 2}}]
        >>> detect_all_presets(steps)
        {"spin": SpinOption.COLLINEAR, "soc": SOCOption.NO_SOC, "material": MaterialOption.INSULATOR}
    """
    result = {}
    for dimension in V0_DIMENSIONS:
        result[dimension] = detect_dimension_from_steps(steps, dimension)
    return result


def detect_presets_from_step_specs(
    step_specs: List[Any],
) -> Dict[str, Union[SpinOption, SOCOption, MaterialOption, _CustomType]]:
    """
    Convenience function to detect presets from StructureStepSpec objects.
    
    Extracts the parameters dict from each step spec and runs detection.
    
    Args:
        step_specs: List of StructureStepSpec objects
        
    Returns:
        Dict mapping dimension name to detected value (or CUSTOM)
    """
    # Extract parameters from step specs
    steps_params = []
    for spec in step_specs:
        # Handle both dict and object forms
        if hasattr(spec, "parameters"):
            steps_params.append(spec.parameters or {})
        elif isinstance(spec, dict):
            steps_params.append(spec.get("parameters", {}))
        else:
            steps_params.append({})
    
    return detect_all_presets(steps_params)

