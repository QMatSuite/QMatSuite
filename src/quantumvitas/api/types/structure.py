"""
Structure DTO.

This module provides DTOs for atomic structures.
"""

from __future__ import annotations

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

