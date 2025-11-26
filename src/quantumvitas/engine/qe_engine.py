"""
Wrapper exposing the legacy QuantumEspressoEngine through the new Engine API.
"""

from __future__ import annotations

from pathlib import Path

from typing import Optional

from quantumvitas.core.engines.qe import QuantumEspressoEngine as _LegacyQeEngine
from quantumvitas.core.engines.base import EngineConfig

from .base import Engine, StepResult


class QeEngine(Engine):
    """
    Thin adapter over the legacy QuantumEspressoEngine.

    For now we expect ``step.parameters`` to contain an ``input_file`` entry
    (absolute or relative to the workflow raw directory). Future iterations
    can add high-level builders that translate Step parameters into QEInput
    objects.
    """

    name = "qe"

    def __init__(self, config: Optional[EngineConfig] = None):
        super().__init__(config or EngineConfig(name="qe"))
        self._engine = _LegacyQeEngine(self.config)

    def run_step(self, step, working_dir: Path) -> StepResult:
        working_dir.mkdir(parents=True, exist_ok=True)
        input_file = step.parameters.get("input_file")
        if not input_file:
            raise ValueError(f"Step '{step.id}' is missing 'input_file' parameter")

        input_path = Path(input_file)
        if not input_path.is_absolute():
            input_path = working_dir / input_path
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        timeout = step.parameters.get("timeout")
        return self._engine.run_step(
            input_file=input_path,
            working_dir=working_dir,
            step_type=step.type.value,
            timeout=timeout,
        )

