"""
Calculation runner orchestrates step execution and verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .calculation import Calculation
from .results import CalculationResult, StepResultSummary
from .types import StepMode, StepStatus, StepType
from .verification import evaluate_step_result
from quantumvitas.engine.registry import EngineRegistry


def compute_io_dir_from_calculation_model(calculation_dir: Path, working_dir_name: Optional[str] = None) -> Path:
    """
    Compute the I/O directory path from calculation model/context.
    
    This is the SINGLE SOURCE OF TRUTH for determining the I/O directory.
    Both the server (for pending jobs) and runner (for execution) use this function.
    
    Args:
        calculation_dir: Path to the calculation directory (containing calculation.yaml)
        working_dir_name: Name of the working directory subdirectory (from calculation.working_dir).
                         If None, defaults to "raw" (the convention for local runner).
    
    Returns:
        Absolute Path to the I/O directory (the actual directory used by the runner
        to write QE input/output and artifacts).
    
    Note:
        This function encapsulates the default "raw" convention. If the runner's
        I/O directory policy changes in the future, only this function needs to be updated.
    """
    # Default to "raw" if not specified (local runner convention)
    # This is the ONLY place that knows the "raw" default
    subdir = working_dir_name or "raw"
    io_dir = (calculation_dir / subdir).resolve()
    return io_dir


def _coerce_step_type(value) -> StepType:
    if isinstance(value, StepType):
        return value
    try:
        return StepType(value)
    except Exception:
        return StepType.CUSTOM


class CalculationRunner:
    """
    Execute calculation steps using the configured engine registry.
    """

    def __init__(self, engine_registry: EngineRegistry):
        self.engine_registry = engine_registry

    def run(self, calculation: Calculation) -> CalculationResult:
        calculation.io.ensure()
        started = datetime.now(timezone.utc)
        step_summaries: List[StepResultSummary] = []
        status = StepStatus.SUCCESS
        calculation_failed = False

        for step in calculation.steps:
            # If a previous step failed in strict mode, mark remaining steps as SKIPPED
            if calculation_failed:
                step_type = _coerce_step_type(step.step_type) if step.step_type else StepType.CUSTOM
                summary = StepResultSummary(
                    step_id=step.id,
                    step_type=step_type,
                    status=StepStatus.SKIPPED,
                    working_dir=calculation.raw_dir,
                    input_file=step.input_file if hasattr(step, 'input_file') else Path(),
                    output_file=Path(),
                    reference_file=step.reference_output,
                    message="Step skipped because a previous step failed",
                    metrics={},
                )
                step_summaries.append(summary)
                continue

            engine = self.engine_registry.get(step.engine)
            # Use compute_io_dir_from_calculation_model to ensure consistency with server-side planned_io_dir
            # calculation.raw_dir uses the same logic (calculation_dir / working_dir, default "raw")
            raw_dir = calculation.raw_dir
            raw_dir.mkdir(parents=True, exist_ok=True)

            result = step.run(
                engine=engine,
                calculation_raw_dir=raw_dir,
                project_root=calculation.project.root,
            )
            output_text = ""
            if result.output_file and result.output_file.exists():
                output_text = result.output_file.read_text()
            step_mode = StepMode.STRICT if calculation.mode == StepMode.STRICT else step.mode

            step_type = _coerce_step_type(result.step_type)
            step_status, message, metrics = evaluate_step_result(
                mode=step_mode,
                step_type=step_type,
                output_text=output_text,
                reference_file=step.reference_output,
            )
            combined_metrics = dict(getattr(result, "parsed_output", {}) or {})
            for key, value in (metrics or {}).items():
                if value is not None:
                    combined_metrics[key] = value
            summary = StepResultSummary(
                step_id=step.id,
                step_type=step_type,
                status=step_status,
                working_dir=raw_dir,
                input_file=result.input_file,
                output_file=result.output_file,
                reference_file=step.reference_output,
                message=message,
                metrics=combined_metrics,
            )
            step_summaries.append(summary)

            if step_status != StepStatus.SUCCESS:
                status = StepStatus.FAILED
                calculation_failed = True
                if calculation.mode == StepMode.STRICT:
                    # In strict mode, stop execution and mark remaining steps as SKIPPED
                    break

        finished = datetime.now(timezone.utc)
        # Get the actual I/O directory used by the runner (source of truth)
        io_dir = calculation.raw_dir.resolve() if calculation.raw_dir else None
        return CalculationResult(
            calculation_id=calculation.id,
            mode=calculation.mode,
            steps=step_summaries,
            status=status,
            started_at=started,
            finished_at=finished,
            io_dir=io_dir,  # The actual I/O directory used by the runner
        )

