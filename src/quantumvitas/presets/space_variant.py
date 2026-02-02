"""
ParamSpace Variant: Declaration-driven preset application.

Each variant explicitly declares which step types it applies to.
This is the single source of truth for "where a preset applies".

Per Constitution: No heuristics, no JSON-driven behavior, only explicit declarations.
"""

from dataclasses import dataclass
from typing import FrozenSet

from quantumvitas.presets.paramspace import ParamSpace


@dataclass(frozen=True)
class ParamSpaceVariant:
    """
    A variant of a ParamSpace that applies to specific step types.
    
    This is the ground truth for preset application scope.
    Each variant explicitly lists which step types it applies to.
    
    Attributes:
        name: Unique identifier for this variant (e.g., "PRECISION_PW_DEFAULT")
        dimension: Dimension name (e.g., "precision", "magnetism")
        space: The ParamSpace instance for this variant
        applies_to_step_types: Set of step types this variant applies to
        priority: Optional priority for tie-breaking (default 0, prefer to forbid overlaps)
    """
    name: str
    dimension: str
    space: ParamSpace
    applies_to_step_types: FrozenSet[str]
    priority: int = 0
    
    def __post_init__(self):
        """Validate variant configuration."""
        if not self.name:
            raise ValueError("Variant name cannot be empty")
        if not self.dimension:
            raise ValueError("Variant dimension cannot be empty")
        if not self.applies_to_step_types:
            raise ValueError(f"Variant {self.name} must apply to at least one step type")
        if not isinstance(self.space, ParamSpace):
            raise ValueError(f"Variant {self.name} must have a ParamSpace instance")
    
    def applies_to(self, step_type_gen: str) -> bool:
        """Check if this variant applies to a given step type."""
        return step_type_gen in self.applies_to_step_types

