"""
Run result DTO.

This module provides DTOs for execution runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quantumvitas.api.types.base import BaseDTO
from quantumvitas.api.types.error import ErrorDTO


@dataclass
class RunResultDTO(BaseDTO):
    """
    Execution run result DTO.
    
    NOTE: Uses run_id (not job_id) for consistent ULID naming.
    """
    # Identity (required)
    run_ulid: str               # ULID (was job_id)
    calc_ulid: str
    status: str               # submitted, running, completed, failed, cancelled

    # Steps executed
    step_ulids: list[str]

    # Timing (optional)
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None

    # Result (optional)
    exit_code: int | None = None
    log_path: str | None = None
    error: ErrorDTO | None = None
    
    # Compatibility: store step details for historical CLI contract
    # This is a list of dicts with step_id, step_type, status, message, metrics
    _step_details: list[dict[str, Any]] | None = field(default=None, repr=False)
    
    # Compatibility: store io_dir, input_file, output_file for historical CLI contract
    io_dir: str | None = None
    input_file: str | None = None
    output_file: str | None = None
    
    @property
    def steps(self) -> list[Any]:
        """
        Compatibility property: return step objects with step_id, step_type, status, message, metrics.
        
        Returns a list of simple objects that have these attributes.
        """
        if self._step_details:
            # Return step-like objects from stored details
            return [StepResultCompat(**step_dict) for step_dict in self._step_details]
        
        # Fallback: create minimal step objects from step_ulids
        return [StepResultCompat(step_ulid=step_ulid) for step_ulid in self.step_ulids]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with compatibility properties."""
        result = super().to_dict()
        # Add steps property for compatibility (always include, even if empty)
        result["steps"] = [
            {
                "step_ulid": s.step_ulid,
                "step_type_spec": s.step_type_spec,
                "step_type_gen": s.step_type_gen,
                "status": s.status,
                "message": s.message,
                "metrics": s.metrics,
            }
            for s in self.steps
        ]
        # Legacy status mapping for frontend compatibility
        # Frontends (CLI/daemon) expect "SUCCESS" instead of "completed"
        legacy_status_map = {
            "completed": "SUCCESS",
            "failed": "FAILED",
            "running": "RUNNING",
            "submitted": "PENDING",
            "pending": "PENDING",
            "cancelled": "CANCELLED",
        }
        canonical_status = result.get("status", "").lower()
        result["status"] = legacy_status_map.get(canonical_status, result.get("status", "").upper())
        return result


class StepResultCompat:
    """Compatibility class for step results in RunResultDTO."""
    
    def __init__(self, step_ulid: str, step_type_spec: str | None = None, step_type_gen: str | None = None, status: str | None = None,
                 message: str | None = None, metrics: dict[str, Any] | None = None):
        self.step_ulid = step_ulid
        self.step_type_spec = step_type_spec
        self.step_type_gen = step_type_gen
        self.status = status
        self.message = message
        self.metrics = metrics or {}

