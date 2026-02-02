"""
Detector B: Reverse detection of presets from step parameters.

This module implements Detector B per Constitution Chapter 10.4-10.5:
- Detector B is the sole legitimate source for preset/option state (10.4.1)
- No "Selected vs Detected" dual-track model (10.4.2)
- Supports implicit default semantics (10.5.3)

Detector B is a "semantic interpreter" - it tolerantly infers user intent
from step parameters, including handling implicit QE defaults.

Key functions:
- detect_magnetism(params) -> MagnetismOption: Detect magnetism treatment from step params (merged spin + SOC)
- detect_occupations_scheme(params, step_type) -> OccupationsSchemeOption: Detect occupations scheme from step params
- detect_all_presets(steps) -> Dict: Aggregate detection across all steps
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from quantumvitas.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    PrecisionOption,
    CUSTOM,
    DIMENSION_MAGNETISM,
    DIMENSION_OCCUPATIONS_SCHEME,
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


def detect_magnetism(
    params: Dict[str, Dict[str, Any]],
    step_type_gen: str = "scf",
) -> MagnetismOption:
    """
    Detect magnetism treatment from step parameters using variants API.
    
    Args:
        params: Step parameters dict with section -> params structure
        step_type_gen: Step type gen (default "scf" for backward compatibility)
        
    Returns:
        Detected MagnetismOption or CUSTOM
    """
    from quantumvitas.presets.variants_registry import detect_dimension_for_step
    
    detected = detect_dimension_for_step("magnetism", step_type_gen, params)
    
    # If None (no variant applies) or CUSTOM, return CUSTOM
    if detected is None or detected == CUSTOM:
        return CUSTOM
    
    return detected


def detect_occupations_scheme(
    params: Dict[str, Dict[str, Any]],
    step_type_gen: str = "scf",
) -> Union[OccupationsSchemeOption, _CustomType]:
    """
    Detect occupations_scheme from step parameters using variants API.
    
    Args:
        params: Step parameters dict with section -> params structure
        step_type_gen: Step type gen (default "scf" for backward compatibility)
        
    Returns:
        Detected OccupationsSchemeOption or CUSTOM
    """
    from quantumvitas.presets.variants_registry import detect_dimension_for_step
    
    detected = detect_dimension_for_step("occupations_scheme", step_type_gen, params)
    
    # If None (no variant applies) or CUSTOM, return CUSTOM
    if detected is None or detected == CUSTOM:
        return CUSTOM
    
    return detected


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


def _get_kpoints_mesh(params: dict[str, dict[str, Any]]) -> Optional[tuple[int, int, int, int, int, int]]:
    """
    Extract K_POINTS automatic mesh from step content.
    
    QE kpoints are represented as cards.K_POINTS only.
    Format: cards.K_POINTS = {"option": "automatic", "data": [[nk1, nk2, nk3, sk1, sk2, sk3]]}
    
    Returns:
        tuple of (nk1, nk2, nk3, sk1, sk2, sk3) or None if not automatic mesh or not found.
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


def detect_precision(
    params: Dict[str, Dict[str, Any]],
    *,
    lattice_matrix: Optional[List[List[float]]] = None,
    base_ecutwfc: Optional[float] = None,
    base_ecutrho: Optional[float] = None,
) -> Union[PrecisionOption, _CustomType]:
    """
    Detect precision level from step parameters.
    
    Thin wrapper around registry-driven ParamSpace detection.
    
    Requires structure + pseudo context for strict matching.
    Returns CUSTOM if context not available (no heuristic fallback).
    
    Args:
        params: Step parameters dict with section -> params structure
        lattice_matrix: Optional 3x3 lattice vectors in Angstrom (required for strict matching)
        base_ecutwfc: Optional base ecutwfc from pseudos (required for strict matching)
        base_ecutrho: Optional base ecutrho from pseudos (required for strict matching)
        
    Returns:
        Detected PrecisionOption or CUSTOM if context not available
    """
    from quantumvitas.presets.spaces_registry import detect_dimension
    
    return detect_dimension(
        "precision",
        params,
        lattice_matrix=lattice_matrix,
        base_ecutwfc=base_ecutwfc,
        base_ecutrho=base_ecutrho,
    )


# Legacy function removed - use detect_precision() with ParamSpace instead


def _detect_dimension(
    params: Dict[str, Dict[str, Any]],
    dimension: str,
) -> Union[MagnetismOption, OccupationsSchemeOption, PrecisionOption]:
    """
    Detect a single dimension value from step parameters.
    
    Uses registry-based detection (ParamSpace-only approach).
    
    Args:
        params: Step parameters dict
        dimension: Dimension name (magnetism, occupations_scheme, precision)
        
    Returns:
        Detected value for the dimension
        
    Raises:
        ValueError: If dimension is not recognized
    """
    from quantumvitas.presets.spaces_registry import detect_dimension as registry_detect
    
    # Use registry-based detection (ParamSpace-only)
    return registry_detect(dimension, params)


