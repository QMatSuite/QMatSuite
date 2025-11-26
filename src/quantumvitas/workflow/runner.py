"""
Workflow runner orchestrates step execution and verification.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from .workflow import Workflow
from .results import WorkflowResult, StepResultSummary
from .types import StepMode, StepStatus, StepType
from .verification import evaluate_step_result
from quantumvitas.engine.registry import EngineRegistry


class WorkflowRunner:
    """
    Execute workflow steps using the configured engine registry.
    """

    def __init__(self, engine_registry: EngineRegistry):
        self.engine_registry = engine_registry

    def run(self, workflow: Workflow) -> WorkflowResult:
        workflow.io.ensure()
        started = datetime.utcnow()
        step_summaries: List[StepResultSummary] = []
        status = StepStatus.SUCCESS

        for step in workflow.steps:
            engine = self.engine_registry.get(step.engine)
            raw_dir = workflow.raw_dir
            raw_dir.mkdir(parents=True, exist_ok=True)

            result = engine.run_step(step, working_dir=raw_dir)
            output_text = result.output_file.read_text() if result.output_file.exists() else ""
            step_mode = StepMode.STRICT if workflow.mode == StepMode.STRICT else step.mode

            step_status, message = evaluate_step_result(
                mode=step_mode,
                step_type=result.step_type,
                output_text=output_text,
                reference_file=step.reference_output,
            )
            summary = StepResultSummary(
                step_id=step.id,
                step_type=result.step_type,
                status=step_status,
                working_dir=raw_dir,
                input_file=result.input_file,
                output_file=result.output_file,
                reference_file=step.reference_output,
                message=message,
                metrics=getattr(result, "parsed_output", {}) or {},
            )
            step_summaries.append(summary)

            if step_status != StepStatus.SUCCESS:
                status = StepStatus.FAILED
                if workflow.mode == StepMode.STRICT:
                    break

        finished = datetime.utcnow()
        return WorkflowResult(
            workflow_id=workflow.id,
            mode=workflow.mode,
            steps=step_summaries,
            status=status,
            started_at=started,
            finished_at=finished,
        )

