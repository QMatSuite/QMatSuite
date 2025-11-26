"""
Standardized QE step execution and verification.

This module provides a unified interface for running QE steps and verifying results.
All tests should use these functions instead of implementing their own execution logic.
"""

from pathlib import Path
from typing import Optional, Tuple
import time
import shutil

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.qe_workflow import StepResult
from quantumvitas.io import QEInputParser, QEInput, QEInputGenerator, QENamelist, QEModule
from quantumvitas.core.engines import ensure_pseudopotentials
from .qe_step_verification import verify_step_result, verify_step_with_reference


def _safe_copy(src: Path, dst: Path) -> None:
    """Best-effort file copy that never raises and skips self-copies."""
    if src == dst:
        return
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except Exception:
        pass


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


def set_outdir_to_temp(qe_input: QEInput, project_root: Path) -> None:
    """
    Set outdir parameter in QE input to ./outdir (relative to working directory).
    
    All QE runs execute in their working directory, and outdir is created as
    a subdirectory ./outdir within the working directory.
    
    Some modules (ph.x, q2r.x, matdyn.x, dynmat.x) don't use &control namelist.
    For these modules, outdir should be added to their own namelist if present.
    
    Args:
        qe_input: Parsed QE input object
        project_root: Project root directory (not used, kept for compatibility)
    """
    # Use relative path: ./outdir (relative to working directory)
    # All QE runs execute in working_dir, and outdir is ./outdir within working_dir
    outdir_rel = "./outdir"
    
    # Detect module type
    module = qe_input.module or qe_input.detect_module()
    
    # Modules that don't use &control namelist
    no_control_modules = [QEModule.PH, QEModule.Q2R, QEModule.MATDYN, QEModule.DYNMAT]
    
    # Check all namelists for outdir parameter
    found_outdir = False
    for namelist in qe_input.namelists:
        if "outdir" in namelist.parameters:
            namelist.parameters["outdir"] = outdir_rel
            found_outdir = True
    
    # If outdir not found, add it to appropriate namelist
    if not found_outdir:
        if module in no_control_modules:
            # For modules without &control:
            # ph.x: add outdir to &inputph (ph.x needs outdir to read from pw.x output)
            # q2r.x, matdyn.x, dynmat.x: don't add outdir (they read from files, not .save directories)
            if module == QEModule.PH:
                for namelist in qe_input.namelists:
                    if namelist.name.lower() == "inputph":
                        namelist.parameters["outdir"] = outdir_rel
                        found_outdir = True
                        break
            # For q2r.x, matdyn.x, dynmat.x, don't add outdir if not present
        else:
            # For modules with &control (pw.x, etc.), add to &control
            control_namelist = None
            for namelist in qe_input.namelists:
                if namelist.name.lower() == "control":
                    control_namelist = namelist
                    break
            
            if control_namelist:
                control_namelist.parameters["outdir"] = outdir_rel
            else:
                control_namelist = QENamelist("control", {"outdir": outdir_rel})
                qe_input.namelists.insert(0, control_namelist)