def detect_dimension_from_steps(
    steps: List[Dict[str, Dict[str, Any]]],
    dimension: str,
    *,
    step_types: Optional[List[str]] = None,
    calculation_dir: Optional[Path] = None,
) -> Union[MagnetismOption, OccupationsSchemeOption, PrecisionOption, _CustomType]:
    """
    Detect a preset dimension value aggregated across multiple steps using variants.
    
    Per Constitution 10.5.1:
    - If all steps have the same value → return that value
    - If steps have different values → return CUSTOM
    - Single step is valid (returns its value, not CUSTOM)
    - Steps without a variant for this dimension are skipped (dimension is N/A)
    
    Uses variants registry to determine which steps are relevant.
    
    Args:
        steps: List of step parameters dicts
        dimension: Dimension name to detect
        step_types: Optional list of step_type strings (one per step)
        calculation_dir: Optional calculation directory (for precision context)
        
    Returns:
        Detected value or CUSTOM if heterogeneous
    """
    from quantumvitas.presets.variants_registry import (
        get_variant,
        detect_dimension_for_step,
    )
    
    if not steps:
        # No steps - return default for this dimension
        if dimension == DIMENSION_MAGNETISM:
            return MagnetismOption.NONMAGNETIC
        elif dimension == DIMENSION_OCCUPATIONS_SCHEME:
            return OccupationsSchemeOption.FIXED
        elif dimension == DIMENSION_PRECISION:
            return CUSTOM  # Precision requires context, cannot default
        else:
            return CUSTOM
    
    # If step_types not provided, try to detect without variants (legacy path)
    if step_types is None or len(step_types) != len(steps):
        # Fallback to old logic for backward compatibility during transition
        values = set()
        for step_params in steps:
            value = _detect_dimension(step_params, dimension)
            values.add(value)
        
        if len(values) == 1:
            return values.pop()
        else:
            return CUSTOM
    
    # Use variants-based detection
    values = []
    for step_params, step_type_gen in zip(steps, step_types):
        # Check if variant applies
        variant = get_variant(dimension, step_type_gen)
        if variant is None:
            # No variant applies - skip this step (dimension is N/A for this step)
            continue
        
        # Build context for precision
        precision_context = None
        if dimension == DIMENSION_PRECISION and calculation_dir:
            try:
                from quantumvitas.presets.precision_context import resolve_precision_context
                from quantumvitas.presets.precision import aggregate_cutoffs
                context = resolve_precision_context(calculation_dir)
                if context.structure:
                    # Compute base cutoffs from pseudos
                    base_ecutwfc, base_ecutrho = aggregate_cutoffs(
                        context.species_map, context.pseudo_index
                    )
                    precision_context = {
                        "lattice_matrix": context.lattice_matrix,
                        "base_ecutwfc": base_ecutwfc,
                        "base_ecutrho": base_ecutrho,
                    }
            except Exception:
                # Context resolution failed - cannot detect precision for this step
                continue
        
        # Detect using variant
        detected = detect_dimension_for_step(
            dimension,
            step_type_gen,
            step_params,
            precision_context=precision_context,
        )
        
        if detected is not None:
            values.append(detected)
    
    # If no steps had applicable variants, return CUSTOM
    if not values:
        return CUSTOM
    
    # Per Constitution 10.5.1: single unique value or Custom
    unique_values = set(values)
    if len(unique_values) == 1:
        return unique_values.pop()
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
    
    for step_params, step_type_gen in zip(steps, step_types):
        spec = get_precision_receiver_spec(step_type_gen)
        
        # Non-receiver steps are wildcards (don't contribute)
        if not spec or not spec.accepts_any:
            continue
        
        # Use variants API for detection
        precision_context = {
            "lattice_matrix": lattice_matrix,
            "base_ecutwfc": base_ecutwfc,
            "base_ecutrho": base_ecutrho,
        }
        from quantumvitas.presets.variants_registry import detect_dimension_for_step
        detected = detect_dimension_for_step(
            "precision",
            step_type_gen,
            step_params,
            precision_context=precision_context,
        )
        
        # Convert CUSTOM/None to None for strict detection
        if detected is None or detected == CUSTOM:
            detected = None
        
        if detected is None:
            # Step doesn't match any precision level
            return CUSTOM
        
        receiver_values.append(detected)
    
    # If no receiver steps, return CUSTOM (no default fallback)
    if not receiver_values:
        return CUSTOM
    
    # Check if all receiver steps agree
    unique_values = set(receiver_values)
    if len(unique_values) == 1:
        return unique_values.pop()
    else:
        return CUSTOM


