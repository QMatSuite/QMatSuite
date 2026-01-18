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

# Import scan expansion modules
from quantumvitas.execution.scan_expansion import (
    collect_scan_dimensions,
    expand_variants,
    compute_variant_key,
    VariantAssignment,
)
from quantumvitas.execution.post_job import (
    PostJobContext,
    ArchiveToSlotAction,
    snapshot_raw_dir,
)
from quantumvitas.calculation.hash_utils import compute_step_sha


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
    pre_snapshot: Dict[str, float] = field(default_factory=dict)  # For scan archiving


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
            # Check for scan dimensions in this job
            scan_dimensions = self._collect_scan_dimensions_for_job(job, calculation)
            
            if not scan_dimensions:
                # No scans: execute job normally
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
            else:
                # Has scans: expand and execute variants
                logger.info(f"[EXECUTOR] Job {job.id} has scan dimensions, expanding variants")
                variants = expand_variants(scan_dimensions)
                logger.info(f"[EXECUTOR] Expanded to {len(variants)} variants")
                
                # Execute each variant
                variant_results: List[JobResult] = []
                for variant_assignments in variants:
                    variant_key = compute_variant_key(variant_assignments)
                    logger.info(f"[EXECUTOR] Executing variant {variant_key} for job {job.id}")
                    
                    # Check skip for this variant (using effective fingerprint)
                    should_skip_variant = self._should_skip_variant(
                        job,
                        variant_assignments,
                        manifest=manifest,
                        calculation=calculation,
                        is_target_job=(job.id == target_job_id),
                    )
                    
                    if should_skip_variant:
                        logger.info(f"[EXECUTOR] Variant {variant_key} SKIPPED")
                        variant_results.append(JobResult(
                            job_id=job.id,
                            success=True,
                            skipped=True,
                        ))
                        continue
                    
                    # Capture pre-snapshot for archiving
                    raw_dir = calculation.raw_dir
                    pre_snapshot = snapshot_raw_dir(raw_dir, exclude=["outdir", "scan"])
                    
                    # Execute job with variant assignments
                    variant_result = self._execute_job_with_variant(
                        job,
                        calculation,
                        variant_assignments,
                        variant_key,
                        run_id=run_id,
                    )
                    variant_result.pre_snapshot = pre_snapshot
                    variant_results.append(variant_result)
                    
                    # MVP failure policy: stop on first variant failure
                    if not variant_result.success:
                        logger.error(f"[EXECUTOR] Variant {variant_key} FAILED: {variant_result.error}")
                        execution_success = False
                        failed_job_id = job.id
                        # Add all variant results so far
                        results.extend(variant_results)
                        break
                
                # Add all variant results
                results.extend(variant_results)
                
                # If any variant failed, stop job-group
                if not execution_success:
                    break

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

    def _collect_scan_dimensions_for_job(
        self,
        job: Job,
        calculation: "Calculation",
    ) -> List[Any]:  # Returns List[ScanDimension] from scan_expansion
        """
        Collect scan dimensions for a job's steps.
        
        Args:
            job: Job to check
            calculation: Calculation context
            
        Returns:
            List of ScanDimensions, or empty list if no scans
        """
        # Load step documents for this job
        step_docs: Dict[str, dict] = {}
        calc_dir = calculation.dir
        steps_dir = calc_dir / "steps"
        
        for step_ulid in job.step_ids:
            # Try to find step file by ULID
            step_file = None
            if steps_dir.exists():
                for candidate in steps_dir.glob("*.step.yaml"):
                    try:
                        from quantumvitas.core.yamldoc import StepDoc
                        step_doc = StepDoc.load(candidate)
                        if step_doc.get(["meta", "id"]) == step_ulid:
                            step_file = candidate
                            break
                    except Exception:
                        continue
            
            if step_file and step_file.exists():
                try:
                    from quantumvitas.core.yamldoc import StepDoc
                    step_doc = StepDoc.load(step_file)
                    step_docs[step_ulid] = step_doc.to_dict()
                except Exception as e:
                    logger.debug(f"Failed to load step doc for {step_ulid}: {e}")
                    continue
        
        if not step_docs:
            return []
        
        # Collect scan dimensions
        try:
            dimensions = collect_scan_dimensions(job.step_ids, step_docs)
            return dimensions
        except Exception as e:
            logger.warning(f"Failed to collect scan dimensions for job {job.id}: {e}")
            return []
    
    def _should_skip_variant(
        self,
        job: Job,
        variant_assignments: List[VariantAssignment],
        *,
        manifest: Optional["RunManifest"],
        calculation: "Calculation",
        is_target_job: bool,
    ) -> bool:
        """
        Check if a variant can be skipped based on effective fingerprints.
        
        Args:
            job: Job being executed
            variant_assignments: Variant assignments for this variant
            manifest: Current manifest
            calculation: Calculation context
            is_target_job: Whether this is the target job
            
        Returns:
            True if variant should be skipped
        """
        # Target job variants must always run
        if is_target_job:
            return False
        
        # No manifest = can't skip
        if manifest is None:
            return False
        
        # Build variant_assignments dict for fingerprint computation
        variant_assignments_dict = {
            assignment.param_path: assignment.value
            for assignment in variant_assignments
        }
        
        # Check all steps in this job
        for step_ulid in job.step_ids:
            entry = self._get_manifest_entry_for_step(manifest, step_ulid)
            if entry is None:
                return False
            if not entry.done:
                return False
            
            # Compute effective fingerprint for this variant
            try:
                from quantumvitas.core.yamldoc import StepDoc
                step = self._find_step_by_ulid(calculation, step_ulid)
                if step is None:
                    return False
                
                # Find step file
                calc_dir = calculation.dir
                steps_dir = calc_dir / "steps"
                step_file = None
                if steps_dir.exists():
                    for candidate in steps_dir.glob("*.step.yaml"):
                        try:
                            step_doc = StepDoc.load(candidate)
                            if step_doc.get(["meta", "id"]) == step_ulid:
                                step_file = candidate
                                break
                        except Exception:
                            continue
                
                if not step_file or not step_file.exists():
                    return False
                
                step_doc = StepDoc.load(step_file)
                step_doc_dict = step_doc.to_dict()
                
                # Compute effective SHA with variant assignments
                effective_sha = compute_step_sha(step_doc_dict, variant_assignments_dict)
                
                # Compare with manifest entry
                if entry.step_sha != effective_sha:
                    return False
            except Exception as e:
                logger.debug(f"Failed to compute effective SHA for variant: {e}")
                return False
        
        return True
    
    def _execute_job_with_variant(
        self,
        job: Job,
        calculation: "Calculation",
        variant_assignments: List[VariantAssignment],
        variant_key: str,
        run_id: str,
    ) -> JobResult:
        """
        Execute a job with variant assignments (scan variant).
        
        Args:
            job: Job to execute
            calculation: Calculation context
            variant_assignments: Variant assignments
            variant_key: Variant key for archiving
            run_id: Run ID
            
        Returns:
            JobResult
        """
        # For now, we execute the job normally
        # In a full implementation, we would:
        # 1. Build effective step docs with resolved scan tokens
        # 2. Materialize inputs with resolved values
        # 3. Execute
        # 4. Run post-job archive action
        
        # Execute job (handler will use step docs as-is; materialization happens in handler)
        # TODO: In full implementation, we need to pass variant_assignments to handler
        # For MVP, we'll execute and then archive
        job_result = self._execute_job(job, calculation)
        
        # Run post-job archive action
        if job_result.success or not job_result.success:  # Always archive (best-effort)
            try:
                raw_dir = calculation.raw_dir
                context = PostJobContext(
                    calc_raw_dir=raw_dir,
                    variant_key=variant_key,
                    run_id=run_id,
                )
                
                archive_action = ArchiveToSlotAction(variant_key=variant_key)
                archive_action.execute(job_result, context)
            except Exception as e:
                logger.warning(f"Failed to archive variant {variant_key}: {e}")
        
        return job_result
    
    def _find_step_by_ulid(self, calculation: "Calculation", step_ulid: str) -> Optional["Step"]:
        """Find step in calculation by ULID."""
        for step in calculation.steps:
            if hasattr(step, 'meta') and step.meta.id == step_ulid:
                return step
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
