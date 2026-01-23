"""
Run result DTO.

This module provides DTOs for execution runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from quantumvitas.api.types.base import BaseDTO
from quantumvitas.api.types.error import ErrorDTO


@dataclass
class RunResultDTO(BaseDTO):
    """
    Execution run result DTO.
    
    NOTE: Uses run_id (not job_id) for consistent ULID naming.
    """
    # Identity (required)
    run_id: str               # ULID (was job_id)
    calc_id: str
    status: str               # submitted, running, completed, failed, cancelled

    # Steps executed
    step_ids: list[str]

    # Timing (optional)
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None

    # Result (optional)
    exit_code: int | None = None
    log_path: str | None = None
    error: ErrorDTO | None = None

