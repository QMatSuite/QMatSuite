"""
Standardized QE step execution and verification.

This module provides a unified interface for running QE steps and verifying results.
All tests should use these functions instead of implementing their own execution logic.
"""

from pathlib import Path
from typing import Optional, Tuple
import time

from src.quantumvitas.core.engines.qe import QuantumEspressoEngine
from src.quantumvitas.core.engines.qe_workflow import StepResult
from src.quantumvitas.core.engines.qe_input import QEInputParser, QEInput
from .qe_step_verification import verify_step_result, verify_step_with_reference


def set_outdir_to_temp(qe_input: QEInput, project_root: Path) -> None:
    """
    Set outdir parameter in QE input to temp/outdir.
    
    Args:
        qe_input: Parsed QE input object
        project_root: Project root directory
    """
    temp_outdir = project_root / "temp" / "outdir"
    temp_outdir.mkdir(parents=True, exist_ok=True)
    outdir_abs = str(temp_outdir.absolute())
    
    # Check all namelists for outdir parameter
    found_outdir = False
    for namelist in qe_input.namelists:
        if "outdir" in namelist.parameters:
            namelist.parameters["outdir"] = outdir_abs
            found_outdir = True
    
    # If outdir not found, add it to control namelist
    if not found_outdir:
        control_namelist = None
        for namelist in qe_input.namelists:
            if namelist.name.lower() == "control":
                control_namelist = namelist
                break
        
        if control_namelist:
            control_namelist.parameters["outdir"] = outdir_abs
        else:
            from src.quantumvitas.core.engines.qe_input import QENamelist
            control_namelist = QENamelist("control", {"outdir": outdir_abs})
            qe_input.namelists.insert(0, control_namelist)


def set_pseudo_dir_to_temp(qe_input: QEInput, project_root: Path) -> None:
    """
    Set pseudo_dir parameter in QE input to temp/pseudo.
    
    Args:
        qe_input: Parsed QE input object
        project_root: Project root directory
    """
    temp_pseudo_dir = project_root / "temp" / "pseudo"
    temp_pseudo_dir.mkdir(parents=True, exist_ok=True)
    pseudo_dir_abs = str(temp_pseudo_dir.absolute())
    
    # Check all namelists for pseudo_dir parameter
    found_pseudo_dir = False
    for namelist in qe_input.namelists:
        if "pseudo_dir" in namelist.parameters:
            namelist.parameters["pseudo_dir"] = pseudo_dir_abs
            found_pseudo_dir = True
    
    # If pseudo_dir not found, add it to control namelist
    if not found_pseudo_dir:
        control_namelist = None
        for namelist in qe_input.namelists:
            if namelist.name.lower() == "control":
                control_namelist = namelist
                break
        
        if control_namelist:
            control_namelist.parameters["pseudo_dir"] = pseudo_dir_abs
        else:
            from src.quantumvitas.core.engines.qe_input import QENamelist
            control_namelist = QENamelist("control", {"pseudo_dir": pseudo_dir_abs})
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
    project_root: Optional[Path] = None
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
    
    # Parse input file and set outdir/pseudo_dir
    qe_input = QEInputParser.parse_file(input_file)
    set_outdir_to_temp(qe_input, project_root)
    set_pseudo_dir_to_temp(qe_input, project_root)
    
    # Generate modified input file in working directory
    from src.quantumvitas.core.engines.qe_input import QEInputGenerator
    modified_input = working_dir / input_file.name
    QEInputGenerator.write_file(qe_input, modified_input)
    
    # Auto-detect step type if not provided
    if step_type is None:
        step_type = qe_engine.detect_step_type(modified_input)
    
    # Run the step
    step_result = qe_engine.run_step(
        input_file=modified_input,
        working_dir=working_dir,
        step_type=step_type,
        timeout=timeout
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
    project_root: Optional[Path] = None
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
        project_root=project_root
    )
    
    if not success:
        raise AssertionError(
            f"Step {step_result.step_type} failed: {message}\n"
            f"Input file: {input_file}\n"
            f"Output file: {step_result.output_file}\n"
            f"Error: {step_result.error}"
        )
    
    return step_result
