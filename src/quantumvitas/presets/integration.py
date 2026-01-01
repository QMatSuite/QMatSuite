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
    CUSTOM,
    DIMENSION_MAGNETISM,
    DIMENSION_OCCUPATIONS_SCHEME,
    DIMENSION_PRECISION,
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


def detect_presets_from_calculation(
    calculation_dir: Path,
) -> Dict[str, Union[str, _CustomType]]:
    """
    Detect preset values from a calculation's steps.
    
    This is the primary integration point for UI preset state derivation.
    Per Constitution §10.4.1: Detector B is the sole legitimate source
    for preset/option state.
    
    Args:
        calculation_dir: Path to calculation directory containing
            calculation.yaml and steps/*.step.yaml
            
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
    step_types_list = [step_type for _, step_type in step_data]
    
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
        step_types=step_types_list if enable_precision else None,
        calculation_dir=calculation_dir if enable_precision else None,
    )
    
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
) -> Dict[str, Union[MagnetismOption, OccupationsSchemeOption, _CustomType]]:
    """
    Detect preset values from a calculation's steps (typed version).
    
    Same as detect_presets_from_calculation but returns enum values
    instead of strings.
    
    Args:
        calculation_dir: Path to calculation directory
        
    Returns:
        Dict mapping dimension name to detected enum value or CUSTOM
    """
    step_params_list = _load_step_parameters(calculation_dir)
    return detect_all_presets(step_params_list)


def _load_step_parameters(
    calculation_dir: Path,
    *,
    receivers_only: bool = True,
) -> List[Dict[str, Dict[str, Any]]]:
    """
    Load parameters from steps in a calculation.
    
    Args:
        calculation_dir: Path to calculation directory
        receivers_only: If True (default), only load parameters from
            preset-receiving steps (pw.x-based). Post-processing steps
            like DOS are excluded from detection to avoid false Custom.
        
    Returns:
        List of step parameter dicts (section -> params)
    """
    from quantumvitas.presets.receivers import is_receiver
    
    calculation_dir = Path(calculation_dir).resolve()
    steps_dir = calculation_dir / "steps"
    
    if not steps_dir.exists():
        return []
    
    step_params_list = []
    
    # Find all step.yaml files
    step_files = sorted(steps_dir.glob("*.step.yaml"))
    
    for step_file in step_files:
        try:
            content = yaml.safe_load(step_file.read_text()) or {}
            step_type = content.get("step_type", "scf")
            
            # Filter to only receiver steps for preset detection
            if receivers_only and not is_receiver(step_type):
                continue
            
            parameters = content.get("parameters", {})
            cards = content.get("cards", {})
            if parameters or cards:
                # Store both parameters and cards for detector
                # (detector needs cards.K_POINTS for canonical format)
                step_params = dict(parameters)
                if cards:
                    step_params["cards"] = cards
                step_params["_step_type"] = step_type  # Internal metadata for detector
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
    Load parameters from steps with step_type information.
    
    Args:
        calculation_dir: Path to calculation directory
        receivers_only: If True (default), only load from receiver steps
        
    Returns:
        List of (params_dict, step_type) tuples
    """
    from quantumvitas.presets.receivers import is_receiver
    
    calculation_dir = Path(calculation_dir).resolve()
    steps_dir = calculation_dir / "steps"
    
    if not steps_dir.exists():
        return []
    
    result = []
    step_files = sorted(steps_dir.glob("*.step.yaml"))
    
    for step_file in step_files:
        try:
            content = yaml.safe_load(step_file.read_text()) or {}
            step_type = content.get("step_type", "scf")
            
            if receivers_only and not is_receiver(step_type):
                continue
            
            parameters = content.get("parameters", {})
            cards = content.get("cards", {})
            if parameters or cards:
                # Include both parameters and cards for detector
                step_params = dict(parameters)
                if cards:
                    step_params["cards"] = cards
                result.append((step_params, step_type))
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
        # bands_pw variant does NOT own K_POINTS
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
    Apply preset options to an existing step using variants registry.
    
    Per Constitution §10.3.3: This OVERWRITES preset-related parameters,
    it does NOT merge. Non-preset parameters are preserved.
    
    Uses variants registry to determine which dimensions apply to this step_type.
    Deletions are driven by profile NOT_APPLICABLE cells and keys that will be written.
    
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
    
    step_path = Path(step_path).resolve()
    
    if not step_path.exists():
        raise FileNotFoundError(f"Step file not found: {step_path}")
    
    # Load existing step content
    content = yaml.safe_load(step_path.read_text()) or {}
    step_type = content.get("step_type", "scf")
    existing_params = content.get("parameters", {})
    existing_cards = dict(content.get("cards", {}))
    
    # Build step_yaml structure for compilation
    step_yaml: Dict[str, Dict[str, Any]] = dict(existing_params)
    if "SYSTEM" not in step_yaml:
        step_yaml["SYSTEM"] = {}
    if "ELECTRONS" not in step_yaml:
        step_yaml["ELECTRONS"] = {}
    if existing_cards:
        step_yaml["cards"] = existing_cards
    else:
        step_yaml["cards"] = {}
    
    # Get existing params (copy to avoid mutating original)
    existing_system = dict(existing_params.get("SYSTEM", {}))
    existing_electrons = dict(existing_params.get("ELECTRONS", {}))
    
    # Track which dimensions are being applied (check variants)
    applied_dimensions = []
    filtered_options = {}
    
    for dimension, option_value in options.items():
        variant = get_variant(dimension, step_type)
        if variant is not None:
            applied_dimensions.append(dimension)
            filtered_options[dimension] = option_value
    
    # If no dimensions apply, skip
    if not applied_dimensions:
        return {
            "content": content,
            "accepted": False,
            "filtered_options": {},
            "updated_fields": [],
            "skipped_fields": ["no variant applies to this step_type"],
        }
    
    # Per ParamSpace Constitution v1: Apply must be executed in phases
    # Phase 1: Prerequisite ParamSpaces (occupations_scheme, step_type, etc.)
    # Phase 2: Dependent ParamSpaces (precision)
    prerequisite_dimensions = [
        d for d in applied_dimensions 
        if d in (DIMENSION_OCCUPATIONS_SCHEME, DIMENSION_MAGNETISM)
    ]
    dependent_dimensions = [
        d for d in applied_dimensions 
        if d == DIMENSION_PRECISION
    ]
    
    # Compile each dimension using variants
    compiled_patches: dict[str, dict[str, Any]] = {
        "SYSTEM": {},
        "ELECTRONS": {},
        "cards": {},
    }
    all_deletions: set[Tuple[str, str]] = set()  # (section, key) tuples
    
    # Phase 1: Prerequisite dimensions
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
            step_type,
            step_yaml,
            explicit_defaults=True,
            precision_context=precision_context,
        )
        
        # Merge patch
        if "SYSTEM" in patch:
            compiled_patches["SYSTEM"].update(patch["SYSTEM"])
        if "ELECTRONS" in patch:
            compiled_patches["ELECTRONS"].update(patch["ELECTRONS"])
        if "cards" in patch:
            compiled_patches["cards"].update(patch["cards"])
        
        # Collect deletions
        all_deletions.update(deletions)
    
    # Apply Phase 1 patches to step_yaml (for oracle to read latest state)
    step_yaml["SYSTEM"].update(compiled_patches["SYSTEM"])
    step_yaml["ELECTRONS"].update(compiled_patches["ELECTRONS"])
    if "cards" not in step_yaml:
        step_yaml["cards"] = {}
    step_yaml["cards"].update(compiled_patches["cards"])
    
    # Phase 2: Dependent dimensions (precision)
    for dimension in dependent_dimensions:
        # Normalize option
        if dimension == DIMENSION_PRECISION:
            option_enum = _normalize_option(filtered_options[dimension], PrecisionOption, PrecisionOption.MED)
        else:
            continue
        
        # Build precision context if needed
        precision_context = None
        if dimension == DIMENSION_PRECISION and precision_advice is not None:
            # Check if variant requires lattice_matrix (if it includes K_POINTS)
            variant = get_variant(dimension, step_type)
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
                        f"precision_lattice_matrix is required for precision preset application to {step_type}. "
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
            step_type,
            step_yaml,
            explicit_defaults=True,
            precision_context=precision_context,
        )
        
        # Merge patch
        if "SYSTEM" in patch:
            compiled_patches["SYSTEM"].update(patch["SYSTEM"])
        if "ELECTRONS" in patch:
            compiled_patches["ELECTRONS"].update(patch["ELECTRONS"])
        if "cards" in patch:
            compiled_patches["cards"].update(patch["cards"])
        
        # Collect deletions
        all_deletions.update(deletions)
    
    # Phase 2: Dependent dimensions (precision)
    for dimension in dependent_dimensions:
        # Normalize option
        if dimension == DIMENSION_PRECISION:
            option_enum = _normalize_option(filtered_options[dimension], PrecisionOption, PrecisionOption.MED)
        else:
            continue
        
        # Build precision context if needed
        precision_context = None
        if dimension == DIMENSION_PRECISION and precision_advice is not None:
            # Check if variant requires lattice_matrix (if it includes K_POINTS)
            variant = get_variant(dimension, step_type)
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
                        f"precision_lattice_matrix is required for precision preset application to {step_type}. "
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
            step_type,
            step_yaml,
            explicit_defaults=True,
            precision_context=precision_context,
        )
        
        # Merge patch
        if "SYSTEM" in patch:
            compiled_patches["SYSTEM"].update(patch["SYSTEM"])
        if "ELECTRONS" in patch:
            compiled_patches["ELECTRONS"].update(patch["ELECTRONS"])
        if "cards" in patch:
            compiled_patches["cards"].update(patch["cards"])
        
        # Collect deletions
        all_deletions.update(deletions)
    
    # Apply deletions (only keys marked NOT_APPLICABLE or that will be written)
    for section, key in all_deletions:
        if section == "SYSTEM":
            existing_system.pop(key, None)
        elif section == "ELECTRONS":
            existing_electrons.pop(key, None)
        elif section == "cards":
            existing_cards.pop(key, None)
    
    # Also delete keys that will be written (overwrite semantics)
    for section, patch_dict in compiled_patches.items():
        if section == "SYSTEM":
            for key in patch_dict.keys():
                existing_system.pop(key, None)
        elif section == "ELECTRONS":
            for key in patch_dict.keys():
                existing_electrons.pop(key, None)
        elif section == "cards":
            for key in patch_dict.keys():
                existing_cards.pop(key, None)
    
    # Add compiled params
    existing_system.update(compiled_patches["SYSTEM"])
    existing_electrons.update(compiled_patches["ELECTRONS"])
    existing_cards.update(compiled_patches["cards"])
    
    # Per ParamSpace Constitution v1: Apply invariants unconditionally
    # Build current YAML state for oracle (must be mutable dict for invariant enforcement)
    current_yaml_state = {
        "SYSTEM": existing_system,
        "ELECTRONS": existing_electrons,
        "cards": existing_cards,
    }
    oracle = Oracle(current_yaml_state)
    
    # Apply invariants for all ParamSpaces (even if not being applied)
    # This ensures invariant enforcement runs even when CUSTOM
    # Per Constitution v1 §2: Custom Apply (Invariant Enforcement) always runs
    from quantumvitas.presets.spaces_registry import SPACES
    for dimension_name, paramspace in SPACES.items():
        paramspace.apply_invariants(current_yaml_state, oracle)
    
    # Update existing dicts from current_yaml_state (invariants may have mutated it)
    existing_system = current_yaml_state["SYSTEM"]
    existing_electrons = current_yaml_state["ELECTRONS"]
    existing_cards = current_yaml_state["cards"]
    
    # Physics validation
    if validate_physics:
        _validate_magnetism_physics(existing_system)
    
    # Update content
    if "parameters" not in content:
        content["parameters"] = {}
    
    if existing_system:
        content["parameters"]["SYSTEM"] = existing_system
    if existing_electrons:
        content["parameters"]["ELECTRONS"] = existing_electrons
    
    # Handle cards
    if existing_cards:
        if "cards" not in content:
            content["cards"] = {}
        content["cards"].update(existing_cards)
    
    # Write back
    step_path.write_text(yaml.safe_dump(content, default_flow_style=False, sort_keys=False))
    
    # Build updated_fields
    updated_fields = []
    if compiled_patches["SYSTEM"]:
        updated_fields.extend(compiled_patches["SYSTEM"].keys())
    if compiled_patches["ELECTRONS"]:
        updated_fields.extend([f"ELECTRONS.{k}" for k in compiled_patches["ELECTRONS"].keys()])
    if compiled_patches["cards"]:
        updated_fields.extend([f"cards.{k}" for k in compiled_patches["cards"].keys()])
    
    return {
        "content": content,
        "accepted": True,
        "filtered_options": filtered_options,
        "updated_fields": updated_fields,
        "skipped_fields": [],
    }


