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
    PrecisionOption,
    CUSTOM,
    DIMENSION_SPIN,
    DIMENSION_SOC,
    DIMENSION_MATERIAL,
    DIMENSION_PRECISION,
    V0_DIMENSIONS,
    V1_DIMENSIONS,
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


def _get_electrons_param(
    params: Dict[str, Dict[str, Any]],
    key: str,
    default: Any = None,
) -> Any:
    """
    Get a parameter from the ELECTRONS namelist (case-insensitive).
    """
    electrons = params.get("ELECTRONS") or params.get("electrons") or {}
    
    if key in electrons:
        return electrons[key]
    if key.lower() in electrons:
        return electrons[key.lower()]
    
    for k, v in electrons.items():
        if k.lower() == key.lower():
            return v
    
    return default


def _get_kpoints_mesh(params: Dict[str, Dict[str, Any]]) -> Optional[Tuple[int, int, int, int, int, int]]:
    """
    Extract K_POINTS automatic mesh from parameters.
    
    Returns:
        Tuple of (nk1, nk2, nk3, sk1, sk2, sk3) or None if not automatic mesh.
    """
    kpoints = params.get("K_POINTS") or params.get("k_points") or {}
    
    # Check if it's automatic type
    kp_type = kpoints.get("type", "").lower()
    if kp_type != "automatic":
        return None
    
    mesh = kpoints.get("mesh")
    if not mesh or not isinstance(mesh, (list, tuple)) or len(mesh) < 3:
        return None
    
    # Extract nk and shifts
    nk1 = int(mesh[0]) if len(mesh) > 0 else 1
    nk2 = int(mesh[1]) if len(mesh) > 1 else 1
    nk3 = int(mesh[2]) if len(mesh) > 2 else 1
    sk1 = int(mesh[3]) if len(mesh) > 3 else 0
    sk2 = int(mesh[4]) if len(mesh) > 4 else 0
    sk3 = int(mesh[5]) if len(mesh) > 5 else 0
    
    return (nk1, nk2, nk3, sk1, sk2, sk3)


def _parse_float(value: Any, default: float = 0.0) -> float:
    """Parse a QE float value."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            # Handle Fortran-style exponents (1d-8 -> 1e-8)
            value = value.lower().replace('d', 'e')
            return float(value)
        except ValueError:
            return default
    return default


def _parse_int(value: Any, default: int = 0) -> int:
    """Parse a QE integer value."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def detect_precision(params: Dict[str, Dict[str, Any]]) -> PrecisionOption:
    """
    Detect precision level from step parameters (simple heuristic).
    
    This is a fallback detection based only on conv_thr when structure
    info is not available. For strict detection, use detect_precision_strict().
    
    Detection logic (based on conv_thr ranges):
    - conv_thr >= 5e-7 (loose) → LOW
    - 5e-9 <= conv_thr < 5e-7 → MED
    - conv_thr < 5e-9 (tight) → HIGH
    
    Args:
        params: Step parameters dict with section -> params structure
        
    Returns:
        Detected PrecisionOption (heuristic, may not be exact)
    """
    conv_thr = _get_electrons_param(params, "conv_thr")
    
    if conv_thr is None:
        # QE default is 1e-6, which corresponds to LOW
        # But we're generous and return MED if unspecified
        return PrecisionOption.MED
    
    conv_thr_val = _parse_float(conv_thr, 1e-6)
    
    # Classification based on conv_thr ranges
    if conv_thr_val >= 5e-7:
        return PrecisionOption.LOW
    elif conv_thr_val >= 5e-9:
        return PrecisionOption.MED
    else:
        return PrecisionOption.HIGH


