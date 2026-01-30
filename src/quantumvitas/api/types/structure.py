"""
Structure DTO.

This module provides DTOs for atomic structures.
"""

from __future__ import annotations

from typing import Any

from dataclasses import dataclass

from quantumvitas.api.types.base import BaseDTO
from quantumvitas.api.types.common import MetaDTO


@dataclass
class StructureDTO(BaseDTO):
    """
    Atomic structure summary DTO.
    
    NOTE: No positions or species arrays. Use svc.structure.get_atoms() for full data.
    """
    # Identity (required)
    structure_id: str         # ULID
    formula: str              # Chemical formula
    num_atoms: int

    # Metadata (optional)
    meta: MetaDTO | None = None

    # Crystallographic (optional)
    space_group: str | None = None
    point_group: str | None = None
    cell_volume_ang3: float | None = None

    # Minimal lattice info (optional, for display only)
    lattice_abc: list[float] | None = None  # [a, b, c] in Angstrom
    lattice_angles: list[float] | None = None  # [alpha, beta, gamma] in degrees
    
    # Compatibility properties for historical API contract
    @property
    def id(self) -> str:
        """Compatibility: return structure_id or meta.ulid."""
        return self.meta.ulid if self.meta and self.meta.ulid else self.structure_id
    
    @property
    def name(self) -> str | None:
        """Compatibility: return meta.name."""
        return self.meta.name if self.meta else None
    
    @property
    def slug(self) -> str | None:
        """Compatibility: return meta.slug."""
        return self.meta.slug if self.meta else None
    
    @property
    def path(self) -> str | None:
        """Compatibility: return meta.path."""
        return self.meta.path if self.meta else None
    
    @property
    def n_atoms(self) -> int:
        """Compatibility: alias for num_atoms."""
        return self.num_atoms
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with compatibility properties."""
        result = super().to_dict()
        # Add compatibility properties
        result["ulid"] = self.id
        if self.name is not None:
            result["name"] = self.name
        if self.slug is not None:
            result["slug"] = self.slug
        if self.path is not None:
            result["path"] = self.path
        result["n_atoms"] = self.n_atoms
        return result

