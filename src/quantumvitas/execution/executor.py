"""
JobGraph Executor: Executes jobs from a materialized JobGraph.

This module provides the execution layer that processes JobGraph
jobs in order, respecting selection mode and incremental skip logic.

Per engine_recipes_jobgraph_plan.md (Constitution):
- One pipeline for Run Calc and Run Step (selection determines scope)
- Target step MUST run in TARGET mode
- Manifest is the only persisted run tracking truth
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from quantumvitas.execution.job_graph import Job, JobGraph, SelectionMode

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.calculation.manifest import ManifestStepEntry, RunManifest
    from quantumvitas.calculation.step import Step


logger = logging.getLogger(__name__)


@dataclass
class JobResult:
    """Result of executing a single job."""

    job_id: str
    success: bool
    skipped: bool = False
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    step_results: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of executing a JobGraph."""

    success: bool
    job_results: List[JobResult] = field(default_factory=list)
    failed_job_id: Optional[str] = None


class JobExecutor:
    """
    Executes jobs from a JobGraph.

    The executor is engine-agnostic at the orchestration level.
    Engine-specific execution is delegated to handler functions.
    """

    def __init__(
        self,
        engine_handlers: Optional[Dict[str, Callable[[Job, "Calculation"], JobResult]]] = None,
    ):
        """
        Initialize executor.

        Args:
            engine_handlers: Map of engine name to handler function.
                Handler signature: (job, calculation) -> JobResult
        """
        self.engine_handlers = engine_handlers or {}

    def execute(
        self,
        job_graph: JobGraph,
        calculation: "Calculation",
        selection: SelectionMode = SelectionMode.ALL,
        target_step_id: Optional[str] = None,
        manifest: Optional["RunManifest"] = None,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """
        Execute jobs from a JobGraph.

        Args:
            job_graph: The materialized JobGraph
            calculation: Calculation context
            selection: Selection mode (ALL for Run Calc, TARGET for Run Step)
            target_step_id: Required when selection=TARGET
            manifest: Optional manifest for incremental skip logic
            step_shas: Optional step SHA map for fingerprint comparison

        Returns:
            ExecutionResult with success status and per-job results
        """
        # Get jobs to execute based on selection mode
        if selection == SelectionMode.TARGET:
            if target_step_id is None:
                raise ValueError("target_step_id required for TARGET selection mode")
            jobs_to_execute = job_graph.get_jobs_for_target(target_step_id, selection)
        else:
            jobs_to_execute = list(job_graph.jobs)

        if not jobs_to_execute:
            logger.warning("[EXECUTOR] No jobs to execute")
            return ExecutionResult(success=True, job_results=[])

        results: List[JobResult] = []
        execution_success = True
        failed_job_id = None

        # Determine which job contains the target step (for "target must run" rule)
        target_job_id = None
        if selection == SelectionMode.TARGET and target_step_id:
            target_job = job_graph.get_job_by_step_id(target_step_id)
            if target_job:
                target_job_id = target_job.id

        for job in jobs_to_execute:
            # Check if job can be skipped (incremental logic)
            should_skip = self._should_skip_job(
                job,
                manifest=manifest,
                step_shas=step_shas,
                is_target_job=(job.id == target_job_id),
            )

            if should_skip:
                logger.info(f"[EXECUTOR] Job {job.id} SKIPPED (already done, inputs unchanged)")
                results.append(JobResult(
                    job_id=job.id,
                    success=True,
                    skipped=True,
                ))
                continue

            # Execute the job
            logger.info(f"[EXECUTOR] Executing job {job.id} (engine={job.engine})")
            job_result = self._execute_job(job, calculation)
            results.append(job_result)

            if not job_result.success:
                execution_success = False
                failed_job_id = job.id
                logger.error(f"[EXECUTOR] Job {job.id} FAILED: {job_result.error}")
                break  # Stop on first failure

        return ExecutionResult(
            success=execution_success,
            job_results=results,
            failed_job_id=failed_job_id,
        )

    def _should_skip_job(
        self,
        job: Job,
        *,
        manifest: Optional["RunManifest"],
        step_shas: Optional[Dict[str, str]],
        is_target_job: bool,
    ) -> bool:
        """
        Determine if a job can be skipped.

        Per Constitution:
        - Target step MUST run in TARGET mode (never skip target job)
        - Non-target jobs can be skipped if all steps have:
          - done=True in manifest
          - matching fingerprints
        """
        # Target job must always run
        if is_target_job:
            return False

        # No manifest = can't skip
        if manifest is None:
            return False

        # Check all steps in this job
        for step_id in job.step_ids:
            entry = self._get_manifest_entry_for_step(manifest, step_id)
            if entry is None:
                return False
            if not entry.done:
                return False

            # Check fingerprint if we have step SHAs
            if step_shas:
                current_sha = step_shas.get(step_id)
                if current_sha and entry.step_sha != current_sha:
                    return False

        return True

    def _get_manifest_entry_for_step(
        self, manifest: "RunManifest", step_id: str
    ) -> Optional["ManifestStepEntry"]:
        """Find manifest entry for a step by ULID."""
        for entry in manifest.steps:
            if entry.step_ulid == step_id:
                return entry
        return None

    def _execute_job(self, job: Job, calculation: "Calculation") -> JobResult:
        """
        Execute a single job.

        Delegates to engine-specific handler if registered.
        """
        started = datetime.now(timezone.utc)

        engine = job.engine
        if engine is None:
            return JobResult(
                job_id=job.id,
                success=False,
                error="Job has no engine specified",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        handler = self.engine_handlers.get(engine)
        if handler is None:
            # No handler registered - return placeholder result
            # In a real integration, this would call the actual engine
            logger.warning(f"[EXECUTOR] No handler for engine '{engine}', job {job.id} not executed")
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"No handler registered for engine '{engine}'",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        try:
            result = handler(job, calculation)
            result.started_at = started
            result.finished_at = datetime.now(timezone.utc)
            return result
        except Exception as e:
            logger.exception(f"[EXECUTOR] Error executing job {job.id}")
            return JobResult(
                job_id=job.id,
                success=False,
                error=str(e),
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )


def create_executor_with_default_handlers() -> JobExecutor:
    """
    Create an executor with default engine handlers.

    This is a factory that sets up handlers for QE, ORCA, and PySCF.
    The actual implementation will call the existing engine code.

    Returns:
        Configured JobExecutor
    """
    # For now, return executor without handlers
    # Full integration will add handlers that call existing engine code
    return JobExecutor(engine_handlers={})
