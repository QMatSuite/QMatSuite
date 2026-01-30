"""
Helper functions for preset/ParamSpace testing.

These utilities are used across multiple test files to ensure consistent
behavior for engine availability checks and roundtrip testing.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from quantumvitas.engine.registry import create_default_registry


def is_pyscf_available() -> bool:
    """
    Check if PySCF can be imported.
    
    Returns:
        True if PySCF can be imported, False otherwise
    """
    try:
        import pyscf
        return True
    except ImportError:
        return False


def is_orca_available() -> bool:
    """
    Check if ORCA engine is registered (not binary availability).
    
    This checks if ORCA is in the engine registry, which should always
    be true even if the ORCA binary is not installed.
    
    Returns:
        True if ORCA is in engine registry, False otherwise
    """
    try:
        registry = create_default_registry()
        return registry.has("orca")
    except Exception:
        return False


def build_test_step_yaml(
    step_type: str,
    parameters: Optional[Dict[str, Dict[str, Any]]] = None,
    cards: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a test step YAML structure.
    
    Args:
        step_type: Step type (e.g., "scf", "qe_scf", "pyscf_scf")
        parameters: Optional parameters dict (e.g., {"SYSTEM": {...}})
        cards: Optional cards dict (e.g., {"K_POINTS": {...}})
        
    Returns:
        Dict representing step YAML structure
    """
    result: Dict[str, Any] = {
        "step_type_gen": step_type,
    }
    
    if parameters:
        result["parameters"] = parameters
    else:
        result["parameters"] = {}
    
    if cards:
        result["cards"] = cards
    else:
        result["cards"] = {}
    
    return result


def _apply_patch_to_yaml(
    step_yaml: Dict[str, Any],
    patch: Dict[str, Any],
    deletions: set[tuple[str, str]],
) -> Dict[str, Any]:
    """
    Apply a patch to step_yaml, supporting arbitrary sections.
    
    This is a helper that copies all sections from step_yaml and applies
    the patch, supporting both QE sections (SYSTEM, ELECTRONS, cards) and
    QC sections (scf, dft, engine.orca.scf, etc.).
    
    Args:
        step_yaml: Original step YAML structure
        patch: Patch dict (section -> params)
        deletions: Set of (section, key) tuples to delete
        
    Returns:
        Modified YAML dict (copy with patch applied)
    """
    # Copy all existing sections from step_yaml
    modified_yaml = {}
    for section in step_yaml:
        if isinstance(step_yaml[section], dict):
            modified_yaml[section] = dict(step_yaml[section])
        else:
            modified_yaml[section] = step_yaml[section]
    
    # Apply patch (support arbitrary sections)
    for section, params in patch.items():
        if section not in modified_yaml:
            modified_yaml[section] = {}
        if isinstance(params, dict):
            modified_yaml[section].update(params)
        else:
            modified_yaml[section] = params
    
    # Apply deletions (remove keys)
    for section, key in deletions:
        if section in modified_yaml and key in modified_yaml[section]:
            del modified_yaml[section][key]
    
    return modified_yaml


def apply_and_detect_roundtrip(
    dimension: str,
    option_enum: Any,
    step_type: str,
    step_yaml: Dict[str, Dict[str, Any]],
    *,
    precision_context: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Apply a preset and then detect it, verifying roundtrip.
    
    This is a helper function that:
    1. Compiles the preset option to a patch
    2. Applies the patch to step_yaml
    3. Detects the preset from the modified step_yaml
    4. Returns the detected option
    
    Args:
        dimension: Dimension name (e.g., "magnetism", "precision", "qc_precision")
        option_enum: Enum option (e.g., MagnetismOption.NONMAGNETIC)
        step_type: Step type (gen/public step, e.g., "scf")
        step_yaml: Current step YAML structure
        precision_context: Optional context for precision (lattice, base cutoffs)
        
    Returns:
        Detected option enum (or CUSTOM if no match)
    """
    from quantumvitas.presets.variants_registry import (
        compile_dimension_patch_for_step,
        detect_dimension_for_step,
    )
    
    # Compile preset to patch
    patch, deletions = compile_dimension_patch_for_step(
        dimension,
        option_enum,
        step_type,
        step_yaml,
        explicit_defaults=True,
        precision_context=precision_context,
    )
    
    # Apply patch to step_yaml (create a copy to avoid mutation)
    modified_yaml = _apply_patch_to_yaml(step_yaml, patch, deletions)
    
    # Detect preset from modified YAML
    detected = detect_dimension_for_step(
        dimension,
        step_type,
        modified_yaml,
        precision_context=precision_context,
    )
    
    return detected


def apply_preset_to_yaml(
    dimension: str,
    option_enum: Any,
    step_type: str,
    step_yaml: Dict[str, Dict[str, Any]],
    *,
    precision_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Apply a preset to step_yaml and return the modified YAML.
    
    This is a helper function that:
    1. Compiles the preset option to a patch
    2. Applies the patch to step_yaml (creates a copy)
    3. Returns the modified YAML dict
    
    Args:
        dimension: Dimension name (e.g., "magnetism", "precision", "qc_precision")
        option_enum: Enum option (e.g., MagnetismOption.NONMAGNETIC)
        step_type: Step type (gen/public step, e.g., "scf")
        step_yaml: Current step YAML structure
        precision_context: Optional context for precision (lattice, base cutoffs)
        
    Returns:
        Modified YAML dict (copy of step_yaml with patch applied)
    """
    from quantumvitas.presets.variants_registry import compile_dimension_patch_for_step
    
    # Compile preset to patch
    patch, deletions = compile_dimension_patch_for_step(
        dimension,
        option_enum,
        step_type,
        step_yaml,
        explicit_defaults=True,
        precision_context=precision_context,
    )
    
    # Apply patch to step_yaml (create a copy to avoid mutation)
    modified_yaml = _apply_patch_to_yaml(step_yaml, patch, deletions)
    
    return modified_yaml

