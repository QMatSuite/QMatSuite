"""CP2K step handler.

This module contains the main handler for CP2K step execution.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.executor import JobResult
from quantumvitas.execution.relax_artifacts import RelaxArtifactSpec, is_relax_step_type

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


def cp2k_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a single CP2K step job.

    CRITICAL NOTES:
    - NO workdir cleanup (artifacts accumulate)
    - Uses mtime-based artifact selection
    - Preflight checks run before execution
    - Dependencies resolved from Runtime SSOT only (never raw/scan/)
    """
    from datetime import datetime, timezone
    from quantumvitas.execution.preflight import PreflightChecker
    from quantumvitas.drivers.cp2k.recipe import CP2KRecipe
    from quantumvitas.execution.latest_selector import find_latest_by_mtime

    started = datetime.now(timezone.utc)

    # 1. Validate single-step job
    if len(job.step_ids) != 1:
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"CP2K handler expects single-step job, got {len(job.step_ids)} steps",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

    step_ulid = job.step_ids[0]
    step = _find_step_by_ulid(calculation, step_ulid)
    if step is None:
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Step {step_ulid} not found in calculation",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

    # 2. Get engine
    try:
        engine = engine_registry.get("cp2k")
    except Exception as e:
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Failed to get CP2K engine: {e}",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

    # 3. Create workdir (NO CLEANUP - CP2K accumulates)
    working_dir = job.working_dir
    working_dir.mkdir(parents=True, exist_ok=True)
    # DO NOT add shutil.rmtree() here - critical alignment decision

    # 4. Load step spec (like LAMMPS)
    from quantumvitas.calculation.structure_steps import StructureStepSpec
    from quantumvitas.core.resolution import require_step

    try:
        # Get step file path from registry
        calc_ref = None
        for wf_ref in calculation.project.calculations.values():
            if wf_ref.absolute_path == calculation.dir:
                calc_ref = wf_ref
                break

        calc_selector = calc_ref.meta.slug if calc_ref else calculation.dir.name
        step_resolved = require_step(calculation.project.root, calc_selector, step_ulid)
        step_spec = StructureStepSpec.from_yaml(step_resolved.absolute_path)
    except Exception as e:
        logger.error(f"[CP2K_HANDLER] Failed to load step spec for {step_ulid}: {e}")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Failed to load step spec: {e}",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

    # 5. Run preflight checks
    recipe = CP2KRecipe()
    requirements = recipe.get_preflight_requirements(step_spec)
    if requirements:
        checker = PreflightChecker()
        errors = checker.check(requirements, calculation, step_spec)
        if errors:
            error_msgs = [e.message for e in errors]
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Preflight check failed: {'; '.join(error_msgs)}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                step_results={step_ulid: {"success": False}},
            )

    # 6. Handle restart artifacts (if predecessor exists)
    # CRITICAL: Read from Runtime SSOT (raw/<predecessor_ulid>/), NOT raw/scan/
    restart_info = _resolve_cp2k_restart_artifacts(step_spec, calculation, step_ulid)
    if restart_info:
        # Update step parameters or input generation with restart info
        # For now, restart handling is done via restart_policy in input generation
        pass

    # 7. Materialize inputs
    try:
        engine.materialize_inputs(step_spec, working_dir, calculation)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[CP2K_HANDLER] Failed to materialize inputs for step {step_ulid}: {e}")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"Failed to materialize inputs: {e}\n{tb[:500]}",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

    # 8. Execute
    try:
        result = engine.run_step(step_spec, working_dir, calculation)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.exception(f"[CP2K_HANDLER] Step {step_ulid} execution failed")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"CP2K execution failed: {e}\n{tb[:500]}",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            step_results={step_ulid: {"success": False}},
        )

    # 9. Build JobResult with relax artifact spec if applicable
    step_result_data = {
        "success": result.success,
        "output_file": str(result.output_file) if result.output_file else None,
    }

    if result.success and is_relax_step_type(step_spec.step_type_spec):
        if result.trajectory_file:
            # Include cell_path in extra dict
            extra = {}
            if result.cell_file:
                extra["cell_path"] = str(result.cell_file)
            step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                artifact_type="cp2k_trajectory",
                artifact_path=result.trajectory_file,
                step_ulid=step_ulid,
                step_type_spec=str(step_spec.step_type_spec),
                extra=extra,
            ).to_dict()

    return JobResult(
        job_id=job.id,
        success=result.success,
        error=result.error,
        started_at=started,
        finished_at=datetime.now(timezone.utc),
        step_results={step_ulid: step_result_data},
    )


def _resolve_cp2k_restart_artifacts(step_spec, calculation, step_ulid: str) -> Optional[Dict]:
    """
    Resolve restart artifacts from predecessor step.

    CRITICAL: Always reads from Runtime SSOT (raw/<predecessor_ulid>/),
    NEVER from scan archive (raw/scan/).
    """
    from quantumvitas.execution.latest_selector import find_latest_by_mtime

    params = getattr(step_spec, "parameters", None) or {}
    restart_policy = params.get("restart_policy", {})

    if not restart_policy.get("use_restart") and not restart_policy.get("use_wfn_guess"):
        return None

    # Find predecessor
    steps = calculation.steps
    current_idx = None
    for i, step in enumerate(steps):
        if step.meta.ulid == step_ulid:
            current_idx = i
            break
    if current_idx is None or current_idx == 0:
        return None
    predecessor = steps[current_idx - 1]

    # CRITICAL: Use Runtime SSOT
    predecessor_dir = calculation.io.raw_dir / predecessor.meta.ulid

    result = {}

    if restart_policy.get("use_restart"):
        restart_file = find_latest_by_mtime(predecessor_dir, "cp2k_calc-*.restart")
        if restart_file:
            result["restart_file"] = restart_file

    if restart_policy.get("use_wfn_guess"):
        wfn_file = predecessor_dir / "cp2k_calc-RESTART.wfn"
        if wfn_file.exists():
            result["wfn_file"] = wfn_file

    return result if result else None

