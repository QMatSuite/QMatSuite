"""
Engine Handlers: Bridge between JobExecutor and existing engine execution logic.

These handlers wrap the existing step.run() and chain execution code,
adapting them to the Job-based execution model.

Per engine_recipes_jobgraph_plan.md (Constitution):
- Preserve existing filesystem contracts
- QE: raw/outdir unchanged
- Wannier: raw in-place unchanged
- QC: raw/scf_<suffix>/ unchanged
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.executor import JobResult

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.calculation.step import Step
    from quantumvitas.engine.registry import EngineRegistry


logger = logging.getLogger(__name__)


# Handler type signature
HandlerFunc = Callable[[Job, "Calculation", "EngineRegistry", Dict[str, Any]], JobResult]


def qe_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a single QE/Wannier step job.

    This handler wraps the existing step.run() logic for QE-family engines.
    One job = one step for QE-Recipe.

    Args:
        job: The Job to execute (single step)
        calculation: Calculation context
        engine_registry: Engine registry for engine lookup
        context: Additional context (run_id, run_mode, etc.)

    Returns:
        JobResult with execution status
    """
    if len(job.step_ids) != 1:
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"QE handler expects single-step job, got {len(job.step_ids)} steps",
        )

    step_ulid = job.step_ids[0]

    # Find the step in calculation
    step = _find_step_by_ulid(calculation, step_ulid)
    if step is None:
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Step {step_ulid} not found in calculation",
        )

    # Get engine
    engine_name = job.engine or "qe"
    try:
        engine = engine_registry.get(engine_name)
    except Exception as e:
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Failed to get engine '{engine_name}': {e}",
        )

    # Prepare execution context
    raw_dir = job.working_dir
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Create per-step artifact directory (Phase 3C contract)
    step_artifacts_dir = raw_dir / "step_artifacts" / step_ulid
    step_artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Clear step artifacts (keep only newest results)
    import shutil
    if step_artifacts_dir.exists():
        for item in step_artifacts_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

    # Inject options
    if not hasattr(step, "options") or step.options is None:
        step.options = {}
    step.options["run_mode"] = context.get("run_mode", "incremental")
    step.options["step_artifacts_dir"] = str(step_artifacts_dir)

    # Execute step
    try:
        result = step.run(
            engine=engine,
            calculation_raw_dir=raw_dir,
            project_root=calculation.project.root,
            species_map=calculation.species_map,
        )

        success = result.success if hasattr(result, "success") else False
        error_msg = result.error if hasattr(result, "error") and not success else None

        return JobResult(
            job_id=job.id,
            success=success,
            error=error_msg,
            step_results={
                step_ulid: {
                    "success": success,
                    "output_file": str(result.output_file) if result.output_file else None,
                    "return_code": getattr(result, "return_code", None),
                }
            },
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.exception(f"[QE_HANDLER] Step {step_ulid} execution failed")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"{type(e).__name__}: {e}\n{tb[:500]}",
        )


