"""
Step definitions used by workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .types import StepMode, StepType
from quantumvitas.project.model import StructureRef


@dataclass(slots=True)
class Step:
    """
    One unit of execution inside a workflow.
    """

    id: str
    type: StepType
    engine: str = "qe"
    structure: Optional[StructureRef] = None
    parameters: Dict[str, object] = field(default_factory=dict)
    mode: StepMode = StepMode.NORMAL
    reference_output: Optional[Path] = None

    def with_mode(self, workflow_mode: StepMode) -> "Step":
        """
        Resolve the effective mode for the step (workflow mode overrides step mode).
        """
        resolved_mode = self.mode
        if workflow_mode == StepMode.STRICT:
            resolved_mode = StepMode.STRICT
        return Step(
            id=self.id,
            type=self.type,
            engine=self.engine,
            structure=self.structure,
            parameters=dict(self.parameters),
            mode=resolved_mode,
            reference_output=self.reference_output,
        )

