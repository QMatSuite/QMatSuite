"""
Workflow runner orchestrates step execution and verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .workflow import Workflow
from .results import WorkflowResult, StepResultSummary
from .types import StepMode, StepStatus, StepType
from .verification import evaluate_step_result
from quantumvitas.engine.registry import EngineRegistry


def _coerce_step_type(value) -> StepType:
    if isinstance(value, StepType):
        return value
    try:
        return StepType(value)
    except Exception:
        return StepType.CUSTOM


class WorkflowRunner:
    """
    Execute workflow steps using the configured engine registry.
    """

    def __init__(self, engine_registry: EngineRegistry):
        self.engine_registry = engine_registry

    def run(self, workflow: Workflow) -> WorkflowResult:
        workflow.io.ensure()
        started = datetime.now(timezone.utc)
        step_summaries: List[StepResultSummary] = []
        status = StepStatus.SUCCESS
        workflow_failed = False

        for step in workflow.steps:
            # If a previous step failed in strict mode, mark remaining steps as SKIPPED
            if workflow_failed:
                step_type = _coerce_step_type(step.step_type) if step.step_type else StepType.CUSTOM
                summary = StepResultSummary(
                    step_id=step.id,
                    step_type=step_type,
                    status=StepStatus.SKIPPED,
                    working_dir=workflow.raw_dir,
                    input_file=step.input_file if hasattr(step, 'input_file') else Path(),
                    output_file=Path(),
                    reference_file=step.reference_output,
                    message="Step skipped because a previous step failed",
                    metrics={},
                )
                step_summaries.append(summary)
                continue

            engine = self.engine_registry.get(step.engine)
            raw_dir = workflow.raw_dir
            raw_dir.mkdir(parents=True, exist_ok=True)

            result = step.run(
                engine=engine,
                workflow_raw_dir=raw_dir,
                project_root=workflow.project.root,
            )
            output_text = ""
            if result.output_file and result.output_file.exists():
                output_text = result.output_file.read_text()
            step_mode = StepMode.STRICT if workflow.mode == StepMode.STRICT else step.mode

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
                workflow_failed = True
                if workflow.mode == StepMode.STRICT:
                    # In strict mode, stop execution and mark remaining steps as SKIPPED
                    break

        finished = datetime.now(timezone.utc)
        return WorkflowResult(
            workflow_id=workflow.id,
            mode=workflow.mode,
            steps=step_summaries,
            status=status,
            started_at=started,
            finished_at=finished,
        )

