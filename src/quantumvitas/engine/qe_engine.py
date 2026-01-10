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
    """

    name = "qe"

    def __init__(self, config: Optional[EngineConfig] = None):
        super().__init__(config or EngineConfig(name="qe"))
        self._engine = _LegacyQeEngine(self.config)

    @property
    def backend(self) -> _LegacyQeEngine:
        return self._engine

    def run_step(self, step, working_dir: Path) -> StepResult:
        working_dir.mkdir(parents=True, exist_ok=True)
        timeout = None
        step_type_value = None

        if hasattr(step, "resolve_input_path"):
            input_path = step.resolve_input_path(working_dir)
            step_type = getattr(step, "step_type", None)
            if step_type:
                step_type_value = step_type.value
            elif hasattr(step, "type"):
                step_type_value = getattr(step, "type")
            options = getattr(step, "options", {})
            timeout = options.get("timeout")
        else:
            params = getattr(step, "parameters", {})
            input_file = params.get("input_file")
            if not input_file:
                step_slug = getattr(getattr(step, "meta", None), "slug", "unknown")
                raise ValueError(f"Step '{step_slug}' is missing 'input_file' parameter")
            input_path = Path(input_file)
            if not input_path.is_absolute():
                input_path = working_dir / input_path
            timeout = params.get("timeout")
            if hasattr(step, "type"):
                step_type_value = step.type.value

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        return self._engine.run_step(
            input_file=input_path,
            working_dir=working_dir,
            step_type=step_type_value,
            timeout=timeout,
        )

