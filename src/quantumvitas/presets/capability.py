"""
Capability Resolver: SSOT for preset capability queries.

This module provides the single public API for determining which presets
are available for a given engine and gen step combination.

Contract:
- Engine.supported_presets is SSOT for engine capability declaration
- ParamSpace variants determine applicability by gen step
- Capability = intersection of engine support and ParamSpace applicability
"""

from __future__ import annotations

from typing import List, Optional
from pathlib import Path

from quantumvitas.presets.variants_registry import (
    list_dimensions_for_gen_step,
    get_variant,
)
from quantumvitas.workflow.registry import get_registry, normalize_step_type_to_public


class CapabilityError(Exception):
    """Raised when a preset is not available for the requested engine/gen_step."""
    
    def __init__(self, engine_name: str, gen_step: str, preset_id: str):
        self.engine_name = engine_name
        self.gen_step = gen_step
        self.preset_id = preset_id
        super().__init__(
            f"Preset '{preset_id}' is not available for engine '{engine_name}' on gen step '{gen_step}'"
        )


def list_presets_for_engine(engine_name: str, gen_step: str) -> List[str]:
    """
    List preset dimensions available for a given engine and gen step.
    
    This implements Contract C: returns the intersection of:
    - Engine.supported_presets (engine capability declaration)
    - ParamSpace applicability for the gen step (Contract A)
    
    Args:
        engine_name: Engine identifier (e.g., "qe", "pyscf", "orca")
        gen_step: Gen/public step type (e.g., "scf", "nscf", "td")
        
    Returns:
        Sorted list of dimension names that are both:
        1. Supported by the engine (from engine.supported_presets)
        2. Applicable to the gen step (from ParamSpace variants)
        
    Raises:
        KeyError: If engine_name is not found in engine registry
    """
    from quantumvitas.engine.registry import create_default_registry
    
    # Get engine instance
    engine_registry = create_default_registry()
    if not engine_registry.has(engine_name):
        raise KeyError(f"Engine '{engine_name}' not found in registry")
    
    engine = engine_registry.get(engine_name)
    
    # Get engine-supported presets
    engine_supported = set(engine.supported_presets)
    
    # Get ParamSpace-applicable dimensions for this gen step
    paramspace_applicable = set(list_dimensions_for_gen_step(gen_step))
    
    # Return intersection (both conditions must be true)
    available = engine_supported & paramspace_applicable
    
    return sorted(available)


def list_profiles_for_preset(
    engine_name: str, 
    preset_id: str, 
    gen_step: str
) -> List[str]:
    """
    List available profiles for a preset on engine + gen_step.
    
    Args:
        engine_name: Engine identifier (e.g., "qe", "pyscf", "orca")
        preset_id: Preset dimension name (e.g., "precision", "magnetism")
        gen_step: Gen/public step type (e.g., "scf", "nscf")
        
    Returns:
        Sorted list of profile names available for this preset.
        Returns empty list if preset is not available for engine/gen_step.
        
    Raises:
        KeyError: If engine_name is not found in engine registry
    """
    # First check if preset is available
    if not validate_preset_capability(engine_name, gen_step, preset_id):
        return []
    
    # Get the variant for this dimension and gen step
    variant = get_variant(preset_id, gen_step)
    if variant is None:
        return []
    
    # Extract profile names from ParamSpace
    space = variant.space
    profiles = list(space.profiles.keys())
    
    return sorted(profiles)


def validate_preset_capability(
    engine_name: str, 
    gen_step: str, 
    preset_id: str
) -> bool:
    """
    Check if preset is available for engine + gen_step.
    
    Args:
        engine_name: Engine identifier (e.g., "qe", "pyscf", "orca")
        preset_id: Preset dimension name (e.g., "precision", "magnetism")
        gen_step: Gen/public step type (e.g., "scf", "nscf")
        
    Returns:
        True if preset is available, False otherwise.
        
    Raises:
        KeyError: If engine_name is not found in engine registry
    """
    available_presets = list_presets_for_engine(engine_name, gen_step)
    return preset_id in available_presets


def require_preset_capability(
    engine_name: str, 
    gen_step: str, 
    preset_id: str
) -> None:
    """
    Raise CapabilityError if preset is not available.
    
    This is the guard function for apply operations.
    
    Args:
        engine_name: Engine identifier (e.g., "qe", "pyscf", "orca")
        gen_step: Gen/public step type (e.g., "scf", "nscf")
        preset_id: Preset dimension name (e.g., "precision", "magnetism")
        
    Raises:
        CapabilityError: If preset is not available
        KeyError: If engine_name is not found in engine registry
    """
    if not validate_preset_capability(engine_name, gen_step, preset_id):
        raise CapabilityError(engine_name, gen_step, preset_id)


def resolve_engine_for_step(step_path: Path) -> Optional[str]:
    """
    Determine engine from step.yaml file.
    
    Reads step.yaml, extracts step_type, and uses StepTypeRegistry
    to determine the engine.
    
    Args:
        step_path: Path to step.yaml file
        
    Returns:
        Engine name (e.g., "qe", "pyscf", "orca") or None if not found
    """
    try:
        import yaml
        
        with open(step_path, 'r') as f:
            step_data = yaml.safe_load(f)
        
        if not step_data or 'step_type' not in step_data:
            return None
        
        step_type = step_data['step_type']
        if not step_type:
            return None
        
        # Use registry to get engine from step_type
        registry = get_registry()
        spec = registry.get(step_type)
        
        if spec and spec.engine:
            return spec.engine
        
        return None
    except Exception:
        return None

