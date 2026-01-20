"""
Engine Handlers: Bridge between JobExecutor and existing engine execution logic.

These handlers wrap the existing step.run() and chain execution code,
adapting them to the Job-based execution model.

Per engine_recipes_jobgraph_plan.md (Constitution):
- Preserve existing filesystem contracts
- QE: raw/outdir unchanged
- Wannier: raw in-place unchanged
- QC: raw/scf_<suffix>/ unchanged

Architecture: Capability-based artifact production
=================================================
Handlers produce step_results with optional "relax_artifact_spec" dict
that describes how to post-process outputs into current.json.
Executor uses RELAX_ARTIFACT_HANDLERS registry to process, not engine branching.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.executor import JobResult
from quantumvitas.execution.relax_artifacts import RelaxArtifactSpec, is_relax_step_type

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.calculation.step import Step
    from quantumvitas.engine.registry import EngineRegistry


logger = logging.getLogger(__name__)


# Handler type signature
HandlerFunc = Callable[[Job, "Calculation", "EngineRegistry", Dict[str, Any]], JobResult]


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
                    import logging
                    logger = logging.getLogger(__name__)
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
    from quantumvitas.execution.reference_resolver import find_reference_scf
    from quantumvitas.execution.vasp_staging import stage_chgcar, stage_wavecar
    from quantumvitas.calculation.manifest import Manifest
    
    try:
        # Get step
        if len(job.step_ids) != 1:
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"VASP handler expects exactly one step, got {len(job.step_ids)}",
            )
        
        step_ulid = job.step_ids[0]
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
            import shutil
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
        if step.step_type and step.step_type != "vasp_scf":
            # Non-SCF step: need reference SCF
            steps_list = calculation.steps
            current_idx = next(
                (i for i, s in enumerate(steps_list) if s.meta.id == step_ulid),
                None
            )
            if current_idx is not None:
                ref_result = find_reference_scf(steps_list, current_idx)
                if ref_result:
                    ref_idx, ref_scf_step = ref_result
                    # Get manifest entry for reference
                    ref_manifest_entry = next(
                        (e for e in manifest.steps if e.step_ulid == ref_scf_step.meta.id),
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
        
        # Materialize inputs using step_spec (which has parameters)
        try:
            engine.materialize_inputs(step_spec, working_dir, calculation)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"[LAMMPS_HANDLER] Failed to materialize inputs for step {step_ulid}: {e}")
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Failed to materialize inputs: {e}\n{tb[:500]}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        
        # Execute LAMMPS
        try:
            result = engine.run_step(step_spec, working_dir, calculation)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.exception(f"[LAMMPS_HANDLER] Step {step_ulid} execution failed")
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"{type(e).__name__}: {e}\n{tb[:500]}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
            )
        
        success = result.success if hasattr(result, "success") else False
        error_msg = result.error if hasattr(result, "error") and not success else None
        
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
        step_type = step_spec.step_type if hasattr(step_spec, "step_type") else None
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
            step_artifacts_dir = raw_dir / "step_artifacts" / step.meta.id
            step_result_data = {
                "success": success,
                "executed_in_chain": True,
                "working_dir": str(step_artifacts_dir),
            }
            
            # If this is a relax step and succeeded, add artifact spec
            step_type = step.step_type if hasattr(step, "step_type") else None
            if success and step_type and is_relax_step_type(step_type):
                results_file = step_artifacts_dir / "results.json"
                if results_file.exists():
                    step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                        artifact_type="pyscf_results",
                        artifact_path=results_file,
                        step_ulid=step.meta.id,
                        step_type=str(step_type),
                    ).to_dict()
            
            step_results[step.meta.id] = step_result_data

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

    # Set up working directory (from job, set by recipe)
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
            structure_id=calculation.structure_id if hasattr(calculation, 'structure_id') else None,
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
            step_type = step.step_type if hasattr(step, "step_type") else None
            if success and step_type and is_relax_step_type(step_type):
                step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                    artifact_type="orca_xyz",
                    artifact_path=Path(effective_working_dir),
                    step_ulid=step.meta.id,
                    step_type=str(step_type),
                    extra={"chain_key": effective_chain_key or ""},
                ).to_dict()
            
            step_results[step.meta.id] = step_result_data

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
        "vasp": make_handler(vasp_step_handler),
        "lammps": make_handler(lammps_step_handler),
    }
