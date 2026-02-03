"""QMCPACK step handler.

This module contains the main handler for QMCPACK step execution.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.executor import JobResult

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.engine.registry import EngineRegistry

logger = logging.getLogger(__name__)


def _find_step_by_ulid(calculation: "Calculation", step_ulid: str):
    """Find a step in calculation by its ULID."""
    for step in calculation.steps:
        if step.meta.ulid == step_ulid:
            return step
    return None


def qmcpack_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a single QMCPACK step job.

    This handler:
    1. Creates workdir (isolated per step)
    2. Materializes inputs (qmc_input.xml, wavefunction, pseudopotentials)
    3. Executes QMCPACK

    Args:
        job: The Job to execute (single step)
        calculation: Calculation context
        engine_registry: Engine registry
        context: Additional context (manifest, etc.)

    Returns:
        JobResult with execution status
    """
    from datetime import datetime, timezone

    started = datetime.now(timezone.utc)

    try:
        # Get step
        if len(job.step_ulids) != 1:
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"QMCPACK handler expects exactly one step, got {len(job.step_ulids)}",
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

        # Get engine
        engine = engine_registry.get("qmcpack")
        if engine is None:
            return JobResult(
                job_id=job.id,
                success=False,
                error="QMCPACK engine not found in registry",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        # Create workdir (QMCPACK uses isolated workdir per step)
        working_dir = job.working_dir
        working_dir.mkdir(parents=True, exist_ok=True)

        step_type = job.metadata.get("step_type_spec", "unknown")
        gen_type = job.metadata.get("step_type_gen", "unknown")
        logger.info(f"[QMCPACK] step_ulid={step_ulid}, step_type_spec={step_type}, gen={gen_type}")

        # Load step spec to get parameters
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        from quantumvitas.core.resolution import require_step

        try:
            calc_ref = None
            for wf_ref in calculation.project.calculations.values():
                if wf_ref.absolute_path == calculation.dir:
                    calc_ref = wf_ref
                    break

            calc_selector = calc_ref.meta.slug if calc_ref else calculation.dir.name
            step_resolved = require_step(calculation.project.root, calc_selector, step_ulid)
            step_spec = StructureStepSpec.from_yaml(step_resolved.absolute_path)
        except Exception as e:
            logger.error(f"[QMCPACK] Failed to load step spec for {step_ulid}: {e}")
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Failed to load step spec: {e}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        # Materialize inputs
        try:
            engine.materialize_inputs(step_spec, working_dir, calculation)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"[QMCPACK] Failed to materialize inputs for step {step_ulid}: {e}")
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Failed to materialize inputs: {e}\n{tb[:500]}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        # Execute QMCPACK
        try:
            result = engine.run_step(step_spec, working_dir, calculation)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.exception(f"[QMCPACK] Step {step_ulid} execution failed")
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"{type(e).__name__}: {e}\n{tb[:500]}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )

        success = result.success if hasattr(result, "success") else False
        error_msg = result.error if hasattr(result, "error") and not success else None

        # Verify expected output artifacts exist
        if success:
            scalar_files = list(working_dir.glob("*.scalar.dat"))
            if not scalar_files:
                success = False
                error_msg = f"QMCPACK completed but no scalar.dat files found in {working_dir}"
                logger.error(f"[QMCPACK] {error_msg}")

        step_result_data = {
            "success": success,
            "working_dir": str(working_dir),
            "return_code": getattr(result, "return_code", None),
        }

        return JobResult(
            job_id=job.id,
            success=success,
            error=error_msg,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            step_results={step_ulid: step_result_data},
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.exception("[QMCPACK] Step execution failed")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"{type(e).__name__}: {e}\n{tb[:500]}",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )
