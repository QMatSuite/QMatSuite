"""LAMMPS step handler.

This module contains the main handler for LAMMPS step execution.
LAMMPS has special handling for:
- Restart/checkpoint files
- Trajectory accumulation
- Data file input format
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
        if step.meta.id == step_ulid:
            return step
    return None


def _format_dir_listing_for_debug(dir_path: Path, max_items: int = 200) -> str:
    """
    Format directory listing with file sizes and mtimes for debug output.
    """
    if not dir_path.exists():
        return f"  (directory does not exist: {dir_path})"
    
    items = []
    try:
        for item in sorted(dir_path.iterdir()):
            try:
                stat = item.stat()
                size = stat.st_size
                mtime = stat.st_mtime
                item_type = "DIR" if item.is_dir() else "FILE"
                items.append(f"    {item_type:4s} {item.name:40s} size={size:10d} mtime={mtime:.3f}")
                if len(items) >= max_items:
                    items.append(f"    ... (truncated at {max_items} items)")
                    break
            except Exception as e:
                items.append(f"    ERROR {item.name}: {e}")
    except Exception as e:
        return f"  (error listing directory: {e})"
    
    if not items:
        return "  (directory is empty)"
    
    return "\n".join(items)


def lammps_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a single LAMMPS step job.
    
    This handler:
    1. Creates workdir (isolated per step)
    2. Materializes inputs (in.lammps, structure.data, potentials)
    3. Executes LAMMPS
    
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
        if len(job.step_ids) != 1:
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"LAMMPS handler expects exactly one step, got {len(job.step_ids)}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        
        step_ulid = job.step_ids[0]
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
        engine = engine_registry.get("lammps")
        if engine is None:
            return JobResult(
                job_id=job.id,
                success=False,
                error="LAMMPS engine not found in registry",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        
        # Create workdir (LAMMPS uses isolated workdir per step)
        working_dir = job.working_dir
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Debug: Log step context before materialize
        step_type = job.metadata.get("spec_step_type", "unknown")
        public_type = job.metadata.get("public_type", "unknown")
        print(f"[LAMMPS-DEBUG] lammps_step_handler: step_ulid={step_ulid}, step_type={step_type}, "
              f"public_type={public_type}")
        print(f"[LAMMPS-DEBUG] lammps_step_handler: calc_dir={calculation.dir}, "
              f"raw_dir={calculation.raw_dir}, working_dir={working_dir}")
        
        # Load step spec to get parameters (Step dataclass doesn't have parameters)
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
            logger.error(f"[LAMMPS_HANDLER] Failed to load step spec for {step_ulid}: {e}")
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Failed to load step spec: {e}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        
        # Debug: Check for restart_from before materialize
        step_params = step_spec.parameters if hasattr(step_spec, "parameters") else {}
        restart_from = step_params.get("restart_from") if isinstance(step_params, dict) else None
        if restart_from:
            print(f"[LAMMPS-DEBUG] lammps_step_handler: step has restart_from={restart_from}")
            upstream_workdir = calculation.raw_dir / restart_from
            print(f"[LAMMPS-DEBUG] lammps_step_handler: upstream workdir={upstream_workdir}, exists={upstream_workdir.exists()}")
            if upstream_workdir.exists():
                print(f"[LAMMPS-DEBUG] lammps_step_handler: upstream workdir contents (before materialize):")
                print(_format_dir_listing_for_debug(upstream_workdir, max_items=50))
        
        # Debug: Check current workdir before materialize
        if working_dir.exists():
            print(f"[LAMMPS-DEBUG] lammps_step_handler: current workdir contents (before materialize):")
            print(_format_dir_listing_for_debug(working_dir, max_items=50))
        
        # Materialize inputs using step_spec (which has parameters)
        try:
            engine.materialize_inputs(step_spec, working_dir, calculation)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"[LAMMPS_HANDLER] Failed to materialize inputs for step {step_ulid}: {e}")
            print(f"[LAMMPS-DEBUG] lammps_step_handler: materialize FAILED, workdir contents:")
            if working_dir.exists():
                print(_format_dir_listing_for_debug(working_dir, max_items=50))
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Failed to materialize inputs: {e}\n{tb[:500]}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        
        # Debug: Log after materialize
        print(f"[LAMMPS-DEBUG] lammps_step_handler: materialize completed, workdir contents:")
        if working_dir.exists():
            print(_format_dir_listing_for_debug(working_dir, max_items=100))
        
        # Check key files
        in_lammps = working_dir / "in.lammps"
        structure_data = working_dir / "structure.data"
        print(f"[LAMMPS-DEBUG] lammps_step_handler: in.lammps exists={in_lammps.exists()}, "
              f"structure.data exists={structure_data.exists()}")
        
        # Check potential staging
        potentials_dir = working_dir / "potentials"
        if potentials_dir.exists():
            print(f"[LAMMPS-DEBUG] lammps_step_handler: potentials directory contents:")
            print(_format_dir_listing_for_debug(potentials_dir, max_items=20))
        
        # Execute LAMMPS
        try:
            result = engine.run_step(step_spec, working_dir, calculation)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.exception(f"[LAMMPS_HANDLER] Step {step_ulid} execution failed")
            print(f"[LAMMPS-DEBUG] lammps_step_handler: run_step raised exception: {type(e).__name__}: {e}")
            print(f"[LAMMPS-DEBUG] lammps_step_handler: workdir contents after exception:")
            if working_dir.exists():
                print(_format_dir_listing_for_debug(working_dir, max_items=100))
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"{type(e).__name__}: {e}\n{tb[:500]}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        
        success = result.success if hasattr(result, "success") else False
        error_msg = result.error if hasattr(result, "error") and not success else None
        
        # Debug: Log after LAMMPS run
        return_code = getattr(result, "return_code", None)
        print(f"[LAMMPS-DEBUG] lammps_step_handler: run_step completed, return_code={return_code}, success={success}")
        
        log_file = working_dir / "log.lammps"
        log_exists = log_file.exists()
        if log_exists:
            try:
                log_size = log_file.stat().st_size
                print(f"[LAMMPS-DEBUG] lammps_step_handler: log.lammps exists, size={log_size}")
                # Print last 20 lines if failed or restart_from step
                if not success or restart_from:
                    try:
                        log_lines = log_file.read_text().splitlines()
                        last_lines = log_lines[-20:] if len(log_lines) > 20 else log_lines
                        print(f"[LAMMPS-DEBUG] lammps_step_handler: log.lammps last {len(last_lines)} lines:")
                        for line in last_lines:
                            print(f"  {line}")
                    except Exception as e:
                        print(f"[LAMMPS-DEBUG] lammps_step_handler: failed to read log.lammps: {e}")
            except Exception as e:
                print(f"[LAMMPS-DEBUG] lammps_step_handler: failed to stat log.lammps: {e}")
        else:
            print(f"[LAMMPS-DEBUG] lammps_step_handler: log.lammps does NOT exist")
        
        # Debug: Check for expected output files
        final_data = working_dir / "final.data"
        restart_bin = working_dir / "restart.bin"
        restart_patterns = list(working_dir.glob("restart*.bin"))
        all_data_files = list(working_dir.glob("*.data"))
        
        print(f"[LAMMPS-DEBUG] lammps_step_handler: output files check:")
        print(f"  final.data exists={final_data.exists()}")
        print(f"  restart.bin exists={restart_bin.exists()}")
        print(f"  restart*.bin glob: found {len(restart_patterns)} files")
        if restart_patterns:
            for p in restart_patterns[:10]:  # Limit to 10
                try:
                    stat = p.stat()
                    print(f"    - {p.name} size={stat.st_size} mtime={stat.st_mtime:.3f}")
                except Exception:
                    print(f"    - {p.name} (stat failed)")
        print(f"  *.data glob: found {len(all_data_files)} files")
        if all_data_files:
            for p in all_data_files[:10]:  # Limit to 10
                try:
                    stat = p.stat()
                    print(f"    - {p.name} size={stat.st_size} mtime={stat.st_mtime:.3f}")
                except Exception:
                    print(f"    - {p.name} (stat failed)")
        
        # Debug: Full workdir listing after run
        print(f"[LAMMPS-DEBUG] lammps_step_handler: workdir contents after run:")
        if working_dir.exists():
            print(_format_dir_listing_for_debug(working_dir, max_items=100))
        
        # Verify expected output artifacts exist (fixes Ubuntu CI race condition)
        if success:
            public_type = job.metadata.get("public_type")
            
            # Relax steps must produce final.data
            if public_type == "relax":
                final_data_path = working_dir / "final.data"
                if not final_data_path.exists():
                    success = False
                    error_msg = (
                        f"Relax step completed but final.data not found in {working_dir}. "
                        f"Contents: {list(working_dir.iterdir()) if working_dir.exists() else 'dir missing'}"
                    )
                    logger.error(f"[LAMMPS_HANDLER] {error_msg}")
            
            # MD steps should produce restart.bin (or restart.*.bin)
            elif public_type == "md":
                restart_patterns = list(working_dir.glob("restart*.bin"))
                log_file = working_dir / "log.lammps"
                # Only fail if no restart file AND log indicates completion
                if not restart_patterns and log_file.exists():
                    # Check if LAMMPS completed normally (log should have timing info)
                    log_content = log_file.read_text()
                    if "Total wall time" in log_content or "Loop time" in log_content:
                        # LAMMPS completed but no restart file - this is OK for short runs
                        # but log it for debugging
                        logger.warning(
                            f"[LAMMPS_HANDLER] MD step completed but no restart.bin found in {working_dir}. "
                            f"This may affect downstream restart_from steps."
                        )
        
        # Build step result with capability-based relax artifact spec
        step_result_data = {
            "success": success,
            "working_dir": str(working_dir),
            "return_code": getattr(result, "return_code", None),
        }
        
        # If this is a relax step and succeeded, add artifact spec for post-processing
        step_type = step_spec.step_type_spec if hasattr(step_spec, "step_type_spec") else None
        if success and step_type and is_relax_step_type(step_type):
            final_data_path = working_dir / "final.data"
            if final_data_path.exists():
                step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                    artifact_type="lammps_data",
                    artifact_path=final_data_path,
                    step_ulid=step_ulid,
                    step_type=str(step_type),
                ).to_dict()
        
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
        logger.exception(f"[LAMMPS_HANDLER] Step execution failed")
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"{type(e).__name__}: {e}\n{tb[:500]}",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

