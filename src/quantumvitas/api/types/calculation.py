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
    
    Contains only identity and path - use svc.calculation.get(ref.calc_ulid) for full details.
    """
    # Identity (required)
    calc_ulid: str              # ULID
    
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
    calc_ulid: str              # ULID
    engine: str               # Engine family
    status: str               # pending, running, completed, failed

    # Metadata (optional)
    meta: MetaDTO | None = None

    # References (optional)
    structure_ulid: str | None = None   # ULID
    step_ulids: list[str] | None = None # List of step ULIDs

    # Minimal info (optional)
    step_count: int | None = None
    completed_step_count: int | None = None
    
    # Compatibility properties for historical API contract
    @property
    def id(self) -> str:
        """Compatibility: return calc_ulid or meta.ulid."""
        return self.meta.ulid if self.meta and self.meta.ulid else self.calc_ulid
    
    @property
    def calc_id(self) -> str:
        """Compatibility: return calc_ulid."""
        return self.calc_ulid
    
    @property
    def structure_id(self) -> str | None:
        """Compatibility: return structure_ulid."""
        return self.structure_ulid
    
    @property
    def step_ids(self) -> list[str] | None:
        """Compatibility: return step_ulids."""
        return self.step_ulids
    
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
        result["ulid"] = self.id
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
    step_ulid: str              # ULID
    calc_ulid: str              # Parent calculation ULID
    step_type_spec: str            # SPEC type (e.g., "qe_scf", "vasp_relax")
    status: str               # pending, running, completed, failed
    step_type_gen: str | None = None  # GEN type (e.g., "scf", "relax") - computed from step_type_spec

    # Metadata (optional)
    meta: MetaDTO | None = None

    # Status details (optional)
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    exit_code: int | None = None
    error_message: str | None = None

