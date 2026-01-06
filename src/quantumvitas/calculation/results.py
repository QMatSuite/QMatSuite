"""
Structured calculation results for reporting and analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .types import StepMode, StepStatus, StepType


@dataclass(slots=True)
class StepResultSummary:
    step_id: str
    step_type: StepType
    status: StepStatus
    working_dir: Path
    input_file: Path
    output_file: Path
    reference_file: Optional[Path]
    message: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)
    produced_structure_ulid: Optional[str] = None  # ULID of structure created from this step (if any)


@dataclass(slots=True)
class CalculationResult:
    calculation_id: str
    mode: StepMode
    steps: List[StepResultSummary]
    status: StepStatus
    started_at: datetime
    finished_at: datetime
    io_dir: Optional[Path] = None  # The actual I/O directory used by the runner (source of truth)
    run_id: Optional[str] = None  # History run ULID (for linking to project history)

    def to_dict(self) -> Dict[str, object]:
        result = {
            "calculation_id": self.calculation_id,
            "mode": self.mode.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "steps": [
                {
                    "step_id": step.step_id,
                    "step_type": step.step_type.value,
                    "status": step.status.value,
                    "working_dir": str(step.working_dir),  # Keep for backward compat in step summaries
                    "input_file": str(step.input_file),
                    "output_file": str(step.output_file),
                    "reference_file": str(step.reference_file) if step.reference_file else None,
                    "message": step.message,
                    "metrics": step.metrics,
                    "produced_structure_ulid": step.produced_structure_ulid,
                }
                for step in self.steps
            ],
        }
        # Include io_dir if available (runner is source of truth)
        if self.io_dir:
            result["io_dir"] = str(self.io_dir.resolve())
        # Include run_id for history reference
        if self.run_id:
            result["run_id"] = self.run_id
        return result

