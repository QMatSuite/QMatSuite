"""
Structured workflow results for reporting and analysis.
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


@dataclass(slots=True)
class WorkflowResult:
    workflow_id: str
    mode: StepMode
    steps: List[StepResultSummary]
    status: StepStatus
    started_at: datetime
    finished_at: datetime

    def to_dict(self) -> Dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "mode": self.mode.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "steps": [
                {
                    "step_id": step.step_id,
                    "step_type": step.step_type.value,
                    "status": step.status.value,
                    "working_dir": str(step.working_dir),
                    "input_file": str(step.input_file),
                    "output_file": str(step.output_file),
                    "reference_file": str(step.reference_file) if step.reference_file else None,
                    "message": step.message,
                    "metrics": step.metrics,
                }
                for step in self.steps
            ],
        }

