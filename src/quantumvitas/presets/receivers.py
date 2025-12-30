"""
Preset Receiver Registry.

Per Constitution §10.1.1: Preset application is BROADCAST, not filtered.
The UI and calc layer do NOT decide which steps accept presets.
Each step defines its own "preset receiver" - it may accept, partially accept, or ignore.

This module provides:
- A registry mapping step_type → accepted preset dimensions
- Step-level override mechanism for per-step customization
- Receiver capability checking for BROADCAST apply

Design principles:
- Default behavior: accept none (no-op) for unknown step types
- QE pw.x step_types (scf/nscf/bands/relax/md/vc-*): accept v0 dimensions (spin/soc/material)
- Post-processing steps: accept none (unless explicitly enabled)
- Receiver declaration is metadata, NOT persisted preset state
"""

from enum import Enum
from typing import Dict, FrozenSet, Optional, Set

from quantumvitas.presets.dimensions import (
    DIMENSION_SPIN,
    DIMENSION_SOC, 
    DIMENSION_MATERIAL,
)


class PresetDimension(str, Enum):
    """Preset dimensions that can be applied."""
    SPIN = DIMENSION_SPIN
    SOC = DIMENSION_SOC
    MATERIAL = DIMENSION_MATERIAL


# V0 preset dimensions (spin, soc, material)
V0_DIMENSIONS: FrozenSet[str] = frozenset({
    DIMENSION_SPIN,
    DIMENSION_SOC,
    DIMENSION_MATERIAL,
})

# Step types that accept v0 preset dimensions (QE pw.x-based calculations)
# These are the primary DFT calculation types that have spin/soc/material relevance
PW_STEP_TYPES: FrozenSet[str] = frozenset({
    "scf",
    "nscf", 
    "bands_pw",  # pw.x calculation='bands'
    "relax",
    "vc-relax",
    "md",
    "vc-md",
})

# Step types that do NOT accept presets (post-processing and other utilities)
# These steps work on pre-computed outputs and don't have direct spin/soc/material params
POST_PROCESSING_STEP_TYPES: FrozenSet[str] = frozenset({
    "dos",       # dos.x - works on charge density
    "bands",     # bands.x - post-processes band eigenvalues
    "projwfc",   # projwfc.x - projected DOS
    "pp",        # pp.x - various post-processing
    "q2r",       # q2r.x - phonon
    "matdyn",    # matdyn.x - phonon
    "dynmat",    # dynmat.x - phonon
    "sumpdos",   # sumpdos.x - DOS utilities
    "band_interpolation",
    "ppacf",
    "pprism",
})

# Step types that might accept presets in the future but not in v0
FUTURE_PRESET_STEP_TYPES: FrozenSet[str] = frozenset({
    "ph",        # ph.x - phonon calculations (might need spin)
    "hp",        # hp.x - Hubbard parameters
    "gipaw",     # gipaw.x - NMR/EPR
})


class PresetReceiverRegistry:
    """
    Registry for step_type → accepted preset dimensions mapping.
    
    This is the authoritative source for which step types accept which presets.
    Per Constitution: receiver belongs to step, not to UI/compiler.
    """
    
    def __init__(self):
        # Default registry: step_type -> set of accepted dimensions
        self._registry: Dict[str, FrozenSet[str]] = {}
        
        # Initialize with default mappings
        self._initialize_defaults()
    
    def _initialize_defaults(self):
        """Initialize default step_type → dimensions mapping."""
        # PW.x step types accept all v0 dimensions
        for step_type in PW_STEP_TYPES:
            self._registry[step_type] = V0_DIMENSIONS
        
        # Post-processing steps accept no presets
        for step_type in POST_PROCESSING_STEP_TYPES:
            self._registry[step_type] = frozenset()
        
        # Future preset step types - empty for now
        for step_type in FUTURE_PRESET_STEP_TYPES:
            self._registry[step_type] = frozenset()
        
        # Custom step type - accepts none by default
        self._registry["custom"] = frozenset()
    
    def get_accepted_dimensions(self, step_type: str) -> FrozenSet[str]:
        """
        Get the set of preset dimensions accepted by a step type.
        
        Args:
            step_type: Step type string (e.g., "scf", "nscf", "dos")
            
        Returns:
            FrozenSet of dimension names this step type accepts.
            Empty set means the step accepts no presets (no-op).
        """
        step_type_lower = step_type.lower() if step_type else ""
        return self._registry.get(step_type_lower, frozenset())
    
    def accepts_preset(self, step_type: str, dimension: str) -> bool:
        """
        Check if a step type accepts a specific preset dimension.
        
        Args:
            step_type: Step type string
            dimension: Preset dimension name (e.g., "spin", "soc", "material")
            
        Returns:
            True if step type accepts this dimension, False otherwise.
        """
        return dimension in self.get_accepted_dimensions(step_type)
    
    def filter_presets_for_step(
        self, 
        step_type: str, 
        presets: Dict[str, str],
    ) -> Dict[str, str]:
        """
        Filter preset options to only include dimensions accepted by step type.
        
        This is the core "receiver" logic - it determines which presets
        a step will actually process.
        
        Args:
            step_type: Step type string
            presets: Dict of preset options (dimension -> value)
            
        Returns:
            Filtered dict containing only accepted dimensions.
        """
        accepted = self.get_accepted_dimensions(step_type)
        return {k: v for k, v in presets.items() if k in accepted}
    
    def is_receiver(self, step_type: str) -> bool:
        """
        Check if a step type is a preset receiver (accepts any presets).
        
        Args:
            step_type: Step type string
            
        Returns:
            True if step type accepts at least one preset dimension.
        """
        return len(self.get_accepted_dimensions(step_type)) > 0
    
    def register_step_type(self, step_type: str, dimensions: Set[str]):
        """
        Register or update a step type's accepted dimensions.
        
        Use this for:
        - Adding new step types
        - Overriding default behavior
        - Testing with custom configurations
        
        Args:
            step_type: Step type string
            dimensions: Set of dimension names this step type should accept
        """
        self._registry[step_type.lower()] = frozenset(dimensions)


# Global registry instance
_registry: Optional[PresetReceiverRegistry] = None


def get_receiver_registry() -> PresetReceiverRegistry:
    """Get the global preset receiver registry."""
    global _registry
    if _registry is None:
        _registry = PresetReceiverRegistry()
    return _registry


def reset_receiver_registry():
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None


# Convenience functions that use the global registry

def get_accepted_dimensions(step_type: str) -> FrozenSet[str]:
    """Get preset dimensions accepted by a step type."""
    return get_receiver_registry().get_accepted_dimensions(step_type)


def accepts_preset(step_type: str, dimension: str) -> bool:
    """Check if a step type accepts a preset dimension."""
    return get_receiver_registry().accepts_preset(step_type, dimension)


def filter_presets_for_step(step_type: str, presets: Dict[str, str]) -> Dict[str, str]:
    """Filter presets to only those accepted by step type."""
    return get_receiver_registry().filter_presets_for_step(step_type, presets)


def is_receiver(step_type: str) -> bool:
    """Check if a step type is a preset receiver."""
    return get_receiver_registry().is_receiver(step_type)

