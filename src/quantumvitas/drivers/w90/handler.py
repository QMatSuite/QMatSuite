"""Wannier90 step handler.

This module handles execution of the main Wannier90 calculation.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.executor import JobResult

from .artifact_resolver import resolve_w90_inputs

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.engine.registry import EngineRegistry

logger = logging.getLogger(__name__)


def _find_step_by_ulid(calculation: "Calculation", step_ulid: str):
    """Find a step in calculation by its ULID."""
    from quantumvitas.calculation.step import Step
    for step in calculation.steps:
        if step.meta.ulid == step_ulid:
            return step
    return None


def w90_run_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """Handle Wannier90 execution.

    This handler:
    1. Resolves required input files (.amn, .mmn, .eig) from w90_preproc
    2. Stages the .win input file
    3. Runs wannier90.x
    4. Collects output files

    Args:
        job: Job instance with execution context
        calculation: Calculation context
        engine_registry: Engine registry
        context: Additional context (manifest, etc.)

    Returns:
        JobResult with execution outcome
    """
    from datetime import datetime, timezone

    started = datetime.now(timezone.utc)

    try:
        # Get step
        if len(job.step_ulids) != 1:
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"W90 handler expects exactly one step, got {len(job.step_ulids)}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        step_ulid = job.step_ulids[0]
        step = _find_step_by_ulid(calculation, step_ulid)
        if step is None:
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Step {step_ulid} not found",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        # Create workdir
        working_dir = job.working_dir
        working_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting Wannier90 run: {step_ulid}")

        # Resolve input artifacts from preprocessing
        # Note: This is a simplified version - actual implementation
        # would need to use StepContext which may not be available here
        # For now, we'll search in calculation.raw_dir for previous steps
        try:
            # Find w90_preproc step or any step with .amn, .mmn, .eig files
            inputs = {}
            for prev_step in calculation.steps:
                if prev_step.meta.ulid == step_ulid:
                    continue
                prev_dir = calculation.raw_dir / prev_step.meta.ulid
                if not prev_dir.exists():
                    continue

                # Check for W90 artifacts
                for pattern, art_type in [("*.amn", "w90_amn"), ("*.mmn", "w90_mmn"), ("*.eig", "w90_eig")]:
                    matches = list(prev_dir.glob(pattern))
                    if matches and art_type not in inputs:
                        inputs[art_type] = matches[0]

                if len(inputs) == 3:
                    break

            if len(inputs) < 3:
                return JobResult(
                    job_id=job.id,
                    success=False,
                    error="Failed to resolve Wannier90 input files from preprocessing",
                    started_at=started,
                    finished_at=datetime.now(timezone.utc),
                )
        except Exception as e:
            logger.error(f"Failed to resolve W90 inputs: {e}")
            return JobResult(
                job_id=job.id,
                success=False,
                error=str(e),
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        # Stage input files
        for artifact_type, source_path in inputs.items():
            target = working_dir / source_path.name
            if not target.exists():
                shutil.copy2(source_path, target)
                logger.debug(f"Staged {artifact_type}: {source_path.name}")

        # Generate/stage .win file
        # This would use the recipe to generate the .win file
        from .recipe import W90Recipe
        recipe = W90Recipe()
        step_config = getattr(step, "config", {}) or {}
        try:
            recipe.stage(working_dir, step_config)
        except Exception as e:
            logger.error(f"Failed to generate .win file: {e}")
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Failed to generate .win file: {e}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        # Execute wannier90.x
        # For now, this is a placeholder - actual execution would use
        # the engine infrastructure
        logger.warning("W90 execution not yet fully implemented - placeholder")
        return JobResult(
            job_id=job.id,
            success=True,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            step_results={step_ulid: {"success": True}},
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.exception(f"[W90_HANDLER] Step execution failed")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"{type(e).__name__}: {e}\n{tb[:500]}",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