def get_step_preset_params(step_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Get the preset-related parameters from a step.
    
    Args:
        step_path: Path to step.yaml file
        
    Returns:
        Dict with SYSTEM, ELECTRONS, K_POINTS -> preset params
    """
    step_path = Path(step_path).resolve()
    
    if not step_path.exists():
        return {}
    
    content = yaml.safe_load(step_path.read_text()) or {}
    parameters = content.get("parameters", {})
    cards = content.get("cards", {})
    system = parameters.get("SYSTEM", {})
    electrons = parameters.get("ELECTRONS", {})
    
    # QE kpoints are represented as cards.K_POINTS only
    kpoints = cards.get("K_POINTS", {})
    
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
    Get preset-related parameter footprints for all steps in a calculation.
    
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
    
    calculation_dir = Path(calculation_dir).resolve()
    steps_dir = calculation_dir / "steps"
    
    if not steps_dir.exists():
        return {}
    
    footprints = {}
    
    # Find all step.yaml files
    step_files = sorted(steps_dir.glob("*.step.yaml"))
    
    for step_file in step_files:
        try:
            content = yaml.safe_load(step_file.read_text()) or {}
            parameters = content.get("parameters", {})
            cards = content.get("cards", {})
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
            from quantumvitas.presets.detector import detect_magnetism
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
    Detect the workflow type from a calculation's step sequence.
    
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
    calculation_dir = Path(calculation_dir).resolve()
    
    # Load calculation.yaml to get step info
    calc_yaml = calculation_dir / "calculation.yaml"
    if not calc_yaml.exists():
        return "Unknown"
    
    try:
        content = yaml.safe_load(calc_yaml.read_text()) or {}
        steps = content.get("steps", [])
    except Exception:
        return "Unknown"
    
    # Collect step types
    step_types = set()
    for step_entry in steps:
        # Try to get step_type from entry or load step file
        step_type = step_entry.get("step_type")
        if not step_type:
            # Load from step file
            step_file = step_entry.get("step_file")
            if step_file:
                step_path = calculation_dir / step_file
                if step_path.exists():
                    try:
                        step_content = yaml.safe_load(step_path.read_text()) or {}
                        step_type = step_content.get("step_type")
                    except Exception:
                        pass
        
        if step_type:
            step_types.add(step_type.lower())
    
    # Workflow detection rules (order matters - more specific first)
    if "md" in step_types or "vc-md" in step_types:
        return "MD"
    
    if "relax" in step_types or "vc-relax" in step_types:
        return "Relaxation"
    
    if "ph" in step_types:
        return "Phonon"
    
    if "dos" in step_types:
        return "DOS"
    
    if "bands" in step_types or "bands_pw" in step_types:
        return "BandStructure"
    
    if "scf" in step_types and len(step_types) == 1:
        return "SCF"
    
    if "nscf" in step_types:
        # NSCF without DOS or bands is unusual
        return "NSCF"
    
    return "Unknown"

