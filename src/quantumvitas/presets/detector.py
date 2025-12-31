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

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
    Extract K_POINTS automatic mesh from step content.
    
    QE kpoints are represented as cards.K_POINTS only.
    Format: cards.K_POINTS = {"option": "automatic", "data": [[nk1, nk2, nk3, sk1, sk2, sk3]]}
    
    Returns:
        Tuple of (nk1, nk2, nk3, sk1, sk2, sk3) or None if not automatic mesh or not found.
    """
    cards = params.get("cards") or {}
    kpoints_card = cards.get("K_POINTS") or cards.get("k_points") or {}
    
    if not kpoints_card:
        return None
    
    option = kpoints_card.get("option", "").lower()
    if option != "automatic":
        return None
    
    data = kpoints_card.get("data", [])
    if not data or not isinstance(data, list) or len(data) == 0:
        return None
    
    mesh_row = data[0]
    if not isinstance(mesh_row, (list, tuple)) or len(mesh_row) < 3:
        return None
    
    nk1 = int(mesh_row[0])
    nk2 = int(mesh_row[1])
    nk3 = int(mesh_row[2])
    sk1 = int(mesh_row[3]) if len(mesh_row) > 3 else 0
    sk2 = int(mesh_row[4]) if len(mesh_row) > 4 else 0
    sk3 = int(mesh_row[5]) if len(mesh_row) > 5 else 0
    
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
    *,
    step_types: Optional[List[str]] = None,
    calculation_dir: Optional[Path] = None,
) -> Union[SpinOption, SOCOption, MaterialOption, PrecisionOption, _CustomType]:
    """
    Detect a preset dimension value aggregated across multiple steps.
    
    Per Constitution 10.5.1:
    - If all steps have the same value → return that value
    - If steps have different values → return CUSTOM
    - Single step is valid (returns its value, not CUSTOM)
    
    For precision dimension: Uses step-type-aware strict detection if
    step_types and calculation_dir are provided.
    
    Args:
        steps: List of step parameters dicts
        dimension: Dimension name to detect
        step_types: Optional list of step_type strings (one per step)
        calculation_dir: Optional calculation directory (for precision detection)
        
    Returns:
        Detected value or CUSTOM if heterogeneous
    """
    if not steps:
        # No steps - for precision, return CUSTOM (safer than default)
        # For other dimensions, return default
        if dimension == DIMENSION_PRECISION:
            return CUSTOM
        return _detect_dimension({}, dimension)
    
    # For precision, use step-type-aware strict detection if possible
    if dimension == DIMENSION_PRECISION and step_types and calculation_dir:
        try:
            return _detect_precision_from_steps_strict(steps, step_types, calculation_dir)
        except Exception as e:
            # If precision detection fails (e.g., structure resolution error),
            # return CUSTOM rather than raising (to maintain backward compatibility)
            # But log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Precision detection failed, returning CUSTOM: {e}")
            return CUSTOM
    
    # For other dimensions or when step_types not available, use simple detection
    values = set()
    for step_params in steps:
        value = _detect_dimension(step_params, dimension)
        values.add(value)
    
    # Per Constitution 10.5.1: single unique value or Custom
    if len(values) == 1:
        return values.pop()
    else:
        return CUSTOM


def _detect_precision_from_steps_strict(
    steps: List[Dict[str, Dict[str, Any]]],
    step_types: List[str],
    calculation_dir: Path,
) -> Union[PrecisionOption, _CustomType]:
    """
    Detect precision from steps using step-type-aware strict matching.
    
    Only receiver steps are considered. Non-receiver steps are wildcards.
    Each receiver step must match its step-type-specific canonical values.
    
    Args:
        steps: List of step parameters dicts
        step_types: List of step_type strings (one per step)
        calculation_dir: Calculation directory (for loading structure/species_map)
        
    Returns:
        PrecisionOption if all receiver steps match, CUSTOM otherwise
    """
    from quantumvitas.presets.receivers import get_precision_receiver_spec
    from quantumvitas.core.models import load_calculation
    
    if len(steps) != len(step_types):
        # Mismatch - can't do step-type-aware detection
        return CUSTOM
    
    # Use unified resolver (single source of truth)
    try:
        from quantumvitas.presets.precision_context import (
            resolve_precision_context,
            PrecisionContextError,
        )
        from quantumvitas.presets.precision import aggregate_cutoffs
        
        # Resolve context using unified resolver
        context = resolve_precision_context(
            calculation_dir=calculation_dir,
            project_root=None,  # Will be derived from calculation_dir
        )
        
        # Extract values from context
        species_map = context.species_map
        lattice_matrix = context.lattice_matrix
        
        # Get base cutoffs from pseudos (using context's pseudo_index)
        base_ecutwfc, base_ecutrho = aggregate_cutoffs(species_map, context.pseudo_index)
        
    except PrecisionContextError as e:
        # Precision context resolution failed - this is an error, not CUSTOM
        # Raise exception to propagate error (don't silently return CUSTOM)
        raise PrecisionContextError(
            f"Failed to resolve precision context for detection: {e}"
        ) from e
    except Exception as e:
        # Other errors should also be raised
        from quantumvitas.presets.precision_context import PrecisionContextError
        raise PrecisionContextError(
            f"Unexpected error during precision context resolution: {e}"
        ) from e
    
    # Collect detected precision for each receiver step
    receiver_values = []
    
    for step_params, step_type in zip(steps, step_types):
        spec = get_precision_receiver_spec(step_type)
        
        # Non-receiver steps are wildcards (don't contribute)
        if not spec or not spec.accepts_any:
            continue
        
        # Use strict detection with step-type-aware canonical values
        detected = detect_precision_strict_for_step_type(
            step_params, step_type, lattice_matrix, base_ecutwfc, base_ecutrho
        )
        
        if detected is None:
            # Step doesn't match any precision level
            return CUSTOM
        
        receiver_values.append(detected)
    
    # If no receiver steps, return default
    if not receiver_values:
        return PrecisionOption.MED  # Default
    
    # Check if all receiver steps agree
    unique_values = set(receiver_values)
    if len(unique_values) == 1:
        return unique_values.pop()
    else:
        return CUSTOM


def detect_precision_strict_for_step_type(
    params: Dict[str, Dict[str, Any]],
    step_type: str,
    lattice_matrix: List[List[float]],
    base_ecutwfc: float,
    base_ecutrho: float,
) -> Optional[PrecisionOption]:
    """
    Detect precision with strict matching for a specific step type.
    
    Uses step-type-specific canonical values (e.g., nscf ×2 mesh).
    
    Args:
        params: Step parameters dict
        step_type: Step type string
        lattice_matrix: 3x3 lattice vectors in Angstrom
        base_ecutwfc: Base ecutwfc from pseudos
        base_ecutrho: Base ecutrho from pseudos
        
    Returns:
        PrecisionOption if matches, None otherwise
    """
    from quantumvitas.presets.receivers import get_precision_receiver_spec
    from quantumvitas.presets.precision import (
        PRECISION_CONSTANTS,
        CONV_THR_ABS_TOL,
        compute_kmesh,
        round_cutoff_integer,
        NSCF_KMESH_FACTOR,
    )
    
    spec = get_precision_receiver_spec(step_type)
    if not spec or not spec.accepts_any:
        return None  # Non-receiver step
    
    # Extract actual values
    actual_conv_thr = _parse_float(_get_electrons_param(params, "conv_thr"), None)
    actual_ecutwfc = _parse_int(_get_system_param(params, "ecutwfc"), None)
    actual_ecutrho = _parse_int(_get_system_param(params, "ecutrho"), None)
    actual_kmesh = _get_kpoints_mesh(params)
    
    # Check required params based on spec
    if spec.accepts_conv_thr and actual_conv_thr is None:
        return None
    if spec.accepts_cutoffs and (actual_ecutwfc is None or actual_ecutrho is None):
        return None
    if spec.accepts_kmesh and actual_kmesh is None:
        return None
    
    # Check each precision level
    for level, constants in PRECISION_CONSTANTS.items():
        # Check conv_thr if required
        if spec.accepts_conv_thr:
            if abs(actual_conv_thr - constants.conv_thr) > CONV_THR_ABS_TOL:
                continue
        
        # Check cutoffs if required
        if spec.accepts_cutoffs:
            canonical_ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
            canonical_ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
            
            if actual_ecutwfc != canonical_ecutwfc:
                continue
            if actual_ecutrho != canonical_ecutrho:
                continue
        
        # Check kmesh if required
        if spec.accepts_kmesh and spec.kmesh_strategy != "none":
            # Compute base mesh
            base_nk1, base_nk2, base_nk3, sk1, sk2, sk3 = compute_kmesh(lattice_matrix, constants.delta_k)
            
            # Apply step-type strategy
            if spec.kmesh_strategy == "nscf":
                canonical_nk1 = max(1, base_nk1 * NSCF_KMESH_FACTOR)
                canonical_nk2 = max(1, base_nk2 * NSCF_KMESH_FACTOR)
                canonical_nk3 = max(1, base_nk3 * NSCF_KMESH_FACTOR)
            else:  # "default"
                canonical_nk1, canonical_nk2, canonical_nk3 = base_nk1, base_nk2, base_nk3
            
            actual_nk1, actual_nk2, actual_nk3, actual_sk1, actual_sk2, actual_sk3 = actual_kmesh
            
            if (actual_nk1, actual_nk2, actual_nk3) != (canonical_nk1, canonical_nk2, canonical_nk3):
                continue
            if (actual_sk1, actual_sk2, actual_sk3) != (sk1, sk2, sk3):
                continue
        
        # All required checks passed for this level
        return level
    
    # No level matched
    return None


def detect_all_presets(
    steps: List[Dict[str, Dict[str, Any]]],
    *,
    include_precision: bool = True,
    step_types: Optional[List[str]] = None,
    calculation_dir: Optional[Path] = None,
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
        step_types: Optional list of step_type strings (for step-type-aware precision detection)
        calculation_dir: Optional calculation directory (for precision detection)
        
    Returns:
        Dict mapping dimension name to detected value (or CUSTOM)
        
    Example:
        >>> steps = [{"SYSTEM": {"nspin": 2}}]
        >>> detect_all_presets(steps)
        {"spin": SpinOption.COLLINEAR, "soc": SOCOption.NO_SOC, "material": MaterialOption.INSULATOR, "precision": PrecisionOption.MED}
    """
    from pathlib import Path
    
    dimensions = V1_DIMENSIONS if include_precision else V0_DIMENSIONS
    result = {}
    for dimension in dimensions:
        result[dimension] = detect_dimension_from_steps(
            steps, dimension,
            step_types=step_types,
            calculation_dir=Path(calculation_dir) if calculation_dir else None,
        )
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