def pyscf_chain_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a PySCF chain job (SCF + post-SCF steps in one session).

    This handler delegates to the existing PySCF chain execution logic.

    Args:
        job: The Job to execute (multi-step chain)
        calculation: Calculation context
        engine_registry: Engine registry
        context: Additional context

    Returns:
        JobResult with execution status
    """
    try:
        engine = engine_registry.get("pyscf")
    except Exception as e:
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Failed to get PySCF engine: {e}",
        )

    # Get the steps in this chain
    steps = [_find_step_by_ulid(calculation, ulid) for ulid in job.step_ids]
    if None in steps:
        missing = [ulid for ulid, s in zip(job.step_ids, steps) if s is None]
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Steps not found: {missing}",
        )

    # Set up working directory
    working_dir = job.working_dir
    working_dir.mkdir(parents=True, exist_ok=True)

    # Prepare step artifacts directories
    raw_dir = calculation.raw_dir
    step_results = {}

    for step in steps:
        if step is None:
            continue
        step_artifacts_dir = raw_dir / "step_artifacts" / step.meta.id
        step_artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Clear existing artifacts
        import shutil
        for item in step_artifacts_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

        # Inject options
        if not hasattr(step, "options") or step.options is None:
            step.options = {}
        step.options["run_mode"] = context.get("run_mode", "incremental")
        step.options["step_artifacts_dir"] = str(step_artifacts_dir)
        if calculation.structure_id:
            step.options["structure_id"] = calculation.structure_id
            step.options["project_root"] = str(calculation.project.root)

    # Execute the chain using PySCF engine's chain execution method
    # This properly handles SCF -> post-SCF dependency with shared mf object
    target_step = steps[-1]  # Last step is the target

    try:
        # Use run_step_with_chain which properly executes the entire chain
        # with shared state (mf object) between SCF and post-SCF steps
        result = engine.run_step_with_chain(
            target_step=target_step,
            chain_steps=steps,
            calculation_raw_dir=raw_dir,
            structure_id=calculation.structure_id if hasattr(calculation, 'structure_id') else None,
            project_root=calculation.project.root,
        )

        success = result.success if hasattr(result, "success") else False

        # Record results for all steps in the chain
        for step in steps:
            if step is None:
                continue
            step_results[step.meta.id] = {
                "success": success,
                "executed_in_chain": True,
            }

        return JobResult(
            job_id=job.id,
            success=success,
            error=result.error if hasattr(result, "error") and not success else None,
            step_results=step_results,
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.exception(f"[PYSCF_HANDLER] Chain execution failed: {job.id}")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"{type(e).__name__}: {e}\n{tb[:500]}",
        )


def orca_chain_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute an ORCA chain job (fused SCF + post-SCF steps).

    This handler delegates to the existing ORCA engine chain execution.

    Args:
        job: The Job to execute (multi-step chain)
        calculation: Calculation context
        engine_registry: Engine registry
        context: Additional context

    Returns:
        JobResult with execution status
    """
    try:
        engine = engine_registry.get("orca")
    except Exception as e:
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Failed to get ORCA engine: {e}",
        )

    # Get the steps in this chain
    steps = [_find_step_by_ulid(calculation, ulid) for ulid in job.step_ids]
    if None in steps:
        missing = [ulid for ulid, s in zip(job.step_ids, steps) if s is None]
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Steps not found: {missing}",
        )

    # Set up working directory
    working_dir = job.working_dir
    working_dir.mkdir(parents=True, exist_ok=True)

    # Prepare step artifacts directories
    raw_dir = calculation.raw_dir
    step_results = {}

    for step in steps:
        if step is None:
            continue
        step_artifacts_dir = raw_dir / "step_artifacts" / step.meta.id
        step_artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Inject options
        if not hasattr(step, "options") or step.options is None:
            step.options = {}
        step.options["run_mode"] = context.get("run_mode", "incremental")
        step.options["step_artifacts_dir"] = str(step_artifacts_dir)
        step.options["chain_working_dir"] = str(working_dir)

    # Execute the chain using existing ORCA engine
    target_step = steps[-1]  # Last step is the target

    try:
        result = target_step.run(
            engine=engine,
            calculation_raw_dir=raw_dir,
            project_root=calculation.project.root,
            species_map=calculation.species_map,
        )

        success = result.success if hasattr(result, "success") else False

        # Record results for all steps in the chain
        for step in steps:
            if step is None:
                continue
            step_results[step.meta.id] = {
                "success": success,
                "executed_in_chain": True,
            }

        return JobResult(
            job_id=job.id,
            success=success,
            error=result.error if hasattr(result, "error") and not success else None,
            step_results=step_results,
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.exception(f"[ORCA_HANDLER] Chain execution failed: {job.id}")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"{type(e).__name__}: {e}\n{tb[:500]}",
        )


def _find_step_by_ulid(calculation: "Calculation", step_ulid: str) -> Optional["Step"]:
    """Find a step in calculation by its ULID."""
    for step in calculation.steps:
        if step.meta.id == step_ulid:
            return step
    return None


def create_handler_map(
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> Dict[str, Callable[[Job, "Calculation"], JobResult]]:
    """
    Create a handler map for JobExecutor.

    Returns handlers that capture engine_registry and context via closure.

    Args:
        engine_registry: Engine registry
        context: Execution context (run_id, run_mode, etc.)

    Returns:
        Dict mapping engine name to handler function
    """

    def make_handler(base_handler: HandlerFunc):
        """Create a closure that captures engine_registry and context."""
        def handler(job: Job, calculation: "Calculation") -> JobResult:
            return base_handler(job, calculation, engine_registry, context)
        return handler

    return {
        "qe": make_handler(qe_step_handler),
        "pyscf": make_handler(pyscf_chain_handler),
        "orca": make_handler(orca_chain_handler),
    }
