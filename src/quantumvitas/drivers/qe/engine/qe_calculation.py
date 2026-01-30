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

# Import normalize_step_type_to_public from registry (SSOT for machine→public conversion)
from quantumvitas.workflow.registry import normalize_step_type_to_public as _normalize_step_type_to_public


@dataclass
class StepResult:
    """Result of executing a single QE calculation step."""
    step_type_spec: str  # SPEC type (e.g., "qe_scf", "vasp_relax")
    input_file: Path
    output_file: Optional[Path] = None  # Primary artifact (e.g., <seed>.wout for Wannier90, scf.out for QE)
    stdout_file: Optional[Path] = None  # Stdout capture file (e.g., scf.out, w90_preproc.out)
    stderr_file: Optional[Path] = None  # Stderr capture file (e.g., scf.err, w90_preproc.err)
    success: bool = False
    return_code: Optional[int] = None
    stdout: str = ""  # Content from stdout_file (for in-memory access)
    stderr: str = ""  # Content from stderr_file (for in-memory access)
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


def get_capture_paths(raw_dir: Path, step_type: str) -> Tuple[Path, Path]:
    """
    Get stdout and stderr capture file paths for a step.
    
    This function centralizes the naming convention for capture files:
    - stdout: {step_type}.out
    - stderr: {step_type}.err
    
    These files are always overwritten (mode="w") and never versioned,
    regardless of input file versioning (e.g., scf.in vs scf-1.in).
    
    Args:
        raw_dir: Working directory where capture files are written
        step_type: Step type (e.g., "scf", "nscf", "w90_preproc")
        
    Returns:
        Tuple of (stdout_path, stderr_path)
    """
    stdout_path = raw_dir / f"{step_type}.out"
    stderr_path = raw_dir / f"{step_type}.err"
    return stdout_path, stderr_path


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
        import logging
        logger = logging.getLogger(__name__)
        
        start_time = time.time()
        
        def _ensure_file_path(path: Optional[Path], default_name: str, workdir: Path) -> Path:
            """
            Ensure a path points to a valid file (not a directory).
            
            Args:
                path: Path to check (can be None, absolute, or relative)
                default_name: Default filename to use if path is invalid
                workdir: Working directory for relative paths
            
            Returns:
                Valid file path in workdir
            """
            if path is None:
                return workdir / default_name
            
            path_resolved = Path(path)
            if not path_resolved.is_absolute():
                path_resolved = (workdir / path_resolved).resolve()
            else:
                path_resolved = path_resolved.resolve()
            
            # Check if path is a directory or invalid
            if path_resolved.exists() and path_resolved.is_dir():
                logger.warning(
                    f"[RUN_STEP] Path is a directory, using default: {path_resolved} -> {workdir / default_name}"
                )
                return workdir / default_name
            
            # Check for invalid names like '.', './', etc.
            if str(path_resolved.name) in ('', '.', '..'):
                logger.warning(
                    f"[RUN_STEP] Path has invalid name '{path_resolved.name}', using default: {workdir / default_name}"
                )
                return workdir / default_name
            
            # If it's a relative path, ensure it's relative to workdir
            if not path_resolved.is_absolute() or not str(path_resolved).startswith(str(workdir.resolve())):
                return workdir / default_name
            
            return path_resolved
        
        # Log entry point
        logger.info(f"[RUN_STEP] Starting step execution: step_type={step_type}, input_file={input_file}, working_dir={working_dir}")
        logger.debug(f"[RUN_STEP] input_file type: {type(input_file)}, is_absolute: {input_file.is_absolute() if isinstance(input_file, Path) else 'N/A'}")
        logger.debug(f"[RUN_STEP] input_file exists: {input_file.exists() if isinstance(input_file, Path) else 'N/A'}")
        logger.debug(f"[RUN_STEP] input_file is_dir: {input_file.is_dir() if isinstance(input_file, Path) else 'N/A'}")
        
        # Detect step type if not provided
        if step_type is None:
            step_type = self.detect_step_type(input_file)
            logger.info(f"[RUN_STEP] Auto-detected step_type: {step_type}")
        
        # Convert machine_type (e.g., 'qe_bands') to public_type (e.g., 'bands') for lookup
        step_type_public = _normalize_step_type_to_public(step_type)
        logger.debug(f"[RUN_STEP] step_type_public: {step_type_public} (from {step_type})")
        
        # Get executable for this step type (using public_type)
        executable = self.engine.EXECUTABLE_MAP.get(step_type_public, "pw.x")
        logger.debug(f"[RUN_STEP] Executable: {executable}")
        
        # Resolve input_file to absolute path for logging and validation
        input_file_abs = Path(input_file).resolve() if isinstance(input_file, Path) else Path(input_file)
        logger.debug(f"[RUN_STEP] Resolved input_file_abs: {input_file_abs}")
        logger.debug(f"[RUN_STEP] input_file_abs exists: {input_file_abs.exists()}")
        logger.debug(f"[RUN_STEP] input_file_abs is_dir: {input_file_abs.is_dir()}")
        logger.debug(f"[RUN_STEP] input_file_abs is_file: {input_file_abs.is_file()}")
        
        # Build command (this may modify input_file path for relative resolution)
        command = self.engine.build_command(step_type, input_file, working_dir)
        logger.info(f"[RUN_STEP] Built command: {' '.join(command)}")
        
        # Prepare environment
        env = os.environ.copy()
        if environment:
            env.update(environment)
        
        # Set OMP_NUM_THREADS if not already set
        if 'OMP_NUM_THREADS' not in env:
            omp_threads = self.engine.config.omp_threads if self.engine.config.omp_threads is not None else 1
            env['OMP_NUM_THREADS'] = str(omp_threads)
        
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
        
        # A. Unified stdout/stderr file naming: step_type.out / step_type.err (overwrite, never versioned)
        stdout_capture_path, stderr_capture_path = get_capture_paths(working_dir, step_type)
        
        # B. Determine primary output file (artifact) semantics
        input_stem = input_file.stem if isinstance(input_file, Path) else Path(input_file).stem
        
        if step_type in ("w90_preproc", "w90_run"):
            # Wannier90 steps:
            # - Primary artifact: <seed>.wout (for GUI display of main output)
            # - Stdout capture: w90_preproc.out / w90_run.out (may be empty, but always written)
            primary_output_file = working_dir / f"{input_stem}.wout"
        elif step_type == "pw2wannier90":
            # pw2wannier90: primary output is the stdout capture
            primary_output_file = stdout_capture_path
        else:
            # QE steps (scf, nscf, etc.): primary output is the stdout capture
            # This matches QE convention where scf.out is both the stdout and the main output
            primary_output_file = stdout_capture_path
        
        # Check if step uses stdin or command-line arguments
        uses_stdin = self.engine.uses_stdin(step_type)
        
        # E. Logging: Only essential info at INFO level
        logger.info(f"[RUN_STEP] Starting {step_type}: {input_file.name if hasattr(input_file, 'name') else input_file}")
        logger.info(f"[RUN_STEP] Capturing stdout/stderr to {step_type}.out/.err (overwrite)")
        
        # Execute command
        try:
            if uses_stdin:
                # Standard QE execution with stdin redirection (pw.x, ph.x, etc.)
                
                # Resolve stdin_file path
                stdin_file = Path(input_file)
                if not stdin_file.is_absolute():
                    stdin_file = (working_dir / stdin_file).resolve()
                else:
                    stdin_file = stdin_file.resolve()
                
                # E. Detailed validation logs moved to DEBUG
                logger.debug(f"[RUN_STEP] stdin_file resolved: {stdin_file}")
                logger.debug(f"[RUN_STEP] stdin_file exists: {stdin_file.exists()}, is_dir: {stdin_file.is_dir()}, is_file: {stdin_file.is_file()}")
                
                # Safety check: ensure input_file is a file, not a directory
                if stdin_file.exists() and stdin_file.is_dir():
                    logger.error(f"[RUN_STEP] Input file is a directory: {stdin_file}")
                    raise ValueError(
                        f"Input file path is a directory: {stdin_file}. "
                        f"Step input_file must point to a file (e.g., 'scf.in', 'diamond.win')."
                    )
                if not stdin_file.exists():
                    logger.error(f"[RUN_STEP] Input file not found: {stdin_file}")
                    raise FileNotFoundError(
                        f"Input file not found: {stdin_file}. "
                        f"Step materialization may have failed to generate the input file."
                    )
                
                # Ensure parent directories exist and open files with mode="w" to overwrite
                stdout_capture_path.parent.mkdir(parents=True, exist_ok=True)
                stderr_capture_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(stdin_file, 'r') as stdin_handle:
                    with open(stdout_capture_path, 'w') as output_handle:
                        with open(stderr_capture_path, 'w') as stderr_handle:
                            process = subprocess.Popen(
                                command,
                                stdin=stdin_handle,
                                stdout=output_handle,
                                stderr=stderr_handle,
                                cwd=str(working_dir),
                                env=env,
                                text=True
                            )
                            
                            logger.debug(f"[RUN_STEP] Started process PID: {process.pid}")
                            
                            try:
                                process.wait(timeout=timeout)
                                output_handle.flush()
                                stderr_handle.flush()
                            except subprocess.TimeoutExpired:
                                logger.error(f"[RUN_STEP] {step_type} timed out after {timeout}s (see {stderr_capture_path.name})")
                                process.kill()
                                output_handle.flush()
                                stderr_handle.flush()
                                # Read stderr from file
                                stderr = stderr_capture_path.read_text() if stderr_capture_path.exists() else ""
                                return StepResult(
                                    step_type=step_type,
                                    input_file=input_file,
                                    success=False,
                                    error=f"Step execution timed out after {timeout}s",
                                    stdout="",
                                    stderr=stderr,
                                    execution_time=time.time() - start_time,
                                    return_code=-1,
                                    output_file=primary_output_file if primary_output_file.exists() else None,
                                    stdout_file=stdout_capture_path,
                                    stderr_file=stderr_capture_path,
                                )
            else:
                # Wannier90 execution without stdin (uses command-line arguments: seedname or -i flag)
                # w90_preproc: wannier90.x -pp seedname
                # w90_run: wannier90.x seedname
                # pw2wannier90: pw2wannier90.x -i pw2wan.in
                logger.debug(f"[RUN_STEP] Using command-line arguments for {step_type} (no stdin)")
                logger.debug(f"[RUN_STEP] Command: {' '.join(command)}")
                logger.debug(f"[RUN_STEP] Working dir: {working_dir}")
                
                # For pw2wannier90, verify input file exists BEFORE running
                if step_type == "pw2wannier90":
                    # Command is: pw2wannier90.x -i <input_file>
                    # Input file should be relative to working_dir or absolute
                    # Find the input file path from command
                    if "-i" in command:
                        input_idx = command.index("-i")
                        if input_idx + 1 < len(command):
                            cmd_input_file_str = command[input_idx + 1]
                            # Resolve relative to working_dir
                            cmd_input_file_path = Path(cmd_input_file_str)
                            if not cmd_input_file_path.is_absolute():
                                cmd_input_file_resolved = (working_dir / cmd_input_file_path).resolve()
                            else:
                                cmd_input_file_resolved = cmd_input_file_path.resolve()
                            
                            # E. Validation details at DEBUG level
                            logger.debug(f"[RUN_STEP] pw2wannier90 input validation: arg='{cmd_input_file_str}', resolved={cmd_input_file_resolved}, exists={cmd_input_file_resolved.exists()}, is_dir={cmd_input_file_resolved.is_dir()}")
                            
                            # Safety checks
                            if cmd_input_file_str in (".", "./", ".."):
                                logger.error(f"[RUN_STEP] pw2wannier90 input file is invalid: '{cmd_input_file_str}' (see {stderr_capture_path.name})")
                                raise ValueError(
                                    f"pw2wannier90 input file path is invalid: '{cmd_input_file_str}'. "
                                    f"Command was: {' '.join(command)}"
                                )
                            
                            if cmd_input_file_resolved.exists() and cmd_input_file_resolved.is_dir():
                                logger.error(f"[RUN_STEP] pw2wannier90 input file is a directory: {cmd_input_file_resolved} (see {stderr_capture_path.name})")
                                raise ValueError(
                                    f"pw2wannier90 input file path is a directory: {cmd_input_file_resolved}."
                                )
                            
                            if not cmd_input_file_resolved.exists():
                                logger.error(f"[RUN_STEP] pw2wannier90 input file not found: {cmd_input_file_resolved} (see {stderr_capture_path.name})")
                                if working_dir.exists():
                                    files_in_workdir = [f.name for f in working_dir.glob("*")]
                                    logger.debug(f"[RUN_STEP] Files in working_dir: {files_in_workdir}")
                                raise FileNotFoundError(
                                    f"pw2wannier90 input file not found: {cmd_input_file_resolved}."
                                )
                        else:
                            logger.error(f"[RUN_STEP] ERROR: pw2wannier90 command missing input file after -i flag: {' '.join(command)}")
                            raise ValueError(f"pw2wannier90 command missing input file: {' '.join(command)}")
                    else:
                        logger.error(f"[RUN_STEP] ERROR: pw2wannier90 command missing -i flag: {' '.join(command)}")
                        raise ValueError(f"pw2wannier90 command must include -i flag: {' '.join(command)}")
                
                # C. cwd must be raw_dir (working_dir) - wannier90 writes <seed>.nnkp/.wout there
                # Ensure parent directories exist and open files with mode="w" to overwrite
                stdout_capture_path.parent.mkdir(parents=True, exist_ok=True)
                stderr_capture_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(stdout_capture_path, 'w') as output_handle:
                    with open(stderr_capture_path, 'w') as stderr_handle:
                        process = subprocess.Popen(
                            command,
                            stdin=subprocess.DEVNULL,
                            stdout=output_handle,
                            stderr=stderr_handle,
                            cwd=str(working_dir),  # C. cwd must be raw_dir
                            env=env,
                            text=True
                        )
                        logger.debug(f"[RUN_STEP] Started process PID: {process.pid}")
                        
                        try:
                            process.wait(timeout=timeout)
                            output_handle.flush()
                            stderr_handle.flush()
                        except subprocess.TimeoutExpired:
                            logger.error(f"[RUN_STEP] {step_type} timed out after {timeout}s (see {stderr_capture_path.name})")
                            process.kill()
                            output_handle.flush()
                            stderr_handle.flush()
                            # Read stderr from file
                            stderr = stderr_capture_path.read_text() if stderr_capture_path.exists() else ""
                            return StepResult(
                                step_type=step_type,
                                input_file=input_file,
                                success=False,
                                error=f"Step execution timed out after {timeout}s",
                                stdout="",
                                stderr=stderr,
                                execution_time=time.time() - start_time,
                                return_code=-1,
                                output_file=primary_output_file if primary_output_file.exists() else None,
                                stdout_file=stdout_capture_path,
                                stderr_file=stderr_capture_path,
                            )
            
            # Common result handling for both stdin and non-stdin cases
            return_code = process.returncode
            
            # Read stdout and stderr from capture files for StepResult
            stdout = stdout_capture_path.read_text() if stdout_capture_path.exists() else ""
            stderr = stderr_capture_path.read_text() if stderr_capture_path.exists() else ""
            
            # E. Logging: Essential info only at INFO level
            if return_code == 0:
                logger.info(f"[RUN_STEP] {step_type} finished (returncode=0): output={primary_output_file.name if primary_output_file else 'N/A'}, stdout={stdout_capture_path.name}, stderr={stderr_capture_path.name}")
            else:
                # E. Failure logging: concise error with reference to stderr file
                stderr_preview = ""
                if stderr:
                    stderr_lines = stderr.split('\n')
                    stderr_preview = '\n'.join(stderr_lines[-50:]) if len(stderr_lines) > 50 else stderr
                logger.error(f"[RUN_STEP] {step_type} failed (returncode={return_code}): see {stderr_capture_path.name}")
                logger.debug(f"[RUN_STEP] Stderr preview:\n{stderr_preview}")
            
            logger.debug(f"[RUN_STEP] Read stdout: {len(stdout)} chars, stderr: {len(stderr)} chars")
            
            # Ensure stdout capture ends with a newline
            if stdout and not stdout.endswith('\n'):
                with open(stdout_capture_path, 'a') as f:
                    f.write('\n')
                stdout = stdout + '\n'
            
            # D. Post-run verification: check return code and required artifacts
            success = (return_code == 0)
            error_msg = None
            
            if step_type == "w90_preproc":
                # w90_preproc: returncode==0 AND <seed>.nnkp must exist
                input_stem = input_file.stem if isinstance(input_file, Path) else Path(input_file).stem
                nnkp_file = working_dir / f"{input_stem}.nnkp"
                if return_code == 0:
                    if not nnkp_file.exists():
                        success = False
                        error_msg = f"w90_preproc return_code=0 but required artifact {nnkp_file.name} does not exist"
                        logger.error(f"[RUN_STEP] {error_msg}")
                    else:
                        logger.info(f"[RUN_STEP] w90_preproc succeeded: {nnkp_file} exists")
                else:
                    success = False
                    error_msg = f"w90_preproc failed with return code {return_code}"
                    if stderr:
                        stderr_preview = stderr[-500:] if len(stderr) > 500 else stderr
                        error_msg += f"\n\nStderr:\n{stderr_preview}"
            
            elif step_type == "w90_run":
                # w90_run: returncode==0 AND <seed>.wout must exist
                input_stem = input_file.stem if isinstance(input_file, Path) else Path(input_file).stem
                wout_file = working_dir / f"{input_stem}.wout"
                if return_code == 0:
                    if not wout_file.exists():
                        success = False
                        error_msg = f"w90_run return_code=0 but required artifact {wout_file.name} does not exist"
                        logger.error(f"[RUN_STEP] {error_msg}")
                    else:
                        logger.debug(f"[RUN_STEP] w90_run succeeded: {wout_file.name} exists")
                else:
                    success = False
                    error_msg = f"w90_run failed with return code {return_code}"
                    if stderr:
                        stderr_preview = stderr[-500:] if len(stderr) > 500 else stderr
                        error_msg += f"\n\nStderr:\n{stderr_preview}"
            
            elif step_type == "pw2wannier90":
                # pw2wannier90: returncode==0 means success
                if return_code != 0:
                    success = False
                    error_msg = f"pw2wannier90 failed with return code {return_code}"
                    if stderr:
                        # Include last 50 lines of stderr
                        stderr_lines = stderr.split('\n')
                        stderr_preview = '\n'.join(stderr_lines[-50:]) if len(stderr_lines) > 50 else stderr
                        error_msg += f"\n\nStderr (last 50 lines):\n{stderr_preview}"
                    logger.error(f"[RUN_STEP] {error_msg}")
                else:
                    logger.info(f"[RUN_STEP] pw2wannier90 succeeded (return_code=0)")
            
            else:
                # QE steps: use return_code and optional parsing
                if return_code != 0:
                    success = False
                    error_msg = f"Step failed with return code {return_code}"
                    if stderr:
                        stderr_preview = stderr[-500:] if len(stderr) > 500 else stderr
                        error_msg += f"\n\nStderr:\n{stderr_preview}"
            
            # Parse output if successful (only for QE steps that support it)
            parsed_output = None
            if success and step_type not in ("w90_preproc", "w90_run", "pw2wannier90"):
                # Only parse QE output files, not Wannier90
                if primary_output_file.exists():
                    try:
                        parsed_output = self.engine.parse_output(primary_output_file, step_type)
                    except Exception:
                        pass  # Parsing is optional
            
            # B. Set StepResult fields:
            # - output_file: Primary artifact (<seed>.wout for Wannier90, scf.out for QE)
            # - stdout_file: Stdout capture file (always step_type.out)
            # - stderr_file: Stderr capture file (always step_type.err)
            # Note: output_file should always be set to the expected path, even if file doesn't exist (e.g., execution failed)
            result_output_file = None
            if step_type in ("w90_preproc", "w90_run"):
                # Wannier90: primary artifact is <seed>.wout (only if exists, otherwise None)
                if primary_output_file.exists():
                    result_output_file = primary_output_file
            elif step_type == "pw2wannier90":
                # pw2wannier90: primary output is the stdout capture (always set, even if empty)
                result_output_file = stdout_capture_path
            else:
                # QE steps: primary output is the stdout capture (scf.out, nscf.out, etc.)
                # Always set to stdout_capture_path, even if execution failed and file doesn't exist
                result_output_file = stdout_capture_path
            
            logger.debug(f"[RUN_STEP] StepResult: output_file={result_output_file.name if result_output_file else None}, "
                        f"stdout_file={stdout_capture_path.name}, stderr_file={stderr_capture_path.name}, "
                        f"success={success}, return_code={return_code}")
            
            return StepResult(
                step_type=step_type,
                input_file=input_file,
                output_file=result_output_file,  # Primary artifact
                stdout_file=stdout_capture_path,  # Always step_type.out
                stderr_file=stderr_capture_path,  # Always step_type.err
                success=success,
                return_code=return_code,
                stdout=stdout,  # Content from stdout_file
                stderr=stderr,  # Content from stderr_file
                error=error_msg,
                execution_time=time.time() - start_time,
                parsed_output=parsed_output
            )
        
        except Exception as e:
            return StepResult(
                step_type=step_type,
                input_file=input_file,
                success=False,
                error=f"Step execution failed: {str(e)}",
                execution_time=time.time() - start_time,
                stdout_file=stdout_capture_path,
                stderr_file=stderr_capture_path,
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
                        error=f"Calculation stopped at step {i+1} ({result.step_type_spec}): {result.error}"
                    )
                # Continue even on error if stop_on_error is False
        
        return CalculationResult(
            steps=step_results,
            success=all(r.success for r in step_results),
            total_time=time.time() - calculation_start,
            error=None if all(r.success for r in step_results) else "Some steps failed"
        )

