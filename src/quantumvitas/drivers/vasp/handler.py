"""VASP step handler.

This module contains the main handler for VASP step execution.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.executor import JobResult

# Import staging utilities
from .staging import stage_chgcar, stage_wavecar
from quantumvitas.execution.reference_resolver import find_reference_scf

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


def vasp_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a single VASP step job.
    
    This handler:
    1. Cleans workdir completely (rm -rf)
    2. Finds reference SCF (if needed)
    3. Stages CHGCAR/WAVECAR from reference
    4. Materializes inputs (POSCAR/INCAR/KPOINTS/POTCAR)
    5. Executes VASP
    
    Args:
        job: The Job to execute (single step)
        calculation: Calculation context
        engine_registry: Engine registry
        context: Additional context (manifest, etc.)
    
    Returns:
        JobResult with execution status
    """
    from quantumvitas.calculation.manifest import Manifest
    
    try:
        # Get step
        if len(job.step_ulids) != 1:
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"VASP handler expects exactly one step, got {len(job.step_ulids)}",
            )
        
        step_ulid = job.step_ulids[0]
        step = _find_step_by_ulid(calculation, step_ulid)
        if step is None:
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Step {step_ulid} not found",
            )
        
        # Get engine
        engine = engine_registry.get("vasp")
        if engine is None:
            return JobResult(
                job_id=job.id,
                success=False,
                error="VASP engine not found in registry",
            )
        
        # Clean workdir completely (rm -rf)
        working_dir = job.working_dir
        if working_dir.exists():
            shutil.rmtree(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Get manifest for reference checking
        # Always reload from disk to get latest state (manifest may have been updated by previous steps)
        from quantumvitas.calculation.manifest import load_manifest
        try:
            manifest = load_manifest(calculation.dir)
        except Exception:
            # Fallback to context manifest if load fails
            manifest = context.get("manifest")
            if manifest is None:
                manifest = Manifest()
        
        # Find reference SCF if needed
        ref_scf_step = None
        ref_manifest_entry = None
        if step.step_type_spec and step.step_type_spec != "vasp_scf":
            # Non-SCF step: need reference SCF
            steps_list = calculation.steps
            current_idx = next(
                (i for i, s in enumerate(steps_list) if s.meta.ulid == step_ulid),
                None
            )
            if current_idx is not None:
                ref_result = find_reference_scf(steps_list, current_idx)
                if ref_result:
                    ref_idx, ref_scf_step = ref_result
                    # Get manifest entry for reference
                    ref_manifest_entry = next(
                        (e for e in manifest.steps if e.step_ulid == ref_scf_step.meta.ulid),
                        None
                    )
        
        # Stage artifacts from reference SCF
        calc_raw_dir = calculation.raw_dir
        if ref_scf_step:
            try:
                stage_chgcar(
                    step, ref_scf_step, ref_manifest_entry,
                    calc_raw_dir, working_dir
                )
                # WAVECAR is optional
                stage_wavecar(
                    step, ref_scf_step, ref_manifest_entry,
                    calc_raw_dir, working_dir, required=False
                )
            except Exception as e:
                # Staging errors are already clear from vasp_staging
                return JobResult(
                    job_id=job.id,
                    success=False,
                    error=str(e),
                )
        
        # Materialize inputs
        try:
            engine.materialize_inputs(step, working_dir, calculation)
        except Exception as e:
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Failed to materialize inputs: {e}",
            )
        
        # Execute VASP
        try:
            result = engine.run_step(step, working_dir, calculation)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.exception(f"[VASP_HANDLER] Step {step_ulid} execution failed")
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"{type(e).__name__}: {e}\n{tb[:500]}",
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
                    "output_file": str(result.output_file) if hasattr(result, "output_file") and result.output_file else None,
                    "return_code": getattr(result, "return_code", None),
                }
            },
        )
    
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.exception(f"[VASP_HANDLER] Step execution failed")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"{type(e).__name__}: {e}\n{tb[:500]}",
        )

