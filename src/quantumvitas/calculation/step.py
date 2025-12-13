"""
Step definitions used by calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from quantumvitas.core.resources import ResourceMeta
from quantumvitas.engine.base import Engine, StepResult
from quantumvitas.project.model import StructureRef

from .input_runner import run_input_step
from .types import StepMode, StepType


@dataclass(slots=True)
class Step:
    """
    One unit of execution inside a calculation.
    """

    meta: ResourceMeta
    input_file: Path
    engine: str = "qe"
    step_type: Optional[StepType] = None
    options: Dict[str, object] = field(default_factory=dict)
    mode: StepMode = StepMode.NORMAL
    reference_output: Optional[Path] = None
    structure: Optional[StructureRef] = None

    @property
    def id(self) -> str:
        """
        Legacy identifier accessor (maps to the slug inside ``meta``).
        """
        return self.meta.slug

    def resolve_input_path(self, calculation_raw_dir: Path) -> Path:
        path = Path(self.input_file)
        if not path.is_absolute():
            path = (calculation_raw_dir / path).resolve()
        return path

    def run(
        self,
        engine: Engine,
        calculation_raw_dir: Path,
        project_root: Path,
    ) -> StepResult:
        """
        Execute the step using the provided engine inside the calculation raw dir.
        """
        if engine.name != "qe":
            return engine.run_step(self, calculation_raw_dir)

        from quantumvitas.engine.qe_engine import QeEngine

        if not isinstance(engine, QeEngine):
            raise TypeError("QE steps require QeEngine instances")

        input_path = self.resolve_input_path(calculation_raw_dir)
        step_type_value = self.step_type.value if self.step_type else None
        timeout = self.options.get("timeout")

        result, _ = run_input_step(
            engine=engine.backend,
            input_file=input_path,
            working_dir=calculation_raw_dir,
            project_root=project_root,
            step_type=step_type_value,
            timeout=timeout,
        )
        return result

