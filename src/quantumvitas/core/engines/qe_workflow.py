"""
Quantum ESPRESSO workflow execution.

This module provides step and workflow execution capabilities for QE calculations.
Steps are the basic execution units (scf, nscf, dos, bands, etc.), and workflows
combine multiple steps in sequence.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import os
import time

from .qe_input import QEInput, QEInputParser, QEModule

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
class WorkflowResult:
    """Result of executing a QE workflow (multiple steps)."""
    steps: List[StepResult] = field(default_factory=list)
    success: bool = False
    total_time: float = 0.0
    error: Optional[str] = None


class QEWorkflowRunner:
    """
    Runner for QE calculation steps and workflows.
    
    A step is a single QE calculation (e.g., SCF, NSCF, DOS, bands).
    A workflow is a sequence of steps that depend on each other.
    """
    
    def __init__(self, engine: "QuantumEspressoEngine"):
        """
        Initialize workflow runner.
        
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
        
        # Prepare stdin
        stdin_file = input_file
        
        # Determine output file
        input_stem = input_file.stem
        output_file = working_dir / f"{input_stem}.out"
        
        # Execute command with stdin redirection
        try:
            with open(stdin_file, 'r') as stdin_handle:
                process = subprocess.Popen(
                    command,
                    stdin=stdin_handle,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(working_dir),
                    env=env,
                    text=True
                )
                
                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    return StepResult(
                        step_type=step_type,
                        input_file=input_file,
                        success=False,
                        error=f"Step execution timed out after {timeout}s",
                        stdout=stdout,
                        stderr=stderr,
                        execution_time=time.time() - start_time
                    )
                
                return_code = process.returncode
                
                # Write output to file
                if stdout:
                    output_file.write_text(stdout)
                
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
    
    def run_workflow(
        self,
        steps: List[Tuple[Path, Optional[str]]],
        working_dir: Path,
        timeout: Optional[float] = None,
        environment: Optional[Dict[str, str]] = None,
        stop_on_error: bool = True
    ) -> WorkflowResult:
        """
        Run a workflow of multiple QE calculation steps sequentially.
        
        Args:
            steps: List of (input_file, step_type) tuples. step_type can be None for auto-detection.
            working_dir: Working directory for execution
            timeout: Optional timeout per step (in seconds)
            environment: Optional environment variables dict
            stop_on_error: If True, stop workflow on first error
            
        Returns:
            WorkflowResult with all step results
        """
        workflow_start = time.time()
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
                    return WorkflowResult(
                        steps=step_results,
                        success=False,
                        total_time=time.time() - workflow_start,
                        error=f"Workflow stopped at step {i+1} ({result.step_type}): {result.error}"
                    )
                # Continue even on error if stop_on_error is False
        
        return WorkflowResult(
            steps=step_results,
            success=all(r.success for r in step_results),
            total_time=time.time() - workflow_start,
            error=None if all(r.success for r in step_results) else "Some steps failed"
        )

