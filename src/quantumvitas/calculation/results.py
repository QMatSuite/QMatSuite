"""
Structured calculation results for reporting and analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .types import StepMode, StepStatus


@dataclass(slots=True)
class StepResultSummary:
    step_ulid: str  # ULID (was step_id)
    step_type_spec: str  # SPEC type (was step_type)
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
    calculation_ulid: str  # ULID (was calculation_id)
    mode: StepMode
    steps: List[StepResultSummary]
    status: StepStatus
    started_at: datetime
    finished_at: datetime
    io_dir: Optional[Path] = None  # The actual I/O directory used by the runner (source of truth)
    run_ulid: Optional[str] = None  # History run ULID (for linking to project history)

    def to_dict(self) -> Dict[str, object]:
        result = {
            "calculation_ulid": self.calculation_ulid,
            "mode": self.mode.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "steps": [
                {
                    "step_ulid": step.step_ulid,
                    "step_type_spec": step.step_type_spec,
                    "status": step.status.value,
                    "working_dir": str(step.working_dir),
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
        # Include run_ulid for history reference
        if self.run_ulid:
            result["run_ulid"] = self.run_ulid
        return result

