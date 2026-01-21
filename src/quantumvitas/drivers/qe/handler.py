"""QE step handler."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.executor import JobResult
from quantumvitas.execution.relax_artifacts import RelaxArtifactSpec, is_relax_step_type

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.calculation.step import Step
    from quantumvitas.engine.registry import EngineRegistry


logger = logging.getLogger(__name__)


def _find_step_by_ulid(calculation: "Calculation", step_ulid: str) -> Optional["Step"]:
    """Find a step in calculation by its ULID."""
    for step in calculation.steps:
        if step.meta.id == step_ulid:
            return step
    return None


def _get_step_input_from_calculation_yaml(
    calculation: "Calculation",
    step_ulid: str,
) -> Optional[Path]:
    """
    Get the input file path from calculation.yaml for a given step.
    
    Used by compat input playback mode to find existing .in files.
    
    Args:
        calculation: Calculation instance
        step_ulid: Step ULID to look up
        
    Returns:
        Path to input file if found in calculation.yaml, None otherwise
    """
    import yaml
    
    calculation_yaml = calculation.dir / "calculation.yaml"
    if not calculation_yaml.exists():
        return None
    
    data = yaml.safe_load(calculation_yaml.read_text())
    steps_data = data.get("steps", [])
    
    for step_data in steps_data:
        if step_data.get("step_id") == step_ulid:
            input_path_value = step_data.get("input") or step_data.get("file")
            if input_path_value:
                input_path = Path(input_path_value)
                if not input_path.is_absolute():
                    # Resolve relative to calculation working_dir (raw/)
                    input_path = (calculation.working_dir / input_path).resolve()
                    if not input_path.exists():
                        # Try relative to calculation_dir
                        input_path = (calculation.dir / input_path_value).resolve()
                if input_path.exists():
                    return input_path
                else:
                    # Log for debugging
                    logger.warning(
                        f"[COMPAT] Input file not found: {input_path} "
                        f"(working_dir={calculation.working_dir}, calc_dir={calculation.dir})"
                    )
    
    return None


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

    # Check for compat input playback mode
    compat_input_playback = context.get("compat_input_playback", False)
    
    # Execute step
    try:
        if compat_input_playback:
            # Try to get input path from calculation.yaml
            existing_input_path = _get_step_input_from_calculation_yaml(
                calculation=calculation,
                step_ulid=step_ulid,
            )
            
            if existing_input_path:
                # Use compat executor
                from quantumvitas.calculation.compat_executor import run_qe_step_from_existing_input_compat
                
                result = run_qe_step_from_existing_input_compat(
                    existing_input_path=existing_input_path,
                    working_dir=raw_dir,
                    project_root=calculation.project.root,
                    step_id=step_ulid,
                    calculation_slug=calculation.id,
                    engine=engine,
                    step_type=step.step_type if step.step_type else None,
                    timeout=step.options.get("timeout"),
                )
            else:
                # No input field in calculation.yaml, fall back to normal path
                result = step.run(
                    engine=engine,
                    calculation_raw_dir=raw_dir,
                    project_root=calculation.project.root,
                    species_map=calculation.species_map,
                )
        else:
            # Normal SSOT path
            result = step.run(
                engine=engine,
                calculation_raw_dir=raw_dir,
                project_root=calculation.project.root,
                species_map=calculation.species_map,
            )

        success = result.success if hasattr(result, "success") else False
        error_msg = result.error if hasattr(result, "error") and not success else None

        # Build step result with capability-based relax artifact spec
        step_result_data = {
                    "success": success,
                    "output_file": str(result.output_file) if result.output_file else None,
                    "return_code": getattr(result, "return_code", None),
                }
        
        # If this is a relax step and succeeded, add artifact spec for post-processing
        step_type = step.step_type if hasattr(step, "step_type") else None
        if success and step_type and is_relax_step_type(step_type) and result.output_file:
            step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                artifact_type="qe_output",
                artifact_path=Path(result.output_file),
                step_ulid=step_ulid,
                step_type=str(step_type),
            ).to_dict()

        return JobResult(
            job_id=job.id,
            success=success,
            error=error_msg,
            step_results={step_ulid: step_result_data},
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


def handle_qe_relax_output(
    step_ulid: str,
    step_type: str,
    calc_dir: Path,
    output_path: Path,
    calculation_ulid: str,
    input_structure_ulid: str,
    run_id: Optional[str] = None,
) -> Path:
    """
    Handle QE relax step output: parse and write current.json.
    
    Args:
        step_ulid: ULID of the relax step
        step_type: Machine step type (e.g., "qe_relax")
        calc_dir: Path to calculation directory
        output_path: Path to QE output file (.out)
        calculation_ulid: ULID of the calculation
        input_structure_ulid: ULID of the input structure
        run_id: Optional run ID for provenance
        
    Returns:
        Path to written current.json
        
    Raises:
        ValueError: If output parsing fails
    """
    from quantumvitas.calculation.geometry import (
        read_final_geometry_from_output_text,
        structure_from_qe_geometry_snapshot,
    )
    from quantumvitas.execution.relax_artifacts import write_generated_structure
    
    # 1. Read output
    output_text = output_path.read_text()
    
    # 2. Parse final geometry
    snapshot, species = read_final_geometry_from_output_text(output_text)
    
    # 3. Convert to pymatgen Structure (with canonicalization)
    structure = structure_from_qe_geometry_snapshot(snapshot, species)
    
    # 4. Canonicalize before writing (ensure consistent canonicalization)
    from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place
    canonicalize_structure_like_in_place(structure)
    
    # 5. Write current.json
    artifact_path = write_generated_structure(
        structure=structure,
        calc_dir=calc_dir,
        step_ulid=step_ulid,
        step_type=step_type,
        run_id=run_id,
        calculation_ulid=calculation_ulid,
        input_structure_ulid=input_structure_ulid,
    )
    
    logger.info(f"[RELAX_HANDLER] Wrote generated structure for step {step_ulid} to {artifact_path}")
    
    return artifact_path

