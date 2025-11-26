"""
Step definitions used by workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from quantumvitas.engine.base import Engine, StepResult
from quantumvitas.project.model import StructureRef

from .input_runner import run_input_step
from .types import StepMode, StepType


@dataclass(slots=True)
class Step:
    """
    One unit of execution inside a workflow.
    """

    id: str
    input_file: Path
    engine: str = "qe"
    step_type: Optional[StepType] = None
    options: Dict[str, object] = field(default_factory=dict)
    mode: StepMode = StepMode.NORMAL
    reference_output: Optional[Path] = None
    structure: Optional[StructureRef] = None

    def resolve_input_path(self, workflow_raw_dir: Path) -> Path:
        path = Path(self.input_file)
        if not path.is_absolute():
            path = (workflow_raw_dir / path).resolve()
        return path

    def run(
        self,
        engine: Engine,
        workflow_raw_dir: Path,
        project_root: Path,
    ) -> StepResult:
        """
        Execute the step using the provided engine inside the workflow raw dir.
        """
        if engine.name != "qe":
            return engine.run_step(self, workflow_raw_dir)

        from quantumvitas.engine.qe_engine import QeEngine

        if not isinstance(engine, QeEngine):
            raise TypeError("QE steps require QeEngine instances")

        input_path = self.resolve_input_path(workflow_raw_dir)
        step_type_value = self.step_type.value if self.step_type else None
        timeout = self.options.get("timeout")

        result, _ = run_input_step(
            engine=engine.backend,
            input_file=input_path,
            working_dir=workflow_raw_dir,
            project_root=project_root,
            step_type=step_type_value,
            timeout=timeout,
        )
        return result

