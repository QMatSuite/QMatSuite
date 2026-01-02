"""
Quantum ESPRESSO calculation execution.

This module provides step and calculation execution capabilities for QE calculations.
Steps are the basic execution units (scf, nscf, dos, bands, etc.), and calculations
combine multiple steps in sequence.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import os
import time

from quantumvitas.io import QEInput, QEInputParser, QEModule

if TYPE_CHECKING:
    from .qe import QuantumEspressoEngine


@dataclass
class StepResult:
    """Result of executing a single QE calculation step."""
    step_type: str
    input_file: Path
    output_file: Optional[Path] = None
    success: bool = False
    return_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    execution_time: float = 0.0
    parsed_output: Optional[Dict[str, Any]] = None


@dataclass
class CalculationResult:
    """Result of executing a QE calculation (multiple steps)."""
    steps: List[StepResult] = field(default_factory=list)
    success: bool = False
    total_time: float = 0.0
    error: Optional[str] = None


class QECalculationRunner:
    """
    Runner for QE calculation steps and calculations.
    
    A step is a single QE calculation (e.g., SCF, NSCF, DOS, bands).
    A calculation is a sequence of steps that depend on each other.
    """
    
    def __init__(self, engine: "QuantumEspressoEngine"):
        """
        Initialize calculation runner.
        
        Args:
            engine: QuantumEspressoEngine instance
        """
        self.engine = engine
    
    def detect_step_type(self, input_file: Path) -> str:
        """
        Detect step type from input file.
        
        Detection logic:
        1. Parse input file to get QEInput
        2. Detect QE module (pw, ph, dos, bands, etc.)
        3. For pw.x: detect calculation type (scf, nscf, bands, opt, md, etc.)
        4. For other modules: use module name as step type
        
        Args:
            input_file: Path to QE input file
            
        Returns:
            Step type string (e.g., "scf", "nscf", "dos", "bands", "ph", etc.)
        """
        qe_input = QEInputParser.parse_file(input_file)
        module = qe_input.detect_module()
        
        # For pw.x, detect calculation type from control namelist
        if module == QEModule.PW:
            control = qe_input.get_namelist('control')
            if control:
                calculation = control.get('calculation', 'scf').lower()
                # Map QE calculation types to step types
                # Note: 'bands' in pw.x is still pw.x, not bands.x
                calculation_map = {
                    'scf': 'scf',
                    'nscf': 'nscf',
                    'bands': 'bands_pw',  # pw.x bands calculation (not bands.x)
                    'relax': 'opt',
                    'vc-relax': 'opt',
                    'md': 'md',
                    'vc-md': 'md',
                }
                return calculation_map.get(calculation, 'scf')
            return 'scf'  # Default for pw.x
        
        # For other modules, use module name as step type
        module_to_step = {
            QEModule.PH: 'ph',
            QEModule.DOS: 'dos',
            QEModule.BANDS: 'bands',  # bands.x
            QEModule.PROJWFC: 'projwfc',
            QEModule.Q2R: 'q2r',
            QEModule.MATDYN: 'matdyn',
            QEModule.PP: 'pp',
            QEModule.NEB: 'neb',
            QEModule.CP: 'cp',
            QEModule.LD1: 'ld1',
            QEModule.HP: 'hp',
            QEModule.PWCOND: 'pwcond',
            QEModule.DYNMAT: 'dynmat',
            QEModule.GIPAW: 'gipaw',
        }
        
        return module_to_step.get(module, 'unknown')
    
    def run_step(
        self,
        input_file: Path,
        working_dir: Path,
        step_type: Optional[str] = None,
        timeout: Optional[float] = None,
        environment: Optional[Dict[str, str]] = None
    ) -> StepResult:
        """
        Run a single QE calculation step.
        
        Args:
            input_file: Path to QE input file
            working_dir: Working directory for execution
            step_type: Optional step type (auto-detected if not provided)
            timeout: Optional timeout in seconds
            environment: Optional environment variables dict
            
        Returns:
            StepResult with execution results
        """
        start_time = time.time()
        
        # Detect step type if not provided
        if step_type is None:
            step_type = self.detect_step_type(input_file)
        
        # Get executable for this step type
        executable = self.engine.EXECUTABLE_MAP.get(step_type, "pw.x")
        
        # Build command
        command = self.engine.build_command(step_type, input_file, working_dir)
        
        # Prepare environment
        env = os.environ.copy()
        if environment:
            env.update(environment)
        
        # Set OMP_NUM_THREADS if not already set
        if 'OMP_NUM_THREADS' not in env:
            env['OMP_NUM_THREADS'] = str(self.engine.config.omp_threads)
        
        # Constitution: QE runtime only reads project/pseudo
        # Step0 has already prepared pseudos in project/pseudo (if in project mode)
        if 'ESPRESSO_PSEUDO' not in env:
            from quantumvitas.core.project_utils import find_project_root
            from quantumvitas.core.pseudo_config import _find_quantumvitas_root
            
            # Try to detect project root
            detected_project_root = find_project_root(start=working_dir, stop_at=None)
            
            # Validate it's not repo root
            if detected_project_root:
                repo_root = _find_quantumvitas_root()
                if repo_root and detected_project_root.resolve() == repo_root.resolve():
                    detected_project_root = None
            
            if detected_project_root:
                # Project mode: use project/pseudo (Step0 has prepared it)
                project_pseudo_dir = detected_project_root / "pseudo"
            else:
                # Standalone mode: use working_dir/pseudo
                project_pseudo_dir = working_dir / "pseudo"
            
            # GUARD: Never use repo_root/pseudo
            repo_root = _find_quantumvitas_root()
            if repo_root:
                repo_pseudo = (repo_root / "pseudo").resolve()
                project_pseudo_resolved = project_pseudo_dir.resolve()
                if project_pseudo_resolved == repo_pseudo:
                    raise RuntimeError(
                        f"BUG: ESPRESSO_PSEUDO attempted to use repo_root/pseudo at {project_pseudo_dir}. "
                        f"Internal pseudo library must be at resources/pseudo, not repo_root/pseudo."
                    )
            
            # Ensure directory exists (Step0 should have created project/pseudo, but be safe for standalone)
            project_pseudo_dir.mkdir(parents=True, exist_ok=True)
            env['ESPRESSO_PSEUDO'] = str(project_pseudo_dir.absolute())
        
        # Also ensure pseudopotentials are in working_dir (QE may look there too)
        # This is handled by run_and_verify_step, but we ensure it here as well
        # by checking if working_dir has the pseudopotentials
        
        # Determine output file (use relative path in working_dir)
        input_stem = input_file.stem
        
        # Wannier90 steps have different output files
        if step_type in ("w90_preproc", "w90_run"):
            # Wannier90 writes to seedname.wout
            output_filename = f"{input_stem}.wout"
        else:
            output_filename = f"{input_stem}.out"
        output_file = working_dir / output_filename
        
        # Check if step uses stdin or command-line arguments
        uses_stdin = self.engine.uses_stdin(step_type)
        
        # Execute command
        # Write stdout directly to output file in working_dir
        try:
            if uses_stdin:
                # Standard QE execution with stdin redirection
                stdin_file = input_file
                with open(stdin_file, 'r') as stdin_handle:
                    with open(output_file, 'w') as output_handle:
                        process = subprocess.Popen(
                            command,
                            stdin=stdin_handle,
                            stdout=output_handle,
                            stderr=subprocess.PIPE,
                            cwd=str(working_dir),
                            env=env,
                            text=True
                        )
                        
                        try:
                            _, stderr = process.communicate(timeout=timeout)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            _, stderr = process.communicate()
                            return StepResult(
                                step_type=step_type,
                                input_file=input_file,
                                success=False,
                                error=f"Step execution timed out after {timeout}s",
                                stdout="",
                                stderr=stderr,
                                execution_time=time.time() - start_time
                            )
            else:
                # Wannier90 execution without stdin (uses command-line seedname)
                # Wannier90 writes its own output to seedname.wout
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(working_dir),
                    env=env,
                    text=True
                )
                
                try:
                    _, stderr = process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    _, stderr = process.communicate()
                    return StepResult(
                        step_type=step_type,
                        input_file=input_file,
                        success=False,
                        error=f"Step execution timed out after {timeout}s",
                        stdout="",
                        stderr=stderr,
                        execution_time=time.time() - start_time
                    )
            
            # Common result handling for both stdin and non-stdin cases
            return_code = process.returncode
            
            # Read stdout from output file for StepResult
            stdout = output_file.read_text() if output_file.exists() else ""
            
            # Ensure output file ends with a newline
            if stdout and not stdout.endswith('\n'):
                output_file.write_text(stdout + '\n')
                stdout = stdout + '\n'
            
            # Parse output if successful
            parsed_output = None
            if return_code == 0 and output_file.exists():
                try:
                    parsed_output = self.engine.parse_output(output_file, step_type)
                except Exception:
                    pass  # Parsing is optional
            
            return StepResult(
                step_type=step_type,
                input_file=input_file,
                output_file=output_file if output_file.exists() else None,
                success=(return_code == 0),
                return_code=return_code,
                stdout=stdout,
                stderr=stderr,
                error=None if return_code == 0 else f"Step failed with return code {return_code}",
                execution_time=time.time() - start_time,
                parsed_output=parsed_output
            )
        
        except Exception as e:
            return StepResult(
                step_type=step_type,
                input_file=input_file,
                success=False,
                error=f"Step execution failed: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def run_calculation(
        self,
        steps: List[Tuple[Path, Optional[str]]],
        working_dir: Path,
        timeout: Optional[float] = None,
        environment: Optional[Dict[str, str]] = None,
        stop_on_error: bool = True
    ) -> CalculationResult:
        """
        Run a calculation of multiple QE calculation steps sequentially.
        
        Args:
            steps: List of (input_file, step_type) tuples. step_type can be None for auto-detection.
            working_dir: Working directory for execution
            timeout: Optional timeout per step (in seconds)
            environment: Optional environment variables dict
            stop_on_error: If True, stop calculation on first error
            
        Returns:
            CalculationResult with all step results
        """
        calculation_start = time.time()
        step_results = []
        
        for i, step_input in enumerate(steps):
            if isinstance(step_input, tuple):
                input_file, step_type = step_input
            else:
                input_file = step_input
                step_type = None
            
            # Run step
            result = self.run_step(
                input_file=input_file,
                working_dir=working_dir,
                step_type=step_type,
                timeout=timeout,
                environment=environment
            )
            
            step_results.append(result)
            
            # Check if step failed
            if not result.success:
                if stop_on_error:
                    return CalculationResult(
                        steps=step_results,
                        success=False,
                        total_time=time.time() - calculation_start,
                        error=f"Calculation stopped at step {i+1} ({result.step_type}): {result.error}"
                    )
                # Continue even on error if stop_on_error is False
        
        return CalculationResult(
            steps=step_results,
            success=all(r.success for r in step_results),
            total_time=time.time() - calculation_start,
            error=None if all(r.success for r in step_results) else "Some steps failed"
        )