def detect_precision_strict(
    params: Dict[str, Dict[str, Any]],
    lattice_matrix: List[List[float]],
    base_ecutwfc: float,
    base_ecutrho: float,
) -> Optional[PrecisionOption]:
    """
    Detect precision level with strict 3-way matching.
    
    Checks all three aspects for each level:
    1. conv_thr matches canonical value (within abs_tol)
    2. K_POINTS automatic mesh matches canonical computed mesh
    3. ecutwfc AND ecutrho match canonical integer-rounded values
    
    Args:
        params: Step parameters dict
        lattice_matrix: 3x3 lattice vectors in Angstrom
        base_ecutwfc: Base ecutwfc from pseudos (before multiplier)
        base_ecutrho: Base ecutrho from pseudos (before multiplier)
        
    Returns:
        PrecisionOption if all aspects match a level, None otherwise
    """
    from quantumvitas.presets.precision import (
        PRECISION_CONSTANTS,
        CONV_THR_ABS_TOL,
        compute_kmesh,
        round_cutoff_integer,
    )
    
    # Extract actual values from params
    actual_conv_thr = _parse_float(_get_electrons_param(params, "conv_thr"), None)
    actual_ecutwfc = _parse_int(_get_system_param(params, "ecutwfc"), None)
    actual_ecutrho = _parse_int(_get_system_param(params, "ecutrho"), None)
    actual_kmesh = _get_kpoints_mesh(params)
    
    # If essential params are missing, can't do strict match
    if actual_conv_thr is None or actual_ecutwfc is None or actual_ecutrho is None:
        return None
    if actual_kmesh is None:
        return None
    
    actual_nk1, actual_nk2, actual_nk3, actual_sk1, actual_sk2, actual_sk3 = actual_kmesh
    
    # Check each precision level
    for level, constants in PRECISION_CONSTANTS.items():
        # Compute canonical values for this level
        canonical_conv_thr = constants.conv_thr
        canonical_ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
        canonical_ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
        
        nk1, nk2, nk3, sk1, sk2, sk3 = compute_kmesh(lattice_matrix, constants.delta_k)
        
        # Check conv_thr (with tolerance)
        if abs(actual_conv_thr - canonical_conv_thr) > CONV_THR_ABS_TOL:
            continue
        
        # Check cutoffs (exact integer match)
        if actual_ecutwfc != canonical_ecutwfc:
            continue
        if actual_ecutrho != canonical_ecutrho:
            continue
        
        # Check k-mesh (exact match)
        if (actual_nk1, actual_nk2, actual_nk3) != (nk1, nk2, nk3):
            continue
        if (actual_sk1, actual_sk2, actual_sk3) != (sk1, sk2, sk3):
            continue
        
        # All checks passed for this level
        return level
    
    # No level matched
    return None


def _detect_dimension(
    params: Dict[str, Dict[str, Any]],
    dimension: str,
) -> Union[SpinOption, SOCOption, MaterialOption, PrecisionOption]:
    """
    Detect a single dimension value from step parameters.
    
    Args:
        params: Step parameters dict
        dimension: Dimension name (spin, soc, material, precision)
        
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
    elif dimension == DIMENSION_PRECISION:
        return detect_precision(params)
    else:
        raise ValueError(f"Unknown preset dimension: {dimension}")


def detect_dimension_from_steps(
    steps: List[Dict[str, Dict[str, Any]]],
    dimension: str,
) -> Union[SpinOption, SOCOption, MaterialOption, PrecisionOption, _CustomType]:
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
    *,
    include_precision: bool = True,
) -> Dict[str, Union[SpinOption, SOCOption, MaterialOption, PrecisionOption, _CustomType]]:
    """
    Detect all preset dimensions from a list of steps.
    
    This is the main entry point for Detector B. It returns the detected
    value for each dimension, aggregated across all steps.
    
    Per Constitution 10.4.1: This is the sole legitimate source for
    preset/option state. UI should derive all state from this function.
    
    Args:
        steps: List of step parameters dicts (section -> params)
        include_precision: If True (default), include precision dimension
        
    Returns:
        Dict mapping dimension name to detected value (or CUSTOM)
        
    Example:
        >>> steps = [{"SYSTEM": {"nspin": 2}}]
        >>> detect_all_presets(steps)
        {"spin": SpinOption.COLLINEAR, "soc": SOCOption.NO_SOC, "material": MaterialOption.INSULATOR, "precision": PrecisionOption.MED}
    """
    dimensions = V1_DIMENSIONS if include_precision else V0_DIMENSIONS
    result = {}
    for dimension in dimensions:
        result[dimension] = detect_dimension_from_steps(steps, dimension)
    return result


def detect_presets_from_step_specs(
    step_specs: List[Any],
    *,
    include_precision: bool = True,
) -> Dict[str, Union[SpinOption, SOCOption, MaterialOption, PrecisionOption, _CustomType]]:
    """
    Convenience function to detect presets from StructureStepSpec objects.
    
    Extracts the parameters dict from each step spec and runs detection.
    
    Args:
        step_specs: List of StructureStepSpec objects
        include_precision: If True (default), include precision dimension
        
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
    
    return detect_all_presets(steps_params, include_precision=include_precision)

