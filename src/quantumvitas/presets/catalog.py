"""
Preset Catalog: Declarative API for UI preset rendering.

This module generates a catalog of preset dimensions, options, and scopes
from the variants registry. This is the single source of truth for UI rendering.

Per requirements:
- UI must not hardcode dimensions, options, or labels
- Catalog is generated from variants registry (no duplicate truth)
- Scope information comes from variant applies_to_step_types
"""

from __future__ import annotations

from typing import Dict, List, Any
from collections import defaultdict

from quantumvitas.presets.variants_registry import (
    VARIANTS,
    VARIANTS_BY_DIMENSION,
    PROFILE_TO_ENUM,
    list_dimensions_for_gen_step,
)
from quantumvitas.presets.dimensions import (
    MagnetismOption,
    OccupationsSchemeOption,
    PrecisionOption,
    ConvergenceOption,
)


# Human-readable labels for dimensions
DIMENSION_LABELS: Dict[str, str] = {
    "magnetism": "Magnetism",
    "occupations_scheme": "Occupations",
    "precision": "Precision",
    "convergence": "Convergence",
}

# Human-readable labels for options
OPTION_LABELS: Dict[str, Dict[str, str]] = {
    "magnetism": {
        "nonmagnetic": "Non-magnetic",
        "collinear_lsda": "Collinear (LSDA)",
        "noncollinear": "Noncollinear",
        "noncollinear_soc": "Noncollinear + SOC",
    },
    "occupations_scheme": {
        "fixed": "Fixed",
        "tetrahedra": "Tetrahedra",
        "smearing_gaussian": "Gaussian (0.02)",
    },
    "precision": {
        "low": "Low",
        "med": "Medium",
        "high": "High",
    },
    "convergence": {
        "fast": "Fast",
        "normal": "Normal",
        "robust": "Robust",
        "very_robust": "Very Robust",
    },
}

# Descriptions for dimensions
DIMENSION_DESCRIPTIONS: Dict[str, str] = {
    "magnetism": "Spin/SOC settings",
    "occupations_scheme": "Occupations scheme for BZ integration",
    "precision": "Precision level: controls k-mesh density, cutoffs, and convergence threshold",
    "convergence": "Convergence strategy: controls ELECTRONS mixing parameters and max iterations (conv_thr belongs to precision)",
}

# Default options per dimension
DIMENSION_DEFAULTS: Dict[str, str] = {
    "magnetism": "nonmagnetic",
    "occupations_scheme": "fixed",
    "precision": "med",
    "convergence": "normal",
}

# Order for dimensions (lower = earlier)
DIMENSION_ORDER: Dict[str, int] = {
    "magnetism": 10,
    "occupations_scheme": 20,
    "precision": 30,
    "convergence": 40,
}


def get_preset_catalog() -> Dict[str, Any]:
    """
    Generate preset catalog from variants registry.
    
    This is the single source of truth for UI preset rendering.
    All dimensions, options, labels, and scopes are derived from
    the variants registry.
    
    Returns:
        Dict with catalog structure:
        {
            "dimensions": [
                {
                    "dimension": str,
                    "label": str,
                    "description": str,
                    "order": int,
                    "options": [
                        {"value": str, "label": str}
                    ],
                    "default": str,
                    "scope": {
                        "type": "variant_step_types" | "variants",
                        "step_types": List[str] | None,
                        "variants": List[Dict] | None,
                    }
                }
            ],
            "schema_version": int
        }
    """
    dimensions_list: List[Dict[str, Any]] = []
    
    # Group variants by dimension
    for dimension, variants in VARIANTS_BY_DIMENSION.items():
        # Get all unique step types that this dimension applies to
        all_step_types = set()
        variant_details = []
        
        for variant in variants:
            step_types = sorted(variant.applies_to_step_types)
            all_step_types.update(step_types)
            
            # For precision, include variant details
            if dimension == "precision":
                # Check if variant includes K_POINTS
                has_kpoints = any(
                    key.section == "cards" and key.key == "K_POINTS"
                    for key in variant.space.keys
                )
                notes = "mesh K_POINTS" if has_kpoints else "no K_POINTS (kpath preserved)"
                
                variant_details.append({
                    "name": variant.name,
                    "step_types": step_types,
                    "notes": notes,
                })
        
        # Get options from enum values
        options: List[Dict[str, str]] = []
        profile_to_enum = PROFILE_TO_ENUM.get(dimension, {})
        
        if dimension == "magnetism":
            for opt in MagnetismOption:
                options.append({
                    "value": opt.value,
                    "label": OPTION_LABELS["magnetism"].get(opt.value, opt.value),
                })
        elif dimension == "occupations_scheme":
            for opt in OccupationsSchemeOption:
                options.append({
                    "value": opt.value,
                    "label": OPTION_LABELS["occupations_scheme"].get(opt.value, opt.value),
                })
        elif dimension == "precision":
            for opt in PrecisionOption:
                options.append({
                    "value": opt.value,
                    "label": OPTION_LABELS["precision"].get(opt.value, opt.value),
                })
        elif dimension == "convergence":
            for opt in ConvergenceOption:
                options.append({
                    "value": opt.value,
                    "label": OPTION_LABELS["convergence"].get(opt.value, opt.value),
                })
        
        # Build scope
        if dimension == "precision" and len(variants) > 1:
            # Precision has multiple variants - show variant details
            scope = {
                "type": "variants",
                "variants": variant_details,
            }
        else:
            # Single variant or simple case - show step types
            scope = {
                "type": "variant_step_types",
                "step_types": sorted(all_step_types),
            }
        
        dimensions_list.append({
            "dimension": dimension,
            "label": DIMENSION_LABELS.get(dimension, dimension),
            "description": DIMENSION_DESCRIPTIONS.get(dimension, ""),
            "order": DIMENSION_ORDER.get(dimension, 999),
            "options": options,
            "default": DIMENSION_DEFAULTS.get(dimension, options[0]["value"] if options else ""),
            "scope": scope,
        })
    
    # Sort by order
    dimensions_list.sort(key=lambda d: d["order"])
    
    return {
        "dimensions": dimensions_list,
        "schema_version": 1,
    }


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

