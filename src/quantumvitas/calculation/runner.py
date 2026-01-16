"""
Calculation runner orchestrates step execution and verification.

Integrates with Project History to record run revisions and events.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .calculation import Calculation
from .results import CalculationResult, StepResultSummary
from .types import StepMode, StepStatus, StepType
from .verification import evaluate_step_result
from quantumvitas.engine.registry import EngineRegistry

logger = logging.getLogger(__name__)


def compute_io_dir_from_calculation_model(calculation_dir: Path, working_dir_name: Optional[str] = None) -> Path:
    """
    Compute the I/O directory path from calculation model/context.
    
    This is the SINGLE SOURCE OF TRUTH for determining the I/O directory.
    Both the server (for pending jobs) and runner (for execution) use this function.
    
    Args:
        calculation_dir: Path to the calculation directory (containing calculation.yaml)
        working_dir_name: Name of the working directory subdirectory (from calculation.working_dir).
                         If None, defaults to "raw" (the convention for local runner).
    
    Returns:
        Absolute Path to the I/O directory (the actual directory used by the runner
        to write QE input/output and artifacts).
    
    Note:
        This function encapsulates the default "raw" convention. If the runner's
        I/O directory policy changes in the future, only this function needs to be updated.
    """
    # Default to "raw" if not specified (local runner convention)
    # This is the ONLY place that knows the "raw" default
    subdir = working_dir_name or "raw"
    io_dir = (calculation_dir / subdir).resolve()
    return io_dir


def _coerce_step_type(value) -> StepType:
    """
    Coerce a step type string to StepType enum.

    Handles both GEN types (e.g., "scf") and SPEC types (e.g., "qe_scf")
    by using registry lookup to convert SPEC to GEN when needed.
    """
    if isinstance(value, StepType):
        return value

    # Try direct conversion (works for GEN types like "scf")
    try:
        return StepType(value)
    except (ValueError, KeyError):
        pass

    # If direct conversion failed, try registry lookup for SPEC types
    # SPEC type like "qe_scf" -> public_type "scf" -> StepType.SCF
    try:
        from quantumvitas.workflow.registry import get_registry
        reg = get_registry()
        spec = reg.get(str(value))
        if spec and spec.public_type:
            return StepType(spec.public_type)
    except Exception:
        pass

    return StepType.CUSTOM


def _get_engine_family_from_step(step) -> Optional[str]:
    """
    Determine engine family from a step using registry lookup.

    Constitution §C: Must use explicit registry mapping, NOT prefix inference.
    Uses StepTypeSpec.engine to determine family.

    Args:
        step: A Step object with step_type attribute

    Returns:
        Engine family string ("qe", "pyscf", "orca") or None if unknown
    """
    if not step or not step.step_type:
        return None

    # Get the step type string (may be StepType enum or string)
    step_type_str = str(step.step_type.value) if hasattr(step.step_type, 'value') else str(step.step_type)

    # Look up in registry to get the engine
    try:
        from quantumvitas.workflow.registry import get_registry
        reg = get_registry()
        spec = reg.get(step_type_str)
        if spec and spec.engine:
            # Map engine member to engine family
            engine = spec.engine.lower()
            # QE family: qe, w90
            if engine in ("qe", "w90"):
                return "qe"
            # PySCF family
            elif engine == "pyscf":
                return "pyscf"
            # ORCA family
            elif engine == "orca":
                return "orca"
            # Unknown engine - return as-is
            return engine
    except Exception:
        pass

    return None


class CalculationRunner:
    """
    Execute calculation steps using the configured engine registry.
    """

    def __init__(self, engine_registry: EngineRegistry):
        self.engine_registry = engine_registry

    def run(
        self,
        calculation: Calculation,
        *,
        skip_history: bool = False,
        run_id: Optional[str] = None,
        run_mode: str = "incremental",  # "incremental" or "full"
        target_step_id: Optional[str] = None,  # For Run Step mode (TARGET selection)
        compat_input_playback: bool = False,  # For tutorial playback tests: use existing .in files
    ) -> CalculationResult:
        """
        Execute all steps in a calculation.

        Supports incremental and full run modes, and TARGET selection mode for Run Step.

        Args:
            calculation: The calculation to execute
            skip_history: If True, skip history recording (for testing)
            run_id: External run ID to use (e.g., job_id from JobManager).
                    If provided, this ID will be used for history recording
                    to ensure job_id == run_id identity.
            run_mode: Run mode ("incremental" or "full"). Default "incremental".
                     Incremental skips steps that are already done and unchanged.
                     Full reruns all steps from step0.
            target_step_id: If provided, only run steps up to and including this target
                           (Run Step mode with TARGET selection). Target step always runs.

        Returns:
            CalculationResult with status and step summaries
        """
        calculation.io.ensure()
        started = datetime.now(timezone.utc)
        step_summaries: List[StepResultSummary] = []
        status = StepStatus.SUCCESS
        calculation_failed = False
        
        # Generate run_id if not provided
        if run_id is None:
            import ulid
            run_id = str(ulid.new())
        
        # History: Create run revision and record run_started event
        run_revision = None
        actual_run_id = run_id  # Use external run_id if provided
        if not skip_history:
            run_revision, actual_run_id = self._start_history_recording(
                calculation, started, run_id=run_id
            )

        # Step0: Prepare pseudos in project/pseudo (constitution-compliant)
        # This is the ONLY place allowed to mutate project/pseudo
        if calculation.species_map:
            from quantumvitas.core.pseudo_runtime import (
                prepare_project_pseudos_for_run,
                species_map_to_selections,
                refresh_calc_pseudo_records_after_step0,
            )
            
            report = None
            try:
                selections = species_map_to_selections(
                    calculation.project.root,
                    calculation.species_map,
                )
                
                if selections:
                    # Prepare pseudos (mutates project/pseudo)
                    report = prepare_project_pseudos_for_run(
                        calculation.project.root,
                        selections,
                    )
                else:
                    # No selections to prepare, but still need to refresh records
                    report = None
            except Exception as e:
                # Step0 preparation failed, but still refresh records from existing files
                # This allows updating pseudo_set_sha even if pseudo preparation fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Step0 pseudo preparation failed (non-blocking): {e}")
                report = None
            
            # Refresh calc records with actual file info and update pseudo_set_sha
            # (refresh_calc_pseudo_records_after_step0 now handles pseudo_set_sha update)
            # This runs even if selections is empty or preparation failed (to update SHA from existing files)
            try:
                refresh_calc_pseudo_records_after_step0(
                    calculation.project.root,
                    calculation.dir,
                    calculation.species_map or {},
                )
            except Exception as e:
                # Refresh failure: mark calculation as failed
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Step0 refresh failed: {e}")
                calculation_failed = True
                status = StepStatus.FAILED
                step_summaries.append(StepResultSummary(
                    step_id="step0",
                    step_type=StepType.CUSTOM,
                    status=StepStatus.FAILED,
                    working_dir=calculation.raw_dir,
                    input_file=Path(),
                    output_file=Path(),
                    reference_file=None,
                    message=f"Step0 pseudo refresh failed: {e}",
                    metrics={},
                ))
                # Don't proceed to QE steps if Step0 refresh failed
                return CalculationResult(
                    calculation_id=calculation.id,
                    status=status,
                    started=started,
                    finished=datetime.now(timezone.utc),
                    step_summaries=step_summaries,
                    io_dir=calculation.raw_dir.resolve() if calculation.raw_dir else None,
                    run_id=actual_run_id,
                )
            
            # Log warnings if any
            if report and report.warnings:
                # TODO: Consider logging these warnings somewhere visible
                pass
                step_summaries.append(StepResultSummary(
                    step_id="step0",
                    step_type=StepType.CUSTOM,
                    status=StepStatus.FAILED,
                    working_dir=calculation.raw_dir,
                    input_file=Path(),
                    output_file=Path(),
                    reference_file=None,
                    message=f"Step0 pseudo preparation failed: {e}",
                    metrics={},
                ))
                # Don't proceed to QE steps if Step0 failed
                return CalculationResult(
                    calculation_id=calculation.id,
                    status=status,
                    started=started,
                    finished=datetime.now(timezone.utc),
                    step_summaries=step_summaries,
                )

        import logging
        logger = logging.getLogger(__name__)
        
        # Manifest reconciliation (incremental run support)
        start_idx = 0
        manifest = None
        
        if run_mode == "incremental":
            try:
                from quantumvitas.calculation.manifest_reconcile import reconcile_manifest
                from quantumvitas.calculation.hash_utils import (
                    compute_pseudo_set_sha,
                )
                from quantumvitas.io import read_structure
                from quantumvitas.core.resolution import require_structure
                
                # Compute pseudo_set_sha (should have been computed in preflight, but recompute here for reconciliation)
                project_pseudo_dir = calculation.project.root / "pseudo"
                species_map = calculation.species_map or {}
                current_pseudo_set_sha = compute_pseudo_set_sha(project_pseudo_dir, species_map)
                
                # Resolve structure path
                if calculation.structure_id:
                    structure_resolved = require_structure(
                        calculation.project.root,
                        calculation.structure_id,
                        config=None,
                        index=None,
                    )
                    structure_path = structure_resolved.absolute_path
                else:
                    structure_path = None
                
                if structure_path and structure_path.exists():
                    # Reconcile manifest
                    manifest, start_idx = reconcile_manifest(
                        calc_dir=calculation.dir,
                        project_root=calculation.project.root,
                        calculation_steps=calculation.steps,
                        current_pseudo_set_sha=current_pseudo_set_sha,
                        structure_path=structure_path,
                    )
                    logger.info(f"[CALCULATION_RUNNER] Manifest reconciled: start_idx={start_idx}, total_steps={len(calculation.steps)}")
                else:
                    logger.warning(f"[CALCULATION_RUNNER] Structure path not found, starting from beginning")
                    start_idx = 0
            except Exception as e:
                logger.warning(f"[CALCULATION_RUNNER] Manifest reconciliation failed: {e}, starting from beginning")
                start_idx = 0
        elif run_mode == "full":
            # Full run: reconcile manifest first, then mark all entries as done=False and clear run_id/timestamps
            try:
                from quantumvitas.calculation.manifest_reconcile import reconcile_manifest
                from quantumvitas.calculation.hash_utils import compute_pseudo_set_sha
                from quantumvitas.core.resolution import require_structure
                
                project_pseudo_dir = calculation.project.root / "pseudo"
                species_map = calculation.species_map or {}
                current_pseudo_set_sha = compute_pseudo_set_sha(project_pseudo_dir, species_map) if species_map else ""
                
                if calculation.structure_id:
                    structure_resolved = require_structure(
                        calculation.project.root,
                        calculation.structure_id,
                        config=None,
                        index=None,
                    )
                    structure_path = structure_resolved.absolute_path
                else:
                    structure_path = None
                
                if structure_path and structure_path.exists():
                    # Step 1: Reconcile manifest (ensures length matches topology, updates SHAs and ULIDs)
                    manifest, _ = reconcile_manifest(
                        calc_dir=calculation.dir,
                        project_root=calculation.project.root,
                        calculation_steps=calculation.steps,
                        current_pseudo_set_sha=current_pseudo_set_sha,
                        structure_path=structure_path,
                    )
                    
                    # Step 2: Mark all entries as done=False and clear run_id/timestamps for full run
                    from quantumvitas.calculation.manifest import save_manifest_atomic
                    for entry in manifest.steps:
                        entry.done = False
                        entry.done_at = None
                        entry.run_id = None  # Clear run_id for full run
                        entry.started_at = None  # Clear started_at for full run
                    save_manifest_atomic(calculation.dir, manifest)
                    logger.info(f"[CALCULATION_RUNNER] Full run mode: reconciled manifest, marked all entries as done=False, cleared run_id/timestamps")
                else:
                    logger.warning(f"[CALCULATION_RUNNER] Structure path not found for full run, proceeding without reconciliation")
                
                start_idx = 0
            except Exception as e:
                logger.warning(f"[CALCULATION_RUNNER] Full run manifest reconciliation failed: {e}, proceeding anyway")
                start_idx = 0

        # =====================================================================
        # NEW JOBGRAPH EXECUTION PATH
        # =====================================================================
        # Use the new JobGraph-based execution for all engine families.
        # This provides unified Run Calc / Run Step with selection mode.
        # =====================================================================

        # Compute step SHAs for all steps (needed for JobGraph fingerprinting)
        step_shas: Dict[str, str] = {}
        structure_sha_computed = ""
        pseudo_sha_computed = ""

        try:
            from quantumvitas.calculation.hash_utils import (
                compute_step_sha,
                compute_structure_sha,
                compute_pseudo_set_sha,
            )
            from quantumvitas.core.yamldoc import StepDoc
            from quantumvitas.core.resolution import require_step, require_structure
            from quantumvitas.core.project_utils import load_project_config

            # Compute pseudo_set_sha
            project_pseudo_dir = calculation.project.root / "pseudo"
            species_map = calculation.species_map or {}
            pseudo_sha_computed = compute_pseudo_set_sha(project_pseudo_dir, species_map) if species_map else ""

            # Compute structure_sha
            if calculation.structure_id:
                try:
                    structure_resolved = require_structure(
                        calculation.project.root,
                        calculation.structure_id,
                        config=None,
                        index=None,
                    )
                    structure_sha_computed = compute_structure_sha(structure_resolved.absolute_path)
                except Exception as e:
                    logger.warning(f"[CALCULATION_RUNNER] Failed to compute structure_sha: {e}")

            # Compute step SHAs for all steps
            config = load_project_config(calculation.project.root)
            for step in calculation.steps:
                try:
                    step_resolved = require_step(
                        calculation.project.root,
                        calculation.id,
                        step.meta.id,
                        config=config,
                        index=None,
                    )
                    step_doc_dict = StepDoc.load(step_resolved.absolute_path).to_dict()
                    step_shas[step.meta.id] = compute_step_sha(step_doc_dict)
                except Exception as e:
                    logger.debug(f"[CALCULATION_RUNNER] Failed to compute SHA for step {step.meta.id}: {e}")
                    step_shas[step.meta.id] = ""

        except Exception as e:
            logger.warning(f"[CALCULATION_RUNNER] Failed to compute SHAs for JobGraph: {e}")

        # Execute using JobGraph pipeline
        try:
            step_summaries = self._execute_with_jobgraph(
                calculation,
                run_id=run_id,
                run_mode=run_mode,
                target_step_id=target_step_id,
                manifest=manifest,
                step_shas=step_shas,
                structure_sha=structure_sha_computed,
                pseudo_set_sha=pseudo_sha_computed,
                compat_input_playback=compat_input_playback,
            )

            # Determine overall status
            status = StepStatus.SUCCESS
            for summary in step_summaries:
                if summary.status == StepStatus.FAILED:
                    status = StepStatus.FAILED
                    break

            finished = datetime.now(timezone.utc)
            io_dir = calculation.raw_dir.resolve() if calculation.raw_dir else None

            # History: Complete run revision
            if not skip_history and actual_run_id:
                self._complete_history_recording(
                    calculation=calculation,
                    run_id=actual_run_id,
                    status=status,
                    step_summaries=step_summaries,
                    working_dir=io_dir,
                )

            return CalculationResult(
                calculation_id=calculation.id,
                mode=calculation.mode,
                steps=step_summaries,
                status=status,
                started_at=started,
                finished_at=finished,
                io_dir=io_dir,
                run_id=actual_run_id,
            )

        except Exception as e:
            # No fallback to legacy loop - JobGraph execution is the only path
            # Constitution §C mandates unified pipeline via JobGraph
            logger.exception(f"[CALCULATION_RUNNER] JobGraph execution failed: {e}")
            raise

    def _execute_with_jobgraph(
        self,
        calculation: Calculation,
        *,
        run_id: str,
        run_mode: str,
        target_step_id: Optional[str],
        manifest: Optional[Any],
        step_shas: Dict[str, str],
        structure_sha: str,
        pseudo_set_sha: str,
        compat_input_playback: bool = False,
    ) -> List[StepResultSummary]:
        """
        Execute calculation using JobGraph and JobExecutor pipeline.

        This is the new unified execution path for Run Calc and Run Step.

        Args:
            calculation: Calculation to execute
            run_id: Run ID for manifest tracking
            run_mode: "incremental" or "full"
            target_step_id: If provided, TARGET selection mode
            manifest: Current manifest (for incremental skip logic)
            step_shas: Dict of step_ulid -> SHA for fingerprinting
            structure_sha: Structure SHA for manifest
            pseudo_set_sha: Pseudo set SHA for manifest

        Returns:
            List of StepResultSummary for each executed/skipped step
        """
        from quantumvitas.execution import (
            SelectionMode,
            JobExecutor,
        )
        from quantumvitas.execution.recipes import get_recipe_for_engine
        from quantumvitas.execution.handlers import create_handler_map
        from quantumvitas.calculation.manifest import (
            update_manifest_step,
            now_iso8601,
        )

        step_summaries: List[StepResultSummary] = []

        # Determine engine family
        # Constitution §C: Must use explicit registry lookup, NOT prefix inference
        engine_family = calculation.engine_family
        if not engine_family:
            # Infer from first step using registry lookup (NOT string prefix)
            if calculation.steps:
                first_step = calculation.steps[0]
                engine_family = _get_engine_family_from_step(first_step)
            if not engine_family:
                engine_family = "qe"  # Default

        logger.info(f"[CALCULATION_RUNNER] Using JobGraph pipeline with engine_family={engine_family}")

        # Get recipe and materialize JobGraph
        recipe = get_recipe_for_engine(engine_family)
        raw_dir = calculation.raw_dir
        job_graph = recipe.materialize(calculation.steps, raw_dir, step_shas)

        logger.info(f"[CALCULATION_RUNNER] Materialized JobGraph with {len(job_graph)} jobs")

        # Determine selection mode
        selection = SelectionMode.TARGET if target_step_id else SelectionMode.ALL

        # Create execution context
        context = {
            "run_id": run_id,
            "run_mode": run_mode,
        }

        # Create handlers
        handler_map = create_handler_map(self.engine_registry, context)

        # Create executor and execute
        executor = JobExecutor(engine_handlers=handler_map)

        # For incremental mode, convert manifest to format executor expects
        manifest_for_executor = manifest

        # Execute
        result = executor.execute(
            job_graph=job_graph,
            calculation=calculation,
            selection=selection,
            target_step_id=target_step_id,
            manifest=manifest_for_executor,
            step_shas=step_shas,
        )

        # Convert JobResults to StepResultSummary and update manifest
        for job_result in result.job_results:
            job = job_graph.get_job(job_result.job_id)
            if job is None:
                continue

            # For each step in this job, create a summary and update manifest
            for step_idx, step_ulid in enumerate(job.step_ids):
                step = self._find_step_by_ulid(calculation, step_ulid)
                if step is None:
                    continue

                # Find step index in calculation
                calc_step_idx = self._find_step_index(calculation, step_ulid)

                step_type = _coerce_step_type(step.step_type) if step.step_type else StepType.CUSTOM
                step_type_str = str(step.step_type.value) if step.step_type else "unknown"

                # Extract input/output from Job (source of truth for GEN filenames)
                job_input_file = job.input_files[0] if job.input_files else Path()
                job_output_file = job.expected_outputs[0] if job.expected_outputs else Path()

                if job_result.skipped:
                    # Step was skipped - use Job fields (expected paths)
                    summary = StepResultSummary(
                        step_id=step_ulid,
                        step_type=step_type,
                        status=StepStatus.SUCCESS,
                        working_dir=job.working_dir,
                        input_file=job_input_file,
                        output_file=job_output_file,
                        reference_file=step.reference_output if hasattr(step, 'reference_output') else None,
                        message="Step skipped: already completed with unchanged inputs (incremental run)",
                        metrics={},
                    )
                else:
                    # Step was executed
                    step_success = job_result.success
                    step_error = job_result.error

                    # For executed steps, prefer actual output from handler if available
                    if job_result.step_results:
                        step_result_data = job_result.step_results.get(step_ulid, {})
                        handler_output_file = step_result_data.get("output_file")
                        if handler_output_file:
                            job_output_file = Path(handler_output_file)

                    # Update manifest BEFORE marking as done
                    if calc_step_idx is not None:
                        step_sha = step_shas.get(step_ulid, "")
                        update_manifest_step(
                            calc_dir=calculation.dir,
                            step_index=calc_step_idx,
                            kind=step_type_str,
                            step_ulid=step_ulid,
                            pseudo_set_sha=pseudo_set_sha,
                            structure_sha=structure_sha,
                            step_sha=step_sha,
                            run_id=run_id,
                            done=step_success,
                            started_at=now_iso8601() if not job_result.started_at else job_result.started_at.isoformat(),
                            done_at=now_iso8601() if step_success else None,
                        )

                    summary = StepResultSummary(
                        step_id=step_ulid,
                        step_type=step_type,
                        status=StepStatus.SUCCESS if step_success else StepStatus.FAILED,
                        working_dir=job.working_dir,
                        input_file=job_input_file,
                        output_file=job_output_file,
                        reference_file=step.reference_output if hasattr(step, 'reference_output') else None,
                        message=step_error if step_error else "Step completed successfully",
                        metrics={},
                    )

                step_summaries.append(summary)

        logger.info(f"[CALCULATION_RUNNER] JobGraph execution complete: success={result.success}, summaries={len(step_summaries)}")
        return step_summaries

    def _find_step_by_ulid(self, calculation: Calculation, step_ulid: str):
        """Find a step in calculation by its ULID."""
        for step in calculation.steps:
            if step.meta.id == step_ulid:
                return step
        return None

    def _find_step_index(self, calculation: Calculation, step_ulid: str) -> Optional[int]:
        """Find the index of a step in calculation by its ULID."""
        for idx, step in enumerate(calculation.steps):
            if step.meta.id == step_ulid:
                return idx
        return None

    def _start_history_recording(
        self,
        calculation: Calculation,
        started: datetime,
        *,
        run_id: Optional[str] = None,
    ) -> tuple:
        """
        Create run revision and record run_started event.
        
        Args:
            calculation: The calculation being run
            started: Start timestamp
            run_id: External run ID to use (e.g., job_id from JobManager).
                    If provided, this ID will be used instead of generating a new one.
        
        Returns:
            Tuple of (run_revision, run_id) or (None, None) on error
        """
        try:
            from quantumvitas.history.run_revision import create_run_revision
            from quantumvitas.history.storage import ProjectHistory
            from quantumvitas.history.events import RunStartedEvent
            
            # Gather step info
            step_ids = [s.meta.id for s in calculation.steps]
            step_types = [
                s.step_type.value if hasattr(s.step_type, "value") else str(s.step_type)
                for s in calculation.steps
            ]
            
            # Get preset options if available
            preset_options = None
            try:
                from quantumvitas.presets.integration import detect_presets_from_calculation
                preset_options = detect_presets_from_calculation(calculation.dir)
                # Convert to string representations
                if preset_options:
                    preset_options = {
                        k: v.value if hasattr(v, "value") else str(v)
                        for k, v in preset_options.items()
                    }
            except Exception:
                pass
            
            # Get engine info
            engine_version = None
            engine_path = None
            if self.engine_registry and calculation.steps:
                first_step = calculation.steps[0]
                engine = self.engine_registry.get(first_step.engine)
                if engine:
                    engine_version = getattr(engine, "version", None)
                    engine_path = str(getattr(engine, "executable_path", ""))
            
            # Create run revision (use external run_id if provided)
            run_revision = create_run_revision(
                project_root=calculation.project.root,
                calc_id=calculation.id,
                calc_name=calculation.name if hasattr(calculation, "name") else None,
                step_ids=step_ids,
                step_types=step_types,
                structure_id=getattr(calculation, "structure_id", None),
                structure_name=getattr(calculation, "structure_name", None),
                engine="qe",
                engine_version=engine_version,
                engine_path=engine_path,
                preset_options=preset_options,
                species_map=calculation.species_map,
                working_dir=calculation.raw_dir,
                create_snapshot=True,
                run_id=run_id,  # Use external run_id (job_id) if provided
            )
            
            actual_run_id = run_revision.id
            
            # Record run_started event
            history = ProjectHistory(calculation.project.root)
            project_id = run_revision.project_id
            
            event = RunStartedEvent.create(
                project_id=project_id,
                calc_id=calculation.id,
                run_id=actual_run_id,
                calc_name=calculation.name if hasattr(calculation, "name") else None,
                step_ids=step_ids,
                step_types=step_types,
                engine="qe",
                structure_id=getattr(calculation, "structure_id", None),
                snapshot_path=run_revision.snapshot_path,
            )
            history.append_event(event)
            
            logger.debug(f"[HISTORY] Created run revision: {actual_run_id}")
            return run_revision, actual_run_id
            
        except Exception as e:
            logger.warning(f"[HISTORY] Failed to start history recording: {e}")
            return None, None
    
    def _complete_history_recording(
        self,
        calculation: Calculation,
        run_id: str,
        status: StepStatus,
        step_summaries: List[StepResultSummary],
        working_dir: Optional[Path],
    ) -> None:
        """
        Complete run revision with digests and record run_finished event.
        """
        try:
            from quantumvitas.history.run_revision import complete_run_revision
            from quantumvitas.history.storage import ProjectHistory
            from quantumvitas.history.events import RunFinishedEvent
            
            # Convert step summaries to the format expected by complete_run_revision
            step_results = []
            for summary in step_summaries:
                step_results.append({
                    "step_id": summary.step_id,
                    "step_type": summary.step_type,
                    "step_name": getattr(summary, "step_name", None),
                    "status": summary.status.value if hasattr(summary.status, "value") else str(summary.status),
                    "message": summary.message,
                })
            
            # Determine status string
            status_str = "success" if status == StepStatus.SUCCESS else "failed"
            
            # Error summary for failed runs
            error_summary = None
            if status != StepStatus.SUCCESS:
                failed_steps = [s for s in step_summaries if s.status != StepStatus.SUCCESS]
                if failed_steps:
                    error_summary = f"Failed steps: {', '.join(s.step_id for s in failed_steps[:3])}"
                    if len(failed_steps) > 3:
                        error_summary += f" (+{len(failed_steps) - 3} more)"
            
            # Complete run revision with digests
            run_revision = complete_run_revision(
                project_root=calculation.project.root,
                run_id=run_id,
                status=status_str,
                step_results=step_results,
                working_dir=working_dir or calculation.raw_dir,
                error_summary=error_summary,
            )
            
            # Record run_finished event
            history = ProjectHistory(calculation.project.root)
            
            run_digest = run_revision.run_digest or {}
            duration = run_digest.get("duration_seconds")
            success_count = run_digest.get("success_count", 0)
            failure_count = run_digest.get("failed_count", 0)
            
            event = RunFinishedEvent.create(
                project_id=run_revision.project_id,
                calc_id=calculation.id,
                run_id=run_id,
                status=status_str,
                duration_seconds=duration,
                step_count=len(step_summaries),
                success_count=success_count,
                failure_count=failure_count,
                error_summary=error_summary,
            )
            history.append_event(event)
            
            logger.debug(f"[HISTORY] Completed run revision: {run_id} ({status_str})")
            
        except Exception as e:
            logger.warning(f"[HISTORY] Failed to complete history recording: {e}")