def set_pseudo_dir_to_temp(qe_input: QEInput, project_root: Path) -> None:
    """
    Force pseudo_dir to the unified project_root/pseudo directory.
    
    Some modules (ph.x, q2r.x, matdyn.x, dynmat.x) don't use &control namelist
    and typically don't need pseudo_dir. For these modules we only rewrite the
    parameter when it already exists in the input.
    """
    pseudo_dir_path = str((project_root / "pseudo").resolve())
    
    # Detect module type
    module = qe_input.module or qe_input.detect_module()
    
    # Modules that don't use &control namelist and typically don't need pseudo_dir
    no_control_modules = [QEModule.PH, QEModule.Q2R, QEModule.MATDYN, QEModule.DYNMAT]
    
    # Check all namelists for pseudo_dir parameter
    found_pseudo_dir = False
    for namelist in qe_input.namelists:
        if "pseudo_dir" in namelist.parameters:
            namelist.parameters["pseudo_dir"] = pseudo_dir_path
            found_pseudo_dir = True
    
    # If pseudo_dir not found, add it to appropriate namelist
    # For modules without &control, only add if it's already present (don't add new)
    if not found_pseudo_dir:
        if module in no_control_modules:
            # For ph.x, q2r.x, etc., don't add pseudo_dir (they don't need it)
            # They read from pw.x output files
            pass
        else:
            # For modules with &control (pw.x, etc.), add to &control
            control_namelist = None
            for namelist in qe_input.namelists:
                if namelist.name.lower() == "control":
                    control_namelist = namelist
                    break
            
            if control_namelist:
                control_namelist.parameters["pseudo_dir"] = pseudo_dir_path
            else:
                control_namelist = QENamelist("control", {"pseudo_dir": pseudo_dir_path})
                qe_input.namelists.insert(0, control_namelist)


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
    # Auto-detect project root if not provided
    if project_root is None:
        # Try to find project root by looking for src/quantumvitas
        current = Path(__file__).parent
        while current != current.parent:
            if (current / "src" / "quantumvitas").exists():
                project_root = current
                break
            current = current.parent
        if project_root is None:
            project_root = Path.cwd()
    
    # Ensure pseudopotentials are available before running
    # Use unified pseudo directory at project root
    unified_pseudo_dir = project_root / "pseudo"
    if not ensure_pseudopotentials(input_file, working_dir, unified_pseudo_dir, None):
        # If pseudopotentials are missing, return error result
        return StepResult(
            step_type=step_type or "unknown",
            input_file=input_file,
            success=False,
            error="Failed to obtain required pseudopotentials"
        ), False, "Failed to obtain required pseudopotentials"
    
    # Determine working directory:
    # - If working_dir is provided, always respect it.
    # - If not provided, fall back to a default temp/test_outputs/{category}/ directory.
    if working_dir is None:
        working_dir = get_default_working_dir(project_root, category)
    else:
        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
    
    # Create outdir subdirectory in working_dir
    outdir_path = working_dir / "outdir"
    outdir_path.mkdir(parents=True, exist_ok=True)
    
    # Parse input file and set outdir/pseudo_dir
    # The parser now correctly handles all modules including format-sensitive ones
    # (ph.x q-points, q2r.x simple format, etc.) via extra_data_lines
    try:
        qe_input = QEInputParser.parse_file(input_file)
        set_outdir_to_temp(qe_input, project_root)
        set_pseudo_dir_to_temp(qe_input, project_root)
        
        # Generate modified input file directly in working directory
        # The generator now correctly handles extra_data_lines (e.g., ph.x q-points)
        working_dir_input = working_dir / input_file.name
        QEInputGenerator.write_file(qe_input, working_dir_input)
    except Exception:
        # If parsing fails, fall back to original file
        working_dir_input = working_dir / input_file.name
        if working_dir_input != input_file:
            shutil.copy2(input_file, working_dir_input)
        else:
            working_dir_input = input_file
    
    input_filename = input_file.stem

    # Save original and modified input files alongside outputs for debugging
    original_input_copy = working_dir / f"{input_filename}_original.in"
    _safe_copy(input_file, original_input_copy)

    modified_input_copy = working_dir / f"{input_filename}_modified.in"
    _safe_copy(working_dir_input, modified_input_copy)
    
    # Auto-detect step type if not provided
    if step_type is None:
        step_type = qe_engine.detect_step_type(working_dir_input)
    
    # Run the step in the working directory
    # QE will execute in working_dir, and outdir will be ./outdir within working_dir
    step_result = qe_engine.run_step(
        input_file=working_dir_input,
        working_dir=working_dir,  # Run in working directory
        step_type=step_type,
        timeout=timeout
    )
    
    # The output file should already be in working_dir
    # Ensure step_result.output_file points to the correct location
    expected_output = working_dir / f"{input_filename}.out"
    if step_result.output_file and step_result.output_file.exists():
        # If output file is in a different location, update the reference
        if step_result.output_file != expected_output:
            step_result.output_file = expected_output
    
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
        # Enhanced error reporting for easier debugging of CI/workflow failures
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
