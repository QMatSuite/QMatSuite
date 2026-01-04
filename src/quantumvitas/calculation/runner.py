"""
Calculation runner orchestrates step execution and verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .calculation import Calculation
from .results import CalculationResult, StepResultSummary
from .types import StepMode, StepStatus, StepType
from .verification import evaluate_step_result
from quantumvitas.engine.registry import EngineRegistry


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
    if isinstance(value, StepType):
        return value
    try:
        return StepType(value)
    except Exception:
        return StepType.CUSTOM


class CalculationRunner:
    """
    Execute calculation steps using the configured engine registry.
    """

    def __init__(self, engine_registry: EngineRegistry):
        self.engine_registry = engine_registry

    def run(self, calculation: Calculation) -> CalculationResult:
        calculation.io.ensure()
        started = datetime.now(timezone.utc)
        step_summaries: List[StepResultSummary] = []
        status = StepStatus.SUCCESS
        calculation_failed = False

        # Step0: Prepare pseudos in project/pseudo (constitution-compliant)
        # This is the ONLY place allowed to mutate project/pseudo
        if calculation.species_map:
            from quantumvitas.core.pseudo_runtime import (
                prepare_project_pseudos_for_run,
                species_map_to_selections,
                refresh_calc_pseudo_records_after_step0,
            )
            
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
                    
                    # Refresh calc records with actual file info
                    refresh_calc_pseudo_records_after_step0(
                        calculation.project.root,
                        calculation.dir,
                        calculation.species_map or {},
                    )
                    
                    # Log warnings if any
                    if report.warnings:
                        # TODO: Consider logging these warnings somewhere visible
                        pass
            except Exception as e:
                # Step0 failure: mark calculation as failed
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
        
        for step in calculation.steps:
            # If a previous step failed in strict mode, mark remaining steps as SKIPPED
            if calculation_failed:
                step_type = _coerce_step_type(step.step_type) if step.step_type else StepType.CUSTOM
                logger.warning(
                    f"[CALCULATION_RUNNER] Step {step.id} (type={step_type}) SKIPPED because calculation_failed=True"
                )
                summary = StepResultSummary(
                    step_id=step.id,
                    step_type=step_type,
                    status=StepStatus.SKIPPED,
                    working_dir=calculation.raw_dir,
                    input_file=step.input_file if hasattr(step, 'input_file') else Path(),
                    output_file=Path(),
                    reference_file=step.reference_output,
                    message="Step skipped because a previous step failed",
                    metrics={},
                )
                step_summaries.append(summary)
                continue

            # E. Logging: Only essential info at INFO level
            step_type_str = str(step.step_type.value) if step.step_type else "unknown"
            logger.info(f"[CALCULATION_RUNNER] Entering step: {step.id} ({step_type_str})")
            
            engine = self.engine_registry.get(step.engine)
            # Use compute_io_dir_from_calculation_model to ensure consistency with server-side planned_io_dir
            # calculation.raw_dir uses the same logic (calculation_dir / working_dir, default "raw")
            raw_dir = calculation.raw_dir
            raw_dir.mkdir(parents=True, exist_ok=True)

            # Execute step with exception handling
            try:
                result = step.run(
                    engine=engine,
                    calculation_raw_dir=raw_dir,
                    project_root=calculation.project.root,
                    species_map=calculation.species_map,
                )
                # E. Logging: Essential info only
                logger.debug(
                    f"[CALCULATION_RUNNER] Step {step.id} run() completed: "
                    f"success={result.success}, returncode={getattr(result, 'return_code', 'N/A')}, "
                    f"output_file={result.output_file.name if result.output_file else None}"
                )
            except Exception as e:
                import traceback
                tb_str = traceback.format_exc()
                logger.exception(
                    f"[CALCULATION_RUNNER] Step {step.id} run() raised exception: {type(e).__name__}: {e}"
                )
                # Create a failed StepResult from the exception
                from quantumvitas.calculation.results import StepResult
                result = StepResult(
                    step_type=step_type_str,
                    input_file=getattr(step, 'input_file', Path()),
                    success=False,
                    error=f"{type(e).__name__}: {str(e)}\n\nTraceback:\n{tb_str[:500]}",  # First 500 chars of traceback
                    return_code=-1,
                )
            
            # E. Evaluation must not fail if output_file doesn't exist
            # For Wannier90 steps, output_file is the artifact (<seed>.wout), not stdout
            # For QE steps, we can use output_file if available, or fall back to stdout
            output_text = ""
            wannier90_step_types = {"w90_preproc", "w90_run", "pw2wannier90"}
            is_wannier90_step = result.step_type and str(result.step_type).lower() in wannier90_step_types
            
            if is_wannier90_step:
                # For Wannier90 steps, use stdout field (from capture file) for evaluation
                # output_file points to artifact (<seed>.wout), not stdout
                output_text = result.stdout if result.stdout else ""
                logger.debug(f"[CALCULATION_RUNNER] Wannier90 step: using stdout field ({len(output_text)} chars) for evaluation")
                if result.output_file:
                    logger.debug(f"[CALCULATION_RUNNER] Primary artifact: {result.output_file} (exists={result.output_file.exists()})")
            else:
                # For QE steps, try to read from output_file
                if result.output_file and result.output_file.exists():
                    try:
                        output_text = result.output_file.read_text()
                        logger.debug(f"[CALCULATION_RUNNER] Read {len(output_text)} chars from output_file: {result.output_file}")
                    except Exception as e:
                        logger.warning(f"[CALCULATION_RUNNER] Failed to read output_file {result.output_file}: {e}")
                        # Fall back to stdout field
                        output_text = result.stdout if result.stdout else ""
                else:
                    # Fall back to stdout field if output_file doesn't exist
                    output_text = result.stdout if result.stdout else ""
                    logger.debug(
                        f"[CALCULATION_RUNNER] Step {step.id} output_file not available, using stdout field: "
                        f"output_file={result.output_file}, stdout_length={len(output_text)}"
                    )
            
            step_mode = StepMode.STRICT if calculation.mode == StepMode.STRICT else step.mode

            step_type = _coerce_step_type(result.step_type)
            
            # E. Wrap evaluation in try/except to prevent silent abort
            try:
                step_status, message, metrics = evaluate_step_result(
                    mode=step_mode,
                    step_type=step_type,
                    output_text=output_text,
                    reference_file=step.reference_output,
                    step_result_return_code=getattr(result, 'return_code', None),
                )
                logger.debug(f"[CALCULATION_RUNNER] Evaluation completed: step_status={step_status}, message={message[:100]}")
            except Exception as e:
                import traceback
                tb_str = traceback.format_exc()
                logger.exception(f"[CALCULATION_RUNNER] Evaluation raised exception: {type(e).__name__}: {e}")
                # On evaluation failure, use result.success as primary indicator
                if result.success:
                    step_status = StepStatus.SUCCESS
                    message = f"Step completed successfully (evaluation exception: {type(e).__name__})"
                else:
                    step_status = StepStatus.FAILED
                    message = f"Step failed (evaluation exception: {type(e).__name__}: {str(e)})\n\nTraceback:\n{tb_str[:500]}"
                metrics = {}
            
            # E. Logging: Evaluation results at DEBUG level
            logger.debug(
                f"[CALCULATION_RUNNER] Step {step.id} evaluation: step_status={step_status}, "
                f"message_length={len(message) if message else 0}"
            )
            
            # E. Logging: Failure messages concise at INFO level
            if step_status != StepStatus.SUCCESS:
                # Enhance message with return code and stderr reference
                enhanced_message = message
                if hasattr(result, 'return_code') and result.return_code is not None:
                    enhanced_message += f" [return_code={result.return_code}]"
                # Reference stderr file instead of embedding content at INFO level
                if hasattr(result, 'stderr_file') and result.stderr_file:
                    enhanced_message += f" (see {result.stderr_file.name})"
                elif hasattr(result, 'stderr') and result.stderr:
                    # Fallback: include last 50 lines if stderr_file not available
                    stderr_preview = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
                    enhanced_message += f"\n\nStderr preview:\n{stderr_preview}"
                if result.error:
                    enhanced_message += f"\n\nError: {result.error}"
                message = enhanced_message
                logger.warning(f"[CALCULATION_RUNNER] Step {step.id} ({step_type_str}) failed: {message[:150]}")
            
            combined_metrics = dict(getattr(result, "parsed_output", {}) or {})
            for key, value in (metrics or {}).items():
                if value is not None:
                    combined_metrics[key] = value
            summary = StepResultSummary(
                step_id=step.id,
                step_type=step_type,
                status=step_status,
                working_dir=raw_dir,
                input_file=result.input_file,
                output_file=result.output_file,
                reference_file=step.reference_output,
                message=message,
                metrics=combined_metrics,
            )
            step_summaries.append(summary)

            if step_status != StepStatus.SUCCESS:
                prev_failed = calculation_failed
                status = StepStatus.FAILED
                calculation_failed = True
                logger.debug(f"[CALCULATION_RUNNER] calculation_failed: {prev_failed} -> {calculation_failed}")
                if calculation.mode == StepMode.STRICT:
                    logger.info(f"[CALCULATION_RUNNER] Strict mode: stopping after step {step.id} failure")
                    # In strict mode, stop execution and mark remaining steps as SKIPPED
                    break

        finished = datetime.now(timezone.utc)
        # Get the actual I/O directory used by the runner (source of truth)
        io_dir = calculation.raw_dir.resolve() if calculation.raw_dir else None
        return CalculationResult(
            calculation_id=calculation.id,
            mode=calculation.mode,
            steps=step_summaries,
            status=status,
            started_at=started,
            finished_at=finished,
            io_dir=io_dir,  # The actual I/O directory used by the runner
        )

