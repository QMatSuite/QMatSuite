"""ORCA chain handler.

This module contains the chain handler for ORCA calculations.
ORCA uses a chain pattern where multiple related calculations
can be grouped and executed with shared context.
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
    steps = [_find_step_by_ulid(calculation, ulid) for ulid in job.step_ulids]
    if None in steps:
        missing = [ulid for ulid, s in zip(job.step_ulids, steps) if s is None]
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Steps not found: {missing}",
        )

    # Set up working directory (from job, set by recipe)
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

        # Inject options
        if not hasattr(step, "options") or step.options is None:
            step.options = {}
        step.options["run_mode"] = context.get("run_mode", "incremental")
        step.options["step_artifacts_dir"] = str(step_artifacts_dir)
        step.options["chain_working_dir"] = str(working_dir)

    # Execute the chain using ORCA engine's run_step_with_chain
    # (matches PySCF handler pattern)
    target_step = steps[-1]  # Last step is the target

    try:
        # Call run_step_with_chain directly (like PySCF handler)
        # ORCA recipe sets job.working_dir to calc_raw_dir / namespace_folder (e.g., calc/raw/scf_ABCDEF/)
        # Pass the actual working_dir to run_step_with_chain
        result = engine.run_step_with_chain(
            target_step=target_step,
            chain_steps=steps,
            calculation_raw_dir=working_dir,  # Use job.working_dir directly
            structure_ulid=calculation.structure_ulid if hasattr(calculation, 'structure_ulid') else None,
            project_root=calculation.project.root,
        )

        success = result.success if hasattr(result, "success") else False
        
        # Extract working_dir from parsed_output for post-processing
        # chain_key (basename) comes from job.metadata, not from parsed_output
        chain_working_dir = None
        if hasattr(result, 'parsed_output') and result.parsed_output:
            chain_working_dir = result.parsed_output.get('working_dir')
        
        # Get basename from job.metadata (set by ORCA recipe)
        # This is the actual filename prefix for ORCA output files (e.g., "s", "s_t", "relax")
        basename = job.metadata.get("subchain_basename") if hasattr(job, 'metadata') and job.metadata else None
        
        # Also get chain.key from parsed_output if available (e.g., "chain01_relax")
        # This is the full chain key that matches actual file names
        chain_key_from_result = None
        if hasattr(result, 'parsed_output') and result.parsed_output:
            chain_key_from_result = result.parsed_output.get('chain_key')
        
        # Prefer chain_key from result (matches actual file names), fallback to basename
        effective_chain_key = chain_key_from_result or basename

        # Record results for all steps in the chain
        for step in steps:
            if step is None:
                continue
            effective_working_dir = chain_working_dir or str(working_dir)
            step_result_data = {
                "success": success,
                "executed_in_chain": True,
                "working_dir": effective_working_dir,
                "chain_key": effective_chain_key,
            }
            
            # If this is a relax step and succeeded, add artifact spec
            step_type = step.step_type_spec if hasattr(step, "step_type_spec") else None
            if success and step_type and is_relax_step_type(step_type):
                step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                    artifact_type="orca_xyz",
                    artifact_path=Path(effective_working_dir),
                    step_ulid=step.meta.ulid,
                    step_type_spec=str(step_type),
                    extra={"chain_key": effective_chain_key or ""},
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
        logger.exception(f"[ORCA_HANDLER] Chain execution failed: {job.id}")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"{type(e).__name__}: {e}\n{tb[:500]}",
        )

