"""
Calculation and Step DTOs.

This module provides DTOs for calculations and steps.
"""

from __future__ import annotations

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

