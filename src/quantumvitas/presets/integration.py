"""
Preset integration with QMatSuite calculation infrastructure.

This module connects the preset detection and compilation system
to the calculation layer, enabling:
- Detection of presets from a calculation's steps
- Application of presets to existing steps
- Creation of steps with preset options

Per Constitution Chapter 10:
- §10.1.1: step.yml remains sole executable truth
- §10.2.1: Presets are runtime-only, never persisted
- §10.4.1: Detector B is sole legitimate state source
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

from quantumvitas.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    PrecisionOption,
    ConvergenceOption,
    CUSTOM,
    DIMENSION_MAGNETISM,
    DIMENSION_OCCUPATIONS_SCHEME,
    DIMENSION_PRECISION,
    DIMENSION_CONVERGENCE,
    _CustomType,
)
from quantumvitas.presets.detector import detect_all_presets
from quantumvitas.presets.compiler import (
    compile_presets,
    PresetCompilationError,
    _normalize_option,
)
from quantumvitas.presets.oracle import Oracle


def _parse_bool_value(value: Any) -> Optional[bool]:
    """Parse QE boolean value to Python bool."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in (".true.", "true", "t", ".t."):
            return True
        if s in (".false.", "false", "f", ".f."):
            return False
    return None


def _parse_int_value(value: Any) -> Optional[int]:
    """Parse integer value."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _validate_magnetism_physics(system_params: Dict[str, Any]) -> None:
    """
    Validate magnetism physics constraints in final YAML state.
    
    Rules:
    1. If lspinorb=true then noncolin must be true (SOC requires noncollinear)
    2. If noncolin=true then nspin must be either missing or 4 (contradictions invalid)
    3. If noncolin=false and nspin=4, that's a contradiction
    
    Raises:
        PresetCompilationError: If physics constraints are violated
    """
    noncolin = _parse_bool_value(system_params.get("noncolin"))
    lspinorb = _parse_bool_value(system_params.get("lspinorb"))
    nspin = _parse_int_value(system_params.get("nspin"))
    
    # Rule 1: SOC requires noncollinear
    if lspinorb is True and noncolin is not True:
        raise PresetCompilationError(
            "Physics constraint violation: lspinorb=true requires noncolin=true "
            "(spin-orbit coupling requires noncollinear magnetism)"
        )
    
    # Rule 2: noncolin=true with nspin=2 is a contradiction
    if noncolin is True and nspin == 2:
        raise PresetCompilationError(
            "Physics constraint violation: noncolin=true is incompatible with nspin=2. "
            "Noncollinear magnetism requires nspin=4 or nspin to be absent."
        )
    
    # Rule 3: noncolin=false with nspin=4 is a contradiction
    if noncolin is False and nspin == 4:
        raise PresetCompilationError(
            "Physics constraint violation: nspin=4 requires noncolin=true "
            "(nspin=4 implies noncollinear magnetism)"
        )


def _detect_engine_for_calculation(calculation_dir: Path) -> Optional[str]:
    """
    Detect engine from calculation's steps.
    
    Reads step.yaml files and determines the engine from step_type_spec.
    Returns the first engine found, or None if no engine can be determined.
    
    Args:
        calculation_dir: Path to calculation directory
        
    Returns:
        Engine name (e.g., "qe", "pyscf", "orca") or None
    """
    from quantumvitas.presets.capability import resolve_engine_for_step
    
    steps_dir = calculation_dir / "steps"
    if not steps_dir.exists():
        return None
    
    # Try to find engine from any step.yaml file
    for step_file in steps_dir.glob("*.step.yaml"):
        engine = resolve_engine_for_step(step_file)
        if engine:
            return engine
    
    return None


def detect_presets_from_calculation(
    calculation_dir: Path,
    engine_filter: Optional[str] = None,
) -> Dict[str, Union[str, _CustomType]]:
    """
    Detect preset values from a calculation's steps.
    
    This is the primary integration point for UI preset state derivation.
    Per Constitution §10.4.1: Detector B is the sole legitimate source
    for preset/option state.
    
    Args:
        calculation_dir: Path to calculation directory containing
            calculation.yaml and steps/*.step.yaml
        engine_filter: Optional engine name to filter detection.
            If provided, only detect presets in engine.supported_presets.
            
    Returns:
        Dict mapping dimension name to detected value (string) or "Custom"
        Example: {"magnetism": "collinear_lsda", "occupations_scheme": "smearing_gaussian", "precision": "med"}
        
    Note:
        Returns string values for JSON serialization to daemon/GUI.
        Use detect_presets_from_calculation_typed() for enum values.
    """
    # Load step parameters and types from calculation
    step_data = _load_step_parameters_with_types(calculation_dir)
    step_params_list = [params for params, _ in step_data]
    step_types_list = [step_type_gen for _, step_type_gen in step_data]
    
    # Detect presets (with step-type-aware precision detection)
    # Only enable precision detection if we have step_types and calculation_dir
    # AND if calculation.yaml exists AND project root can be found
    # (indicates proper project structure for precision detection)
    enable_precision = False
    if step_types_list and calculation_dir:
        calc_yaml = calculation_dir / "calculation.yaml"
        if calc_yaml.exists():
            # Quick check: try to find project root by walking up from calculation_dir
            # If found, enable precision detection; otherwise skip it (for test compatibility)
            candidate = calculation_dir.parent
            while candidate != candidate.parent:  # Stop at filesystem root
                if (candidate / "project.qv.yml").exists():
                    enable_precision = True
                    break
                candidate = candidate.parent
    
    # If precision context resolution fails, PrecisionContextError will propagate
    # (don't catch it here - let it bubble up to daemon handler)
    detected = detect_all_presets(
        step_params_list,
        step_types_gen=step_types_list if enable_precision else None,
        calculation_dir=calculation_dir if enable_precision else None,
    )
    
    # Filter by engine capability if engine_filter is provided
    if engine_filter:
        from quantumvitas.engine.registry import create_default_registry
        engine_registry = create_default_registry()
        if engine_registry.has(engine_filter):
            engine = engine_registry.get(engine_filter)
            supported_presets = set(engine.supported_presets)
            # Only keep dimensions that are supported by the engine
            detected = {
                dimension: value
                for dimension, value in detected.items()
                if dimension in supported_presets
            }
    
    # Convert to string representation for JSON serialization
    result = {}
    for dimension, value in detected.items():
        if isinstance(value, _CustomType):
            result[dimension] = "Custom"
        elif hasattr(value, "value"):
            # Enum value
            result[dimension] = value.value
        else:
            result[dimension] = str(value)
    
    return result


def detect_presets_from_calculation_typed(
    calculation_dir: Path,
    engine_filter: Optional[str] = None,
) -> Dict[str, Union[MagnetismOption, OccupationsSchemeOption, _CustomType]]:
    """
    Detect preset values from a calculation's steps (typed version).
    
    Same as detect_presets_from_calculation but returns enum values
    instead of strings.
    
    Args:
        calculation_dir: Path to calculation directory
        engine_filter: Optional engine name to filter detection.
            If provided, only detect presets in engine.supported_presets.
        
    Returns:
        Dict mapping dimension name to detected enum value or CUSTOM
    """
    # Use string version and convert back to typed
    string_result = detect_presets_from_calculation(calculation_dir, engine_filter=engine_filter)
    
    # Convert string values back to typed enums
    from quantumvitas.presets.dimensions import (
        MagnetismOption,
        OccupationsSchemeOption,
        PrecisionOption,
        ConvergenceOption,
    )
    
    typed_result = {}
    for dimension, value_str in string_result.items():
        if value_str == "Custom":
            typed_result[dimension] = CUSTOM
        elif dimension == "magnetism":
            try:
                typed_result[dimension] = MagnetismOption(value_str)
            except (ValueError, KeyError):
                typed_result[dimension] = CUSTOM
        elif dimension == "occupations_scheme":
            try:
                typed_result[dimension] = OccupationsSchemeOption(value_str)
            except (ValueError, KeyError):
                typed_result[dimension] = CUSTOM
        elif dimension == "precision":
            try:
                typed_result[dimension] = PrecisionOption(value_str)
            except (ValueError, KeyError):
                typed_result[dimension] = CUSTOM
        elif dimension == "convergence":
            try:
                typed_result[dimension] = ConvergenceOption(value_str)
            except (ValueError, KeyError):
                typed_result[dimension] = CUSTOM
        else:
            typed_result[dimension] = CUSTOM
    
    return typed_result


def _load_step_parameters(
    calculation_dir: Path,
    *,
    receivers_only: bool = True,
) -> List[Dict[str, Dict[str, Any]]]:
    """
    Load parameters from steps in a calculation using StepDoc.
    
    Args:
        calculation_dir: Path to calculation directory
        receivers_only: If True (default), only load parameters from
            preset-receiving steps (pw.x-based). Post-processing steps
            like DOS are excluded from detection to avoid false Custom.
        
    Returns:
        List of step parameter dicts (section -> params)
    """
    from quantumvitas.presets.receivers import is_receiver
    from quantumvitas.core.yamldoc import StepDoc
    
    calculation_dir = Path(calculation_dir).resolve()
    steps_dir = calculation_dir / "steps"
    
    if not steps_dir.exists():
        return []
    
    step_params_list = []
    
    # Find all step.yaml files
    step_files = sorted(steps_dir.glob("*.step.yaml"))
    
    for step_file in step_files:
        try:
            # Load via StepDoc (detector is read-only)
            doc = StepDoc.load(step_file, access_control=True, owner="detector")
            step_type_spec = doc.get(["step_type_spec"], default="scf")

            # Convert SPEC to GEN for receiver registry lookup (receivers use GEN types)
            from quantumvitas.api import get_step_type_gen
            from quantumvitas.workflow.step_type_convert import gen_from
            try:
                step_type_gen = get_step_type_gen(step_type_spec)
            except (KeyError, ValueError):
                # Fallback: use explicit conversion function (handles both SPEC and GEN)
                step_type_gen = gen_from(step_type_spec)  # gen_from() handles both SPEC and GEN inputs

            # Filter to only receiver steps for preset detection
            if receivers_only and not is_receiver(step_type_gen):
                continue
            
            # Export parameters and cards as deep copies (no reference leakage)
            parameters = doc.export_copy(["parameters"]) if doc.has(["parameters"]) else {}
            cards = doc.export_copy(["cards"]) if doc.has(["cards"]) else {}
            
            if parameters or cards:
                # Store both parameters and cards for detector
                # (detector needs cards.K_POINTS for canonical format)
                step_params = dict(parameters)
                if cards:
                    step_params["cards"] = cards
                step_params["_step_type"] = step_type_gen  # Internal metadata for detector
                step_params_list.append(step_params)
        except Exception:
            # Skip malformed step files
            continue
    
    return step_params_list


def _load_step_parameters_with_types(
    calculation_dir: Path,
    *,
    receivers_only: bool = True,
) -> list[tuple[dict[str, dict[str, Any]], str]]:
    """
    Load parameters from steps with step_type information using StepDoc.
    
    Args:
        calculation_dir: Path to calculation directory
        receivers_only: If True (default), only load from receiver steps
        
    Returns:
        List of (params_dict, step_type_gen) tuples where step_type_gen is the GEN type
    """
    from quantumvitas.presets.receivers import is_receiver
    from quantumvitas.core.yamldoc import StepDoc
    
    calculation_dir = Path(calculation_dir).resolve()
    steps_dir = calculation_dir / "steps"
    
    if not steps_dir.exists():
        return []
    
    result = []
    step_files = sorted(steps_dir.glob("*.step.yaml"))
    
    for step_file in step_files:
        try:
            # Load via StepDoc (detector is read-only)
            doc = StepDoc.load(step_file, access_control=True, owner="detector")
            step_type_spec = doc.get(["step_type_spec"], default="scf")

            # Convert SPEC to GEN for receiver registry lookup (receivers use GEN types)
            from quantumvitas.api import get_step_type_gen
            from quantumvitas.workflow.step_type_convert import gen_from
            try:
                step_type_gen = get_step_type_gen(step_type_spec)
            except (KeyError, ValueError):
                # Fallback: use explicit conversion function (handles both SPEC and GEN)
                step_type_gen = gen_from(step_type_spec)  # gen_from() handles both SPEC and GEN inputs

            if receivers_only and not is_receiver(step_type_gen):
                continue
            
            # Export parameters and cards as deep copies (no reference leakage)
            parameters = doc.export_copy(["parameters"]) if doc.has(["parameters"]) else {}
            cards = doc.export_copy(["cards"]) if doc.has(["cards"]) else {}
            
            if parameters or cards:
                # Include both parameters and cards for detector
                step_params = dict(parameters)
                if cards:
                    step_params["cards"] = cards
                result.append((step_params, step_type_gen))
        except Exception:
            continue
    
    return result


# Dimension ownership: which keys belong to which dimension
# DEPRECATED: This is no longer used for deletion decisions.
# Deletions are now driven by profile NOT_APPLICABLE cells and keys that will be written.
# This mapping is kept only for UI display purposes and should be generated from variants.
# TODO: Generate this from variants registry instead of hardcoding.
DIMENSION_OWNED_KEYS: dict[str, dict[str, set[str]]] = {
    DIMENSION_MAGNETISM: {
        "SYSTEM": {"nspin", "noncolin", "lspinorb"},
    },
    DIMENSION_OCCUPATIONS_SCHEME: {
        "SYSTEM": {"occupations", "smearing", "degauss"},
    },
    DIMENSION_PRECISION: {
        "SYSTEM": {"ecutwfc", "ecutrho"},
        "ELECTRONS": {"conv_thr"},
        # NOTE: cards.K_POINTS is NOT included here because it's variant-dependent
        # bandspw variant does NOT own K_POINTS
    },
    DIMENSION_CONVERGENCE: {
        "ELECTRONS": {"mixing_beta", "electron_maxstep", "mixing_mode", "mixing_ndim", "diagonalization"},
        # NOTE: conv_thr is NOT included here (belongs to precision dimension)
    },
}


def apply_presets_to_step(
    step_path: Path,
    options: Dict[str, Any],
    *,
    validate_physics: bool = True,
    precision_advice: Optional[Any] = None,  # PrecisionAdvice object
    precision_lattice_matrix: Optional[List[List[float]]] = None,  # For precision context
) -> Dict[str, Any]:
    """
    Apply preset options to an existing step using variants registry and StepDoc.
    
    Per Constitution §10.3.3: This OVERWRITES preset-related parameters,
    it does NOT merge. Non-preset parameters are preserved.
    
    Uses variants registry to determine which dimensions apply to this step_type_gen.
    Deletions are driven by profile NOT_APPLICABLE cells and keys that will be written.
    
    Uses StepDoc abstraction for mutation containment (no direct dict mutation).
    
    Args:
        step_path: Path to step.yaml file
        options: Preset options dict with dimension keys
        validate_physics: If True, validate physics constraints
        precision_advice: Optional PrecisionAdvice for precision preset
        precision_lattice_matrix: Optional lattice matrix for precision context
        
    Returns:
        Dict with:
            - "content": Updated step content dict
            - "accepted": True if step accepted presets, False if skipped
            - "filtered_options": Options that were actually applied
        
    Raises:
        PresetCompilationError: If invalid option combinations
        FileNotFoundError: If step file doesn't exist
    """
    from quantumvitas.presets.variants_registry import (
        get_variant,
        compile_dimension_patch_for_step,
    )
    from quantumvitas.core.yamldoc import StepDoc
    
    step_path = Path(step_path).resolve()
    
    if not step_path.exists():
        raise FileNotFoundError(f"Step file not found: {step_path}")
    
    # Load step using StepDoc (compiler has write access to parameters/cards)
    doc = StepDoc.load(step_path, access_control=True, owner="compiler")
    
    # Get step_type_gen for variant lookup (map step_type_spec to step_type_gen if needed)
    step_type_spec_from_doc = doc.get(["step_type_spec"], default="scf")
    # Convert SPEC to GEN for variant lookup (presets use step_type_gen)
    from quantumvitas.workflow.step_type_convert import gen_from, is_spec
    if is_spec(step_type_spec_from_doc):
        step_type_gen = gen_from(step_type_spec_from_doc)
    else:
        # Already a GEN type
        step_type_gen = step_type_spec_from_doc
    
    # Resolve engine from step context (for capability validation)
    from quantumvitas.presets.capability import resolve_engine_for_step, require_preset_capability, CapabilityError
    engine_name = resolve_engine_for_step(step_path)
    
    # Build step_yaml structure for compilation (export to avoid mutation)
    step_yaml: Dict[str, Dict[str, Any]] = {}
    if doc.has(["parameters"]):
        step_yaml = doc.export_copy(["parameters"])
    if doc.has(["cards"]):
        step_yaml["cards"] = doc.export_copy(["cards"])
    
    # Track which dimensions are being applied (check variants and capability)
    applied_dimensions = []
    filtered_options = {}
    
    for dimension, option_value in options.items():
        # First check if variant exists (ParamSpace applicability)
        variant = get_variant(dimension, step_type_gen)
        if variant is None:
            continue
        
        # Then validate engine capability (if engine is known)
        if engine_name:
            try:
                require_preset_capability(engine_name, step_type_gen, dimension)
            except CapabilityError as e:
                # Skip this dimension with clear error message
                continue
        
        applied_dimensions.append(dimension)
        filtered_options[dimension] = option_value
    
    # If no dimensions apply, skip
    if not applied_dimensions:
        return {
            "content": doc.to_dict(),
            "accepted": False,
            "filtered_options": {},
            "updated_fields": [],
            "skipped_fields": ["no variant applies to this step_type_gen"],
        }
    
    # Per ParamSpace Constitution v1: Apply must be executed in phases
    # Phase 1: Prerequisite ParamSpaces (occupations_scheme, step_type_gen, etc.)
    # Phase 2: Dependent ParamSpaces (precision)
    prerequisite_dimensions = [
        d for d in applied_dimensions 
        if d in (DIMENSION_OCCUPATIONS_SCHEME, DIMENSION_MAGNETISM)
    ]
    dependent_dimensions = [
        d for d in applied_dimensions 
        if d in (DIMENSION_PRECISION, DIMENSION_CONVERGENCE)
    ]
    
    # Build unified patch for apply_patch (uses None for deletions)
    unified_patch: Dict[str, Dict[str, Any]] = {
        "parameters": {
            "SYSTEM": {},
            "ELECTRONS": {},
        },
        "cards": {},
    }
    all_deletions: set[Tuple[str, str]] = set()  # (section, key) tuples
    
    # Phase 1: Prerequisite dimensions (occupations_scheme, magnetism)
    for dimension in prerequisite_dimensions:
        # Normalize option
        if dimension == DIMENSION_MAGNETISM:
            option_enum = _normalize_option(filtered_options[dimension], MagnetismOption, MagnetismOption.NONMAGNETIC)
        elif dimension == DIMENSION_OCCUPATIONS_SCHEME:
            option_enum = _normalize_option(
                filtered_options[dimension],
                OccupationsSchemeOption,
                OccupationsSchemeOption.FIXED,
            )
        else:
            continue
        
        # Build precision context if needed (not needed for prerequisite dimensions)
        precision_context = None
        
        # Compile using variant
        patch, deletions = compile_dimension_patch_for_step(
            dimension,
            option_enum,
            step_type_gen,
            step_yaml,
            explicit_defaults=True,
            precision_context=precision_context,
        )
        
        # Merge patch into unified_patch
        if "SYSTEM" in patch:
            unified_patch["parameters"]["SYSTEM"].update(patch["SYSTEM"])
        if "ELECTRONS" in patch:
            unified_patch["parameters"]["ELECTRONS"].update(patch["ELECTRONS"])
        if "cards" in patch:
            unified_patch["cards"].update(patch["cards"])
        
        # Collect deletions
        all_deletions.update(deletions)
    
    # Apply Phase 1 patches to step_yaml (for oracle to read latest state in Phase 2)
    if "SYSTEM" not in step_yaml:
        step_yaml["SYSTEM"] = {}
    if "ELECTRONS" not in step_yaml:
        step_yaml["ELECTRONS"] = {}
    if "cards" not in step_yaml:
        step_yaml["cards"] = {}
    
    if "parameters" in unified_patch:
        if "SYSTEM" in unified_patch["parameters"]:
            step_yaml["SYSTEM"].update(unified_patch["parameters"]["SYSTEM"])
        if "ELECTRONS" in unified_patch["parameters"]:
            step_yaml["ELECTRONS"].update(unified_patch["parameters"]["ELECTRONS"])
    if "cards" in unified_patch:
        step_yaml["cards"].update(unified_patch["cards"])
    
    # Phase 2: Dependent dimensions (precision, convergence)
    for dimension in dependent_dimensions:
        # Normalize option
        if dimension == DIMENSION_PRECISION:
            option_enum = _normalize_option(filtered_options[dimension], PrecisionOption, PrecisionOption.MED)
        elif dimension == DIMENSION_CONVERGENCE:
            option_enum = _normalize_option(filtered_options[dimension], ConvergenceOption, ConvergenceOption.NORMAL)
        else:
            continue
        
        # Build precision context if needed
        precision_context = None
        if dimension == DIMENSION_PRECISION and precision_advice is not None:
            # Check if variant requires lattice_matrix (if it includes K_POINTS)
            variant = get_variant(dimension, step_type_gen)
            has_kpoints_key = False
            if variant is not None:
                has_kpoints_key = any(
                    key.section == "cards" and key.key == "K_POINTS"
                    for key in variant.space.keys
                )
            
            # Only require lattice_matrix if variant includes K_POINTS
            if has_kpoints_key:
                if precision_lattice_matrix is None:
                    # Try to infer from step_path (look for calculation.yaml)
                    calc_dir = step_path.parent.parent
                    calc_yaml = calc_dir / "calculation.yaml"
                    if calc_yaml.exists():
                        try:
                            from quantumvitas.presets.precision_context import resolve_precision_context
                            context = resolve_precision_context(calc_dir)
                            if context.structure:
                                precision_lattice_matrix = [list(vec) for vec in context.structure.lattice.matrix]
                        except Exception:
                            pass
                
                if precision_lattice_matrix is None:
                    from quantumvitas.presets.compiler import PresetCompilationError
                    raise PresetCompilationError(
                        f"precision_lattice_matrix is required for precision preset application to {step_type_gen}. "
                        f"Pass it explicitly or ensure calculation.yaml and structure are available."
                    )
            
            # Get base cutoffs from advice
            base_ecutwfc = precision_advice.base_ecutwfc
            base_ecutrho = precision_advice.base_ecutrho
            
            # If base values not available, approximate from final values and multiplier
            if base_ecutwfc is None or base_ecutrho is None:
                from quantumvitas.presets.precision import PRECISION_CONSTANTS
                constants = PRECISION_CONSTANTS[option_enum]
                if base_ecutwfc is None:
                    base_ecutwfc = precision_advice.ecutwfc / constants.cutoff_multiplier
                if base_ecutrho is None:
                    base_ecutrho = precision_advice.ecutrho / constants.cutoff_multiplier
            
            precision_context = {
                "base_ecutwfc": base_ecutwfc,
                "base_ecutrho": base_ecutrho,
            }
            
            # Only add lattice_matrix if variant requires it
            if has_kpoints_key and precision_lattice_matrix is not None:
                precision_context["lattice_matrix"] = precision_lattice_matrix
        
        # Compile using variant
        patch, deletions = compile_dimension_patch_for_step(
            dimension,
            option_enum,
            step_type_gen,
            step_yaml,
            explicit_defaults=True,
            precision_context=precision_context,
        )
        
        # Merge patch into unified_patch
        if "SYSTEM" in patch:
            unified_patch["parameters"]["SYSTEM"].update(patch["SYSTEM"])
        if "ELECTRONS" in patch:
            unified_patch["parameters"]["ELECTRONS"].update(patch["ELECTRONS"])
        if "cards" in patch:
            unified_patch["cards"].update(patch["cards"])
        
        # Collect deletions
        all_deletions.update(deletions)
    
    # Convert deletions to None values in patch (Delete Semantics A)
    for section, key in all_deletions:
        if section == "SYSTEM":
            unified_patch["parameters"]["SYSTEM"][key] = None
        elif section == "ELECTRONS":
            unified_patch["parameters"]["ELECTRONS"][key] = None
        elif section == "cards":
            unified_patch["cards"][key] = None
    
    # Per ParamSpace Constitution v1: Apply invariants unconditionally
    # Build current YAML state for oracle (must be mutable dict for invariant enforcement)
    # Start with existing state from doc, then apply unified_patch to get final state
    current_yaml_state: Dict[str, Dict[str, Any]] = {
        "SYSTEM": {},
        "ELECTRONS": {},
        "cards": {},
    }
    if doc.has(["parameters", "SYSTEM"]):
        current_yaml_state["SYSTEM"] = dict(doc.export_copy(["parameters", "SYSTEM"]))
    if doc.has(["parameters", "ELECTRONS"]):
        current_yaml_state["ELECTRONS"] = dict(doc.export_copy(["parameters", "ELECTRONS"]))
    if doc.has(["cards"]):
        current_yaml_state["cards"] = dict(doc.export_copy(["cards"]))
    
    # Apply unified_patch to current_yaml_state (for oracle to read final state)
    if "parameters" in unified_patch:
        if "SYSTEM" in unified_patch["parameters"]:
            for key, value in unified_patch["parameters"]["SYSTEM"].items():
                if value is None:
                    current_yaml_state["SYSTEM"].pop(key, None)
                else:
                    current_yaml_state["SYSTEM"][key] = value
        if "ELECTRONS" in unified_patch["parameters"]:
            for key, value in unified_patch["parameters"]["ELECTRONS"].items():
                if value is None:
                    current_yaml_state["ELECTRONS"].pop(key, None)
                else:
                    current_yaml_state["ELECTRONS"][key] = value
    if "cards" in unified_patch:
        for key, value in unified_patch["cards"].items():
            if value is None:
                current_yaml_state["cards"].pop(key, None)
            else:
                current_yaml_state["cards"][key] = value
    
    oracle = Oracle(current_yaml_state)
    
    # Apply invariants for all ParamSpaces (even if not being applied)
    # This ensures invariant enforcement runs even when CUSTOM
    # Per Constitution v1 §2: Custom Apply (Invariant Enforcement) always runs
    from quantumvitas.presets.spaces_registry import SPACES
    for dimension_name, paramspace in SPACES.items():
        paramspace.apply_invariants(current_yaml_state, oracle)
    
    # Update unified_patch from current_yaml_state (invariants may have mutated it)
    # Compare with original to find what changed
    original_system = {}
    original_electrons = {}
    original_cards = {}
    if doc.has(["parameters", "SYSTEM"]):
        original_system = doc.export_copy(["parameters", "SYSTEM"])
    if doc.has(["parameters", "ELECTRONS"]):
        original_electrons = doc.export_copy(["parameters", "ELECTRONS"])
    if doc.has(["cards"]):
        original_cards = doc.export_copy(["cards"])
    
    # Update unified_patch with invariant-enforced values
    # Ensure sections exist in unified_patch
    if "parameters" not in unified_patch:
        unified_patch["parameters"] = {}
    if "SYSTEM" not in unified_patch["parameters"]:
        unified_patch["parameters"]["SYSTEM"] = {}
    if "ELECTRONS" not in unified_patch["parameters"]:
        unified_patch["parameters"]["ELECTRONS"] = {}
    if "cards" not in unified_patch:
        unified_patch["cards"] = {}
    
    # Update SYSTEM: add new/modified values, mark deleted values as None
    for key in set(list(original_system.keys()) + list(current_yaml_state["SYSTEM"].keys())):
        if key in current_yaml_state["SYSTEM"]:
            # Key exists in current state
            if key not in original_system or original_system[key] != current_yaml_state["SYSTEM"][key]:
                unified_patch["parameters"]["SYSTEM"][key] = current_yaml_state["SYSTEM"][key]
        else:
            # Key was deleted (exists in original but not in current)
            if key in original_system:
                unified_patch["parameters"]["SYSTEM"][key] = None
    
    # Update ELECTRONS: add new/modified values, mark deleted values as None
    for key in set(list(original_electrons.keys()) + list(current_yaml_state["ELECTRONS"].keys())):
        if key in current_yaml_state["ELECTRONS"]:
            # Key exists in current state
            if key not in original_electrons or original_electrons[key] != current_yaml_state["ELECTRONS"][key]:
                unified_patch["parameters"]["ELECTRONS"][key] = current_yaml_state["ELECTRONS"][key]
        else:
            # Key was deleted (exists in original but not in current)
            if key in original_electrons:
                unified_patch["parameters"]["ELECTRONS"][key] = None
    
    # Update cards: add new/modified values, mark deleted values as None
    for key in set(list(original_cards.keys()) + list(current_yaml_state["cards"].keys())):
        if key in current_yaml_state["cards"]:
            # Key exists in current state
            if key not in original_cards or original_cards[key] != current_yaml_state["cards"][key]:
                unified_patch["cards"][key] = current_yaml_state["cards"][key]
        else:
            # Key was deleted (exists in original but not in current)
            if key in original_cards:
                unified_patch["cards"][key] = None
    
    # Physics validation before applying
    if validate_physics:
        merged_system = {}
        if doc.has(["parameters", "SYSTEM"]):
            merged_system = doc.export_copy(["parameters", "SYSTEM"])
        # Apply updates
        for key, value in unified_patch["parameters"]["SYSTEM"].items():
            if value is None:
                merged_system.pop(key, None)
            else:
                merged_system[key] = value
        _validate_magnetism_physics(merged_system)
    
    # Apply unified patch via StepDoc (uses apply_patch with None = delete)
    # Clean up empty sections before applying
    if not unified_patch["parameters"]["SYSTEM"]:
        del unified_patch["parameters"]["SYSTEM"]
    if not unified_patch["parameters"]["ELECTRONS"]:
        del unified_patch["parameters"]["ELECTRONS"]
    if not unified_patch["parameters"]:
        del unified_patch["parameters"]
    if not unified_patch["cards"]:
        del unified_patch["cards"]
    
    if unified_patch:
        # Serialize IR patch to engine format before writing to step.yaml
        # step.yaml stores YAML native booleans (true/false), not QE strings
        # Get original step_type_spec (before step_type_gen mapping) to determine engine
        original_step_type_spec = doc.get(["step_type_spec"], default="scf")
        # In v0, all steps are QE, but we check for future extensibility
        # For now, assume QE backend
        from quantumvitas.ir.backends.qe.mapping import ir_params_to_qe_params
        qe_patch = ir_params_to_qe_params(unified_patch)
        doc.apply_patch(qe_patch)
    
    # Save via StepDoc (single commit point)
    doc.save(step_path)
    
    # Build updated_fields from the patch
    updated_fields = []
    params_patch = unified_patch.get("parameters", {})
    if "SYSTEM" in params_patch:
        updated_fields.extend([k for k, v in params_patch["SYSTEM"].items() if v is not None])
    if "ELECTRONS" in params_patch:
        updated_fields.extend([f"ELECTRONS.{k}" for k, v in params_patch["ELECTRONS"].items() if v is not None])
    cards_patch = unified_patch.get("cards", {})
    if cards_patch:
        updated_fields.extend([f"cards.{k}" for k, v in cards_patch.items() if v is not None])
    
    return {
        "content": doc.to_dict(),
        "accepted": True,
        "filtered_options": filtered_options,
        "updated_fields": updated_fields,
        "skipped_fields": [],
    }


def get_step_preset_params(step_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Get the preset-related parameters from a step using StepDoc.
    
    Args:
        step_path: Path to step.yaml file
        
    Returns:
        Dict with SYSTEM, ELECTRONS, K_POINTS -> preset params
    """
    from quantumvitas.core.yamldoc import StepDoc
    
    step_path = Path(step_path).resolve()
    
    if not step_path.exists():
        return {}
    
    # Load via StepDoc (read-only access)
    try:
        doc = StepDoc.load(step_path, access_control=True, owner="detector")
    except Exception:
        return {}
    
    # Extract preset-related params using export_copy (no reference leakage)
    system = doc.export_copy(["parameters", "SYSTEM"]) if doc.has(["parameters", "SYSTEM"]) else {}
    electrons = doc.export_copy(["parameters", "ELECTRONS"]) if doc.has(["parameters", "ELECTRONS"]) else {}
    
    # QE kpoints are represented as cards.K_POINTS only
    kpoints = doc.export_copy(["cards", "K_POINTS"]) if doc.has(["cards", "K_POINTS"]) else {}
    
    # Extract only preset-related params
    SYSTEM_PRESET_PARAMS = {
        "nspin", "noncolin", "lspinorb",
        "occupations", "smearing", "degauss",
        "ecutwfc", "ecutrho",  # Precision
    }
    
    ELECTRONS_PRESET_PARAMS = {
        "conv_thr",  # Precision
    }
    
    result = {}
    
    preset_system = {k: v for k, v in system.items() if k.lower() in SYSTEM_PRESET_PARAMS}
    if preset_system:
        result["SYSTEM"] = preset_system
    
    preset_electrons = {k: v for k, v in electrons.items() if k.lower() in ELECTRONS_PRESET_PARAMS}
    if preset_electrons:
        result["ELECTRONS"] = preset_electrons
    
    # Include K_POINTS if present
    if kpoints:
        result["K_POINTS"] = kpoints
    
    return result


def get_step_preset_footprints(calculation_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Get preset-related parameter footprints for all steps in a calculation using StepDoc.
    
    Returns a dict mapping step file name (without path) to its preset params.
    This enables UI to show parameter summary on each step row.
    
    Args:
        calculation_dir: Path to calculation directory
        
    Returns:
        Dict mapping step_file name to footprint data:
        {
            "1_scf.step.yaml": {
                "params": {"nspin": 2, "occupations": "smearing", "ecutwfc": 60.0, ...},
                "magnetism": "collinear_lsda",
                "occupations_scheme": "smearing_gaussian",
                "precision": "med"
            },
            ...
        }
    """
    from quantumvitas.presets.detector import (
        detect_magnetism, detect_occupations_scheme, detect_precision
    )
    from quantumvitas.core.yamldoc import StepDoc
    
    calculation_dir = Path(calculation_dir).resolve()
    steps_dir = calculation_dir / "steps"
    
    if not steps_dir.exists():
        return {}
    
    footprints = {}
    
    # Find all step.yaml files
    step_files = sorted(steps_dir.glob("*.step.yaml"))
    
    for step_file in step_files:
        try:
            # Load via StepDoc (read-only access)
            doc = StepDoc.load(step_file, access_control=True, owner="detector")
            
            # Export parameters and cards as deep copies (no reference leakage)
            parameters = doc.export_copy(["parameters"]) if doc.has(["parameters"]) else {}
            cards = doc.export_copy(["cards"]) if doc.has(["cards"]) else {}
            system = parameters.get("SYSTEM", {})
            electrons = parameters.get("ELECTRONS", {})
            
            # QE kpoints are represented as cards.K_POINTS only
            kpoints = cards.get("K_POINTS", {})
            
            # Extract preset-related params (for UI display)
            SYSTEM_PRESET_PARAMS = {
                "nspin", "noncolin", "lspinorb",
                "occupations", "smearing", "degauss",
                "ecutwfc", "ecutrho",  # Precision
            }
            
            ELECTRONS_PRESET_PARAMS = {
                "conv_thr",  # Precision
            }
            
            preset_params = {}
            for k, v in system.items():
                if k.lower() in SYSTEM_PRESET_PARAMS:
                    preset_params[k] = v
            for k, v in electrons.items():
                if k.lower() in ELECTRONS_PRESET_PARAMS:
                    preset_params[k] = v
            
            # Add k-mesh summary if present
            # QE kpoints are represented as cards.K_POINTS = {"option": "automatic", "data": [[nk1, nk2, nk3, ...]]}
            if isinstance(kpoints, dict) and "data" in kpoints and kpoints.get("option", "").lower() == "automatic":
                data = kpoints.get("data", [])
                if data and isinstance(data, list) and len(data) > 0:
                    mesh_row = data[0]
                    if isinstance(mesh_row, (list, tuple)) and len(mesh_row) >= 3:
                        preset_params["kmesh"] = f"{mesh_row[0]}×{mesh_row[1]}×{mesh_row[2]}"
            
            # Format ecutwfc/ecutrho for display (round to integer)
            if "ecutwfc" in preset_params:
                try:
                    preset_params["ecutwfc"] = round(float(preset_params["ecutwfc"]))
                except (ValueError, TypeError):
                    pass
            if "ecutrho" in preset_params:
                try:
                    preset_params["ecutrho"] = round(float(preset_params["ecutrho"]))
                except (ValueError, TypeError):
                    pass
            
            # Detect preset values for this step
            magnetism_val = detect_magnetism(parameters)
            occupations_scheme_val = detect_occupations_scheme(parameters)
            # Precision requires context - without it, returns CUSTOM
            precision_val = detect_precision(parameters)
            
            footprint = {
                "params": preset_params,
                "magnetism": magnetism_val.value if hasattr(magnetism_val, 'value') else str(magnetism_val),
                "occupations_scheme": occupations_scheme_val.value if hasattr(occupations_scheme_val, 'value') else str(occupations_scheme_val),
                "precision": precision_val.value if hasattr(precision_val, 'value') else str(precision_val),
            }
            
            footprints[step_file.name] = footprint
            
        except Exception:
            # Skip malformed step files
            continue
    
    return footprints


def detect_workflow_type(calculation_dir: Path) -> str:
    """
    Detect the workflow type from a calculation's step sequence using YamlDoc.
    
    This is informational only - does NOT affect execution.
    Per Constitution: workflow is runtime interpretation only.
    
    Args:
        calculation_dir: Path to calculation directory
        
    Returns:
        Detected workflow type string:
        - "SCF" - single SCF calculation
        - "DOS" - SCF + NSCF + DOS
        - "BandStructure" - SCF + bands calculation
        - "Relaxation" - relax or vc-relax
        - "Phonon" - includes PH step
        - "MD" - molecular dynamics
        - "Unknown" - unrecognized pattern
    """
    from quantumvitas.core.yamldoc import CalcDoc, StepDoc
    
    calculation_dir = Path(calculation_dir).resolve()
    
    # Load calculation.yaml to get step info
    calc_yaml = calculation_dir / "calculation.yaml"
    if not calc_yaml.exists():
        return "Unknown"
    
    try:
        calc_doc = CalcDoc.load(calc_yaml)
        steps = calc_doc.export_copy(["steps"]) if calc_doc.has(["steps"]) else []
    except Exception:
        return "Unknown"
    
    # Collect step types (as GEN types for workflow matching)
    from quantumvitas.workflow.registry import get_registry
    registry = get_registry()

    step_types = set()
    for step_entry in steps:
        # Get step type from step_type_spec field (authoritative for step types)
        step_type_spec = step_entry.get("step_type_spec")
        if not step_type_spec:
            # Load from step file
            step_file = step_entry.get("step_file")
            if step_file:
                step_path = calculation_dir / step_file
                if step_path.exists():
                    try:
                        step_doc = StepDoc.load(step_path, access_control=True, owner="detector")
                        step_type_spec = step_doc.get(["step_type_spec"], default=None)
                    except Exception:
                        pass

        if step_type_spec:
            # ALWAYS use converter to get GEN type - gen_from handles both SPEC and GEN inputs
            from quantumvitas.workflow.step_type_convert import gen_from
            step_type_gen = gen_from(step_type_spec)
            step_types.add(step_type_gen.lower())
    
    # Workflow detection rules (order matters - more specific first)
    # VC is a parameter, not a separate gen step
    if "md" in step_types:
        return "MD"
    
    if "relax" in step_types:
        return "Relaxation"
    
    if "ph" in step_types:
        return "Phonon"
    
    if "dos" in step_types:
        return "DOS"
    
    if "bands" in step_types or "bandspw" in step_types:
        return "BandStructure"
    
    if "scf" in step_types and len(step_types) == 1:
        return "SCF"
    
    if "nscf" in step_types:
        # NSCF without DOS or bands is unusual
        return "NSCF"
    
    return "Unknown"

