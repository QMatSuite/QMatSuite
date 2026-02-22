"""
Wrapper exposing the legacy QuantumEspressoEngine through the new Engine API.
"""

from __future__ import annotations

from pathlib import Path

from typing import Optional

from qmatsuite.core.public import QuantumEspressoEngine as _LegacyQeEngine, EngineConfig

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
    def supported_presets(self) -> list[str]:
        """
        QE engine supports PW-based preset dimensions.
        
        Returns:
            List of supported preset dimensions: precision, magnetism, occupations_scheme, convergence
        """
        return ["precision", "magnetism", "occupations_scheme", "convergence"]

    @property
    def backend(self) -> _LegacyQeEngine:
        return self._engine

    def run_step(self, step_or_input, working_dir: Path | None = None) -> StepResult:
        from qmatsuite.engine.engine_input import EngineInput

        if isinstance(step_or_input, EngineInput):
            ei = step_or_input
            wd = ei.working_dir
            wd.mkdir(parents=True, exist_ok=True)
            input_path = ei.materialized_inputs.get("input_file")
            if input_path is None:
                raise ValueError("EngineInput missing 'input_file' in materialized_inputs")
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")
            return self._engine.run_step(
                input_file=input_path,
                working_dir=wd,
                step_type_spec=ei.step_type_spec,
                timeout=ei.parameters.get("timeout"),
            )

        # Legacy path
        step = step_or_input
        if working_dir is None:
            raise ValueError("working_dir is required for legacy step objects")
        working_dir.mkdir(parents=True, exist_ok=True)
        timeout = None
        step_type_value = None

        if hasattr(step, "resolve_input_path"):
            input_path = step.resolve_input_path(working_dir)
            step_type = getattr(step, "step_type_spec", None)
            if step_type:
                step_type_value = step_type
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
                step_type_value = step.type  # Already a string

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        return self._engine.run_step(
            input_file=input_path,
            working_dir=working_dir,
            step_type_spec=step_type_value,
            timeout=timeout,
        )

