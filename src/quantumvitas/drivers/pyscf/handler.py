"""PySCF chain handler.

This module contains the chain handler for PySCF calculations.
PySCF is Python-native, so the handler executes Python scripts
that call PySCF functions directly.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.executor import JobResult
from quantumvitas.execution.relax_artifacts import RelaxArtifactSpec, is_relax_step_type

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.engine.registry import EngineRegistry

logger = logging.getLogger(__name__)


def _find_step_by_ulid(calculation: "Calculation", step_ulid: str) -> Optional["Step"]:
    """Find a step in calculation by its ULID."""
    from quantumvitas.calculation.step import Step
    for step in calculation.steps:
        if step.meta.ulid == step_ulid:
            return step
    return None


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
    steps = [_find_step_by_ulid(calculation, ulid) for ulid in job.step_ulids]
    if None in steps:
        missing = [ulid for ulid, s in zip(job.step_ulids, steps) if s is None]
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
        step_artifacts_dir = raw_dir / "step_artifacts" / step.meta.ulid
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
        if calculation.structure_ulid:
            step.options["structure_ulid"] = calculation.structure_ulid
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
            structure_ulid=calculation.structure_ulid if hasattr(calculation, 'structure_ulid') else None,
            project_root=calculation.project.root,
        )

        success = result.success if hasattr(result, "success") else False

        # Record results for all steps in the chain
        for step in steps:
            if step is None:
                continue
            step_artifacts_dir = raw_dir / "step_artifacts" / step.meta.ulid
            step_result_data = {
                "success": success,
                "executed_in_chain": True,
                "working_dir": str(step_artifacts_dir),
            }
            
            # If this is a relax step and succeeded, add artifact spec
            step_type = step.step_type_spec if hasattr(step, "step_type_spec") else None
            if success and step_type and is_relax_step_type(step_type):
                results_file = step_artifacts_dir / "results.json"
                if results_file.exists():
                    step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                        artifact_type="pyscf_results",
                        artifact_path=results_file,
                        step_ulid=step.meta.ulid,
                        step_type_spec=str(step_type),
                    ).to_dict()
            
            step_results[step.meta.ulid] = step_result_data

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