def detect_precision_strict_for_step_type(
    params: Dict[str, Dict[str, Any]],
    step_type_gen: str,
    lattice_matrix: List[List[float]],
    base_ecutwfc: float,
    base_ecutrho: float,
) -> Optional[PrecisionOption]:
    """
    Detect precision with strict matching for a specific step type using variants API.
    
    This is a convenience wrapper around detect_dimension_for_step for precision.
    
    Args:
        params: Step parameters dict
        step_type_gen: Step type gen string
        lattice_matrix: 3x3 lattice vectors in Angstrom
        base_ecutwfc: Base ecutwfc from pseudos
        base_ecutrho: Base ecutrho from pseudos
        
    Returns:
        PrecisionOption if matches, None otherwise
    """
    from quantumvitas.presets.variants_registry import detect_dimension_for_step
    
    # Build precision context
    precision_context = {
        "lattice_matrix": lattice_matrix,
        "base_ecutwfc": base_ecutwfc,
        "base_ecutrho": base_ecutrho,
    }
    
    # Use variants API
    detected = detect_dimension_for_step(
        "precision",
        step_type_gen,
        params,
        precision_context=precision_context,
    )
    
    # Return None if CUSTOM or None (no match)
    if detected is None or detected == CUSTOM:
        return None
    
    return detected


def _match_precision_without_kpoints(
    params: Dict[str, Dict[str, Any]],
    canonical_values: Dict[str, Any],
) -> Optional[str]:
    """
    Match precision profile without requiring K_POINTS (for steps that don't accept kmesh).
    
    Only matches on ecutwfc, ecutrho, and conv_thr.
    """
    from quantumvitas.presets.paramspace import get_precision_paramspace, get_yaml_value
    
    paramspace = get_precision_paramspace()
    
    # Extract actual values from YAML
    ecutwfc_present, ecutwfc_raw = get_yaml_value(params, "SYSTEM", "ecutwfc")
    ecutrho_present, ecutrho_raw = get_yaml_value(params, "SYSTEM", "ecutrho")
    conv_thr_present, conv_thr_raw = get_yaml_value(params, "ELECTRONS", "conv_thr")
    
    # All essential params (except K_POINTS) must be present
    if not (ecutwfc_present and ecutrho_present and conv_thr_present):
        return None
    
    # Parse actual values
    key_ecutwfc = paramspace.keys[0]
    key_ecutrho = paramspace.keys[1]
    key_conv_thr = paramspace.keys[2]
    
    actual_ecutwfc = key_ecutwfc.parser(ecutwfc_raw)
    actual_ecutrho = key_ecutrho.parser(ecutrho_raw)
    actual_conv_thr = key_conv_thr.parser(conv_thr_raw)
    
    # Compare with canonical values
    canonical_ecutwfc = canonical_values["ecutwfc"]
    canonical_ecutrho = canonical_values["ecutrho"]
    canonical_conv_thr = canonical_values["conv_thr"]
    
    # Check cutoffs (exact integer match)
    if actual_ecutwfc != canonical_ecutwfc:
        return None
    if actual_ecutrho != canonical_ecutrho:
        return None
    
    # Check conv_thr (with tolerance)
    if not key_conv_thr.matches(actual_conv_thr, canonical_conv_thr):
        return None
    
    # All checks passed - return the profile name from canonical_values
    return canonical_values.get("profile_name")


def detect_all_presets(
    steps: list[dict[str, dict[str, Any]]],
    *,
    include_precision: bool = True,
    step_types: Optional[list[str]] = None,
    calculation_dir: Optional[Path] = None,
) -> dict[str, Union[MagnetismOption, OccupationsSchemeOption, PrecisionOption, _CustomType]]:
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
        {"magnetism": MagnetismOption.COLLINEAR_LSDA, "occupations_scheme": OccupationsSchemeOption.FIXED, "precision": PrecisionOption.MED}
    """
    from pathlib import Path
    
    dimensions = V1_DIMENSIONS if include_precision else V0_DIMENSIONS
    result = {}
    for dimension in dimensions:
        # For precision, if step_types/calculation_dir not provided, return CUSTOM
        # (cannot do strict detection without context, and simple detection is unreliable)
        if dimension == DIMENSION_PRECISION and (not step_types or not calculation_dir):
            result[dimension] = CUSTOM
        else:
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
) -> Dict[str, Union[MagnetismOption, OccupationsSchemeOption, PrecisionOption, _CustomType]]:
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

