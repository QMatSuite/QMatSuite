"""
Calculation and Step DTOs.

This module provides DTOs for calculations and steps.
"""

from __future__ import annotations

from typing import Any

from dataclasses import dataclass

from quantumvitas.api.types.base import BaseDTO
from quantumvitas.api.types.common import MetaDTO


@dataclass
class CalculationRefDTO(BaseDTO):
    """
    Calculation reference DTO (lightweight, for resolution).
    
    Contains only identity and path - use svc.calculation.get(ref.calc_id) for full details.
    """
    # Identity (required)
    calc_id: str              # ULID
    
    # Path (required)
    path: str                 # Relative path from project root (e.g., "calculations/si-scf")
    
    # Metadata (optional, minimal)
    meta: MetaDTO | None = None


@dataclass
class CalculationDTO(BaseDTO):
    """
    Calculation entity DTO.
    
    NOTE: No params field. Use svc.calculation.get_effective_params() if needed.
    """
    # Identity (required)
    calc_id: str              # ULID
    engine: str               # Engine family
    status: str               # pending, running, completed, failed

    # Metadata (optional)
    meta: MetaDTO | None = None

    # References (optional)
    structure_id: str | None = None   # ULID
    step_ids: list[str] | None = None # List of step ULIDs

    # Minimal info (optional)
    step_count: int | None = None
    completed_step_count: int | None = None
    
    # Compatibility properties for historical API contract
    @property
    def id(self) -> str:
        """Compatibility: return calc_id or meta.id."""
        return self.meta.id if self.meta and self.meta.id else self.calc_id
    
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
    def n_steps(self) -> int | None:
        """Compatibility: alias for step_count."""
        return self.step_count
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with compatibility properties."""
        result = super().to_dict()
        # Add compatibility properties
        result["id"] = self.id
        if self.name is not None:
            result["name"] = self.name
        if self.slug is not None:
            result["slug"] = self.slug
        if self.path is not None:
            result["path"] = self.path
        if self.n_steps is not None:
            result["n_steps"] = self.n_steps
        return result


@dataclass
class StepDTO(BaseDTO):
    """
    Calculation step entity DTO.
    """
    # Identity (required)
    step_id: str              # ULID
    calc_id: str              # Parent calculation ULID
    step_type: str            # e.g., "qe_scf", "vasp_relax"
    status: str               # pending, running, completed, failed

    # Metadata (optional)
    meta: MetaDTO | None = None

    # Status details (optional)
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    exit_code: int | None = None
    error_message: str | None = None

