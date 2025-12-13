"""
Standardized QE step execution and verification.

This module provides a unified interface for running QE steps and verifying results.
All tests should use these functions instead of implementing their own execution logic.
"""

from pathlib import Path
from typing import Optional, Tuple
import time

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.qe_calculation import StepResult
from quantumvitas.calculation.input_runner import (
    prepare_input_step,
    run_prepared_step,
    detect_project_root,
)
from .qe_step_verification import verify_step_result, verify_step_with_reference


def get_default_working_dir(
    project_root: Path,
    category: Optional[str] = None,
    test_name: Optional[str] = None,
) -> Path:
    """
    Return a default working directory for QE steps.

    Layout: {project_root}/temp/test_outputs/{category}/{test_name}/
    """
    base = project_root / "temp" / "test_outputs"
    if category:
        base = base / category
    if test_name:
        safe_name = (
            test_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        )
        base = base / safe_name
    base.mkdir(parents=True, exist_ok=True)
    return base


def run_and_verify_step(
    input_file: Path,
    qe_engine: QuantumEspressoEngine,
    working_dir: Path,
    reference_file: Optional[Path] = None,
    category: Optional[str] = None,
    timeout: Optional[float] = None,
    step_type: Optional[str] = None,
    tolerance: Optional[float] = None,
    project_root: Optional[Path] = None,
    step_index: int = 1,
) -> Tuple[StepResult, bool, str]:
    """
    Run a QE step and verify the result.
    
    This is the main function that tests should use. It:
    1. Auto-detects step type from input file
    2. Sets outdir and pseudo_dir to temp directories
    3. Runs the step using qe_engine.run_step()
    4. Verifies the result based on step type (scf->energy, nscf->fermi, other->JOB DONE)
    
    Args:
        input_file: Path to QE input file
        qe_engine: Configured QuantumEspressoEngine
        working_dir: Working directory for execution
        reference_file: Optional reference output file for comparison
        category: Test category name (e.g., "pw_scf", "ph_1d") for threshold selection
        timeout: Optional timeout in seconds
        step_type: Optional step type (auto-detected if not provided)
        tolerance: Optional custom tolerance (overrides category-based threshold)
        project_root: Project root directory (auto-detected if not provided)
    
    Returns:
        (step_result, success, message) tuple
    """
    project_root = detect_project_root(project_root or Path(__file__).parent)
    
    # Determine working directory:
    # - If working_dir is provided, always respect it.
    # - If not provided, fall back to a default temp/test_outputs/{category}/ directory.
    if working_dir is None:
        working_dir = get_default_working_dir(project_root, category)
    else:
        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        prepared = prepare_input_step(
            input_file=input_file,
            working_dir=working_dir,
            project_root=project_root,
        )
    except RuntimeError as exc:
        message = str(exc)
        return StepResult(
            step_type=step_type or "unknown",
            input_file=input_file,
            success=False,
            error=message,
        ), False, message
    
    # Auto-detect step type if not provided
    if step_type is None:
        step_type = qe_engine.detect_step_type(prepared.modified_input)
    
    step_result = run_prepared_step(
        engine=qe_engine,
        prepared_step=prepared,
        step_type=step_type,
        timeout=timeout,
    )
    
    # Verify the result
    success, message = verify_step_result(
        step_result=step_result,
        reference_file=reference_file,
        category=category,
        tolerance=tolerance
    )
    
    return step_result, success, message


def run_and_verify_step_with_assert(
    input_file: Path,
    qe_engine: QuantumEspressoEngine,
    working_dir: Path,
    reference_file: Optional[Path] = None,
    category: Optional[str] = None,
    timeout: Optional[float] = None,
    step_type: Optional[str] = None,
    tolerance: Optional[float] = None,
    project_root: Optional[Path] = None,
    step_index: int = 1,
) -> StepResult:
    """
    Run a QE step, verify the result, and raise AssertionError if verification fails.
    
    This is a convenience function for use in pytest tests.
    
    Args:
        input_file: Path to QE input file
        qe_engine: Configured QuantumEspressoEngine
        working_dir: Working directory for execution
        reference_file: Optional reference output file for comparison
        category: Test category name for threshold selection
        timeout: Optional timeout in seconds
        step_type: Optional step type (auto-detected if not provided)
        tolerance: Optional custom tolerance
        project_root: Project root directory (auto-detected if not provided)
    
    Returns:
        StepResult object
    
    Raises:
        AssertionError: If step execution or verification fails
    """
    step_result, success, message = run_and_verify_step(
        input_file=input_file,
        qe_engine=qe_engine,
        working_dir=working_dir,
        reference_file=reference_file,
        category=category,
        timeout=timeout,
        step_type=step_type,
        tolerance=tolerance,
        project_root=project_root,
        step_index=step_index,
    )
    
    if not success:
        # Enhanced error reporting for easier debugging of CI/calculation failures
        details = [
            f"Step index: {step_index}",
            f"Step type (inferred): {step_result.step_type}",
            f"Category: {category or 'N/A'}",
            f"Working dir: {Path(working_dir).absolute()}",
            f"Input file: {Path(input_file).absolute()}",
            f"Output file: {Path(step_result.output_file).absolute() if step_result.output_file else 'None'}",
            f"Reference file: {Path(reference_file).absolute() if reference_file else 'None'}",
            f"Verification message: {message}",
            f"Engine error: {step_result.error or 'None'}",
            # Placeholder for future structured diff support
            f"Diff summary: {message}",
        ]
        raise AssertionError("Step execution/verification failed:\n" + "\n".join(details))
    
    return step_result
