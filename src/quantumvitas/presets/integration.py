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
from typing import Any, Dict, List, Optional, Union
import yaml

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
    _CustomType,
)
from quantumvitas.presets.detector import detect_all_presets
from quantumvitas.presets.compiler import compile_presets, PresetCompilationError


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
        Example: {"spin": "collinear", "soc": "no_soc", "material": "metal"}
        
    Note:
        Returns string values for JSON serialization to daemon/GUI.
        Use detect_presets_from_calculation_typed() for enum values.
    """
    # Load step parameters from calculation
    step_params_list = _load_step_parameters(calculation_dir)
    
    # Detect presets
    detected = detect_all_presets(step_params_list)
    
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
) -> Dict[str, Union[SpinOption, SOCOption, MaterialOption, _CustomType]]:
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
            if parameters:
                step_params_list.append(parameters)
        except Exception:
            # Skip malformed step files
            continue
    
    return step_params_list


def apply_presets_to_step(
    step_path: Path,
    options: Dict[str, Any],
    *,
    validate_physics: bool = True,
    precision_advice: Optional[Any] = None,  # PrecisionAdvice object
) -> Dict[str, Any]:
    """
    Apply preset options to an existing step.
    
    Per Constitution §10.3.3: This OVERWRITES preset-related parameters,
    it does NOT merge. Non-preset parameters are preserved.
    
    Per Constitution §10.1.1: Step defines its own "preset receiver".
    This function uses the receiver registry to determine which presets
    the step accepts based on step_type.
    
    Args:
        step_path: Path to step.yaml file
        options: Preset options dict with dimension keys
            {"spin": "collinear", "soc": "no_soc", "material": "metal", "precision": "med"}
        validate_physics: If True, validate physics constraints
        precision_advice: Optional PrecisionAdvice for precision preset
            (required if "precision" is in options)
        
    Returns:
        Dict with:
            - "content": Updated step content dict
            - "accepted": True if step accepted presets, False if skipped
            - "filtered_options": Options that were actually applied
        
    Raises:
        PresetCompilationError: If invalid option combinations
        FileNotFoundError: If step file doesn't exist
    """
    from quantumvitas.presets.receivers import filter_presets_for_step
    from quantumvitas.presets.compiler import compile_precision_from_advice
    
    step_path = Path(step_path).resolve()
    
    if not step_path.exists():
        raise FileNotFoundError(f"Step file not found: {step_path}")
    
    # Load existing step content
    content = yaml.safe_load(step_path.read_text()) or {}
    step_type = content.get("step_type", "scf")
    existing_params = content.get("parameters", {})
    
    # Filter options based on step's receiver capability
    filtered_options = filter_presets_for_step(step_type, options)
    
    # If step doesn't accept any of the provided presets, skip
    if not filtered_options:
        return {
            "content": content,
            "accepted": False,
            "filtered_options": {},
        }
    
    # Separate precision from other presets (it needs special handling)
    non_precision_options = {k: v for k, v in filtered_options.items() if k != DIMENSION_PRECISION}
    precision_option = filtered_options.get(DIMENSION_PRECISION)
    
    # Compile non-precision preset options
    compiled_system: Dict[str, Any] = {}
    compiled_electrons: Dict[str, Any] = {}
    compiled_kpoints: Optional[Dict[str, Any]] = None
    
    if non_precision_options:
        compiled = compile_presets(non_precision_options, validate_physics=validate_physics)
        compiled_system = compiled.get("SYSTEM", {})
    
    # Handle precision preset separately (requires pre-computed advice)
    if precision_option is not None and precision_advice is not None:
        precision_compiled = compile_precision_from_advice(precision_advice)
        compiled_system.update(precision_compiled.get("SYSTEM", {}))
        compiled_electrons.update(precision_compiled.get("ELECTRONS", {}))
        compiled_kpoints = precision_compiled.get("K_POINTS")
    
    # Get existing params
    existing_system = dict(existing_params.get("SYSTEM", {}))
    existing_electrons = dict(existing_params.get("ELECTRONS", {}))
    
    # Define preset-related parameters (to be overwritten)
    SYSTEM_PRESET_PARAMS = {
        # Spin
        "nspin", "noncolin",
        # SOC
        "lspinorb",
        # Material
        "occupations", "smearing", "degauss",
        # Precision (cutoffs)
        "ecutwfc", "ecutrho",
    }
    
    ELECTRONS_PRESET_PARAMS = {
        # Precision (convergence)
        "conv_thr",
    }
    
    # Remove existing preset params, then add compiled ones
    for param in SYSTEM_PRESET_PARAMS:
        existing_system.pop(param, None)
    for param in ELECTRONS_PRESET_PARAMS:
        existing_electrons.pop(param, None)
    
    # Add compiled params
    existing_system.update(compiled_system)
    existing_electrons.update(compiled_electrons)
    
    # Update content
    if "parameters" not in content:
        content["parameters"] = {}
    
    if existing_system:
        content["parameters"]["SYSTEM"] = existing_system
    if existing_electrons:
        content["parameters"]["ELECTRONS"] = existing_electrons
    
    # Handle K_POINTS (special card, not namelist)
    if compiled_kpoints is not None:
        content["parameters"]["K_POINTS"] = compiled_kpoints
    
    # Write back
    step_path.write_text(yaml.safe_dump(content, default_flow_style=False, sort_keys=False))
    
    return {
        "content": content,
        "accepted": True,
        "filtered_options": filtered_options,
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
    system = parameters.get("SYSTEM", {})
    electrons = parameters.get("ELECTRONS", {})
    kpoints = parameters.get("K_POINTS", {})
    
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
                "spin": "collinear",
                "material": "metal",
                "precision": "med"
            },
            ...
        }
    """
    from quantumvitas.presets.detector import (
        detect_spin, detect_soc, detect_material, detect_precision
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
            system = parameters.get("SYSTEM", {})
            electrons = parameters.get("ELECTRONS", {})
            kpoints = parameters.get("K_POINTS", {})
            
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
            if isinstance(kpoints, dict) and "mesh" in kpoints:
                mesh = kpoints["mesh"]
                if isinstance(mesh, (list, tuple)) and len(mesh) >= 3:
                    preset_params["kmesh"] = f"{mesh[0]}×{mesh[1]}×{mesh[2]}"
            
            # Detect preset values for this step
            spin_val = detect_spin(parameters)
            soc_val = detect_soc(parameters)
            material_val = detect_material(parameters)
            precision_val = detect_precision(parameters)
            
            footprint = {
                "params": preset_params,
                "spin": spin_val.value if hasattr(spin_val, 'value') else str(spin_val),
                "soc": soc_val.value if hasattr(soc_val, 'value') else str(soc_val),
                "material": material_val.value if hasattr(material_val, 'value') else str(material_val),
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

