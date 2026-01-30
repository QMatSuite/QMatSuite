"""
Standardized QE step execution and verification.

This module provides a unified interface for running QE steps and verifying results.
All tests should use these functions instead of implementing their own execution logic.

TERMINOLOGY CLARIFICATION:
--------------------------
This module uses specific terminology to distinguish test fixtures from product runtime directories:

1. fixture_dir (tests only):
   - Read-only template directory containing input files (.in templates)
   - Used as source for copying inputs to sandbox
   - Must never be used as working_dir for run_step()
   - Example: tests/integration/test_pw_step_specs.py uses fixture_dir = working_dir / "raw"

2. sandbox_dir / execution_dir (tests only):
   - Writable temporary directory where QE execution happens
   - Created via create_sandbox_working_dir()
   - Contains copied inputs, materialized pseudos (sandbox_dir/pseudo/), QE outputs
   - This is what gets passed as working_dir to run_step()

3. calculation.raw_dir (product only):
   - Writable runtime I/O directory: project_root/calculations/<calc_id>/raw/
   - Part of the project structure, used for actual QE execution in product mode
   - NOT the same as test fixture_dir (which is read-only)

4. working_dir (context-dependent):
   - In tests: Base test directory (may contain fixture_dir as subdirectory)
   - In product: Same as calculation.raw_dir (the I/O directory name)

The sandbox pattern ensures:
- fixture_dir stays read-only (no execution, no pseudo materialization)
- All QE execution happens in sandbox_dir (temporary, isolated)
- Tests never execute QE in directories under repo root (except reading fixtures)
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

    Layout: {repo_root}/.tmp/runs/{category}/{test_name}/
    Note: project_root is ignored for test runs; uses repo .tmp/runs/
    """
    from quantumvitas.core.paths import tmp_runs_dir
    
    base = tmp_runs_dir()
    if category:
        base = base / category
    if test_name:
        safe_name = (
            test_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        )
        base = base / safe_name
    base.mkdir(parents=True, exist_ok=True)
    return base


def create_sandbox_working_dir(
    base_dir: Path,
    prefix: str = "sandbox_",
) -> Path:
    """
    Create a temporary sandbox working directory for test execution.
    
    Terminology clarification:
    - fixture_dir: Read-only template directory containing input files (tests only)
    - sandbox_dir: Writable execution directory where QE runs (tests only)
    - calculation.raw_dir: Writable runtime I/O directory in product (project/calc/raw)
    
    This function creates a sandbox_dir to ensure fixture directories stay read-only
    and all QE execution happens in a separate temporary directory.
    
    Args:
        base_dir: Base directory for creating sandbox
        prefix: Prefix for sandbox directory name
        
    Returns:
        Path to created sandbox directory
    """
    import tempfile
    import uuid
    
    # Create a unique sandbox directory
    sandbox_name = f"{prefix}{uuid.uuid4().hex[:8]}"
    sandbox_dir = base_dir / sandbox_name
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    return sandbox_dir


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
    # Determine working directory first (needed for boundary detection)
    if working_dir is None:
        # If project_root is provided, use it to determine working_dir
        if project_root is not None:
            project_root = Path(project_root).resolve()
            # Validate project_root is not repo root
            from quantumvitas.core.pseudo_config import _find_quantumvitas_root
            repo_root = _find_quantumvitas_root()
            if repo_root and project_root == repo_root.resolve():
                raise ValueError(
                    f"Project root cannot be the repository root. "
                    f"Provided project_root={project_root} is the repo root, which is invalid."
                )
            working_dir = get_default_working_dir(project_root, category)
        else:
            # No project_root and no working_dir: use tmp
            import tempfile
            working_dir = Path(tempfile.mkdtemp(prefix="qe_test_"))
    else:
        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
    
    # If project_root not provided, try to detect from working_dir
    # In tests, we want to sandbox the search, so use working_dir as boundary
    if project_root is None:
        # Sandbox: stop search at working_dir (tests should create projects within tmp)
        # This prevents search from escaping into repo root
        from quantumvitas.core.project_utils import find_project_root
        from quantumvitas.core.pseudo_config import _find_quantumvitas_root
        
        # Use working_dir as stop_at boundary to sandbox the search
        detected = find_project_root(start=working_dir, stop_at=working_dir)
        if detected:
            # Validate it's not repo root (shouldn't happen with stop_at, but be safe)
            repo_root = _find_quantumvitas_root()
            if repo_root and detected.resolve() == repo_root.resolve():
                # Repo root detected - treat as standalone mode
                project_root = None
            else:
                project_root = detected
        # If not found, project_root stays None (standalone mode)
    else:
        project_root = Path(project_root).resolve()
        # Validate project_root is not repo root
        from quantumvitas.core.pseudo_config import _find_quantumvitas_root
        repo_root = _find_quantumvitas_root()
        if repo_root and project_root == repo_root.resolve():
            raise ValueError(
                f"Project root cannot be the repository root. "
                f"Provided project_root={project_root} is the repo root, which is invalid."
            )
    
    try:
        prepared = prepare_input_step(
            input_file=input_file,
            working_dir=working_dir,
            project_root=project_root,
        )
    except RuntimeError as exc:
        message = str(exc)
        return StepResult(
            step_type_spec=step_type or "unknown",
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
            f"Step type (inferred): {step_result.step_type_spec}",
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
