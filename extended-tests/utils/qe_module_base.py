#!/usr/bin/env python3
"""
Base test framework for QE modules.

This module provides common functionality for testing different QE modules
(pw, ph, pp, cp, etc.) in the official test suite style.
"""

import sys
import subprocess
import configparser
import tempfile
import shutil
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import os
import time

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe_input import QEInput

# Import shared test utilities from tests/core
from tests.core.qe_test_utils import (
    parse_jobconfig,
    extract_ph_frequencies,
    compare_with_benchmark
)

# Import test function from extended-tests/utils
import importlib.util
test_file = project_root / "extended-tests" / "utils" / "test_qe_roundtrip_execution.py"
if test_file.exists():
    spec = importlib.util.spec_from_file_location("test_qe_roundtrip_execution", test_file)
    test_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_module)
    ensure_pseudopotentials = test_module.ensure_pseudopotentials
    set_outdir_to_temp = test_module.set_outdir_to_temp
else:
    # Fallback: define set_outdir_to_temp locally
    def set_outdir_to_temp(qe_input: QEInput, project_root: Path) -> None:
        """Set outdir parameter in QE input to temp/outdir if it exists."""
        for namelist in qe_input.namelists:
            if "outdir" in namelist.parameters:
                temp_outdir = project_root / "temp" / "outdir"
                temp_outdir.mkdir(parents=True, exist_ok=True)
                namelist.parameters["outdir"] = str(temp_outdir.absolute())
    
    # Fallback: define a simple version if file doesn't exist
    def ensure_pseudopotentials(input_file: Path, working_dir: Path, test_suite_dir: Path = None) -> bool:
        """Placeholder for pseudopotential download."""
        return True


# Re-export for backward compatibility
__all__ = [
    "parse_jobconfig",
    "extract_ph_frequencies",
    "compare_with_benchmark",
    "ensure_pseudopotentials",
]


# Functions extract_ph_frequencies and compare_with_benchmark are now imported
# from tests.core.qe_test_utils above. Legacy implementations removed.


def run_module_test(
    input_file: Path,
    executable_name: str,
    qe_engine: QuantumEspressoEngine,
    working_dir: Path,
    timeout: int = 60,
    input_flag: str = "-inp",
    nprocs: int = 1,
    save_output_to_temp: bool = True,
    category: str = None,
    step: str = None
) -> Dict[str, Any]:
    """
    Run a single QE module test.
    
    Args:
        input_file: Input file path
        executable_name: QE executable name (e.g., "ph.x", "pp.x")
        qe_engine: Configured QE engine
        working_dir: Working directory for test
        timeout: Timeout in seconds
        input_flag: Input flag for executable ("-inp" or "-i")
    
    Returns:
        Dictionary with test results
    """
    result = {
        "input_file": str(input_file),
        "success": False,
        "error": None,
        "run_success": False,
        "verify_success": False,
        "output_file": None,
        "time_taken": None,
        "message": None
    }
    
    start_time = time.time()
    
    try:
        # Parse and write input file to temp for debugging
        try:
            from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator
            
            # Parse the input file
            qe_input = QEInputParser.parse_file(input_file)
            
            # Set outdir to temp/outdir if it exists
            set_outdir_to_temp(qe_input, project_root)
            
            # Generate parsed input file
            parsed_content = QEInputGenerator.generate(qe_input)
            
            # Save to temp folder
            if save_output_to_temp:
                temp_output_dir = project_root / "temp" / "test_outputs"
                if category:
                    temp_output_dir = temp_output_dir / category
                temp_output_dir.mkdir(parents=True, exist_ok=True)
                
                # Create parsed filename: {input_filename}_parsed.in
                input_filename = Path(input_file).name
                parsed_filename = input_filename.replace(".in", "_parsed.in")
                if not parsed_filename.endswith(".in"):
                    parsed_filename = f"{input_filename}_parsed.in"
                
                if step:
                    parsed_filename = f"{Path(input_filename).stem}_{step}_parsed.in"
                
                parsed_output_path = temp_output_dir / parsed_filename
                parsed_output_path.write_text(parsed_content)
                result["parsed_input_file"] = str(parsed_output_path)
        except Exception as e:
            # If parsing fails, log but don't fail the test
            result["parse_warning"] = f"Failed to parse input file: {e}"
        
        # Find executable
        exe_path = qe_engine.get_executable_path(executable_name)
        if not exe_path or not exe_path.exists():
            result["error"] = f"{executable_name} not found"
            return result
        
        # Build command (without input file flags, will use stdin redirection)
        base_command = [str(exe_path)]
        
        # Add MPI if NPROCS > 1
        if nprocs > 1:
            # Try to find mpirun or mpiexec
            mpirun = shutil.which("mpirun") or shutil.which("mpiexec")
            if mpirun:
                command = [mpirun, "-np", str(nprocs)] + base_command
            else:
                # Fallback: set OMP_NUM_THREADS and hope for the best
                command = base_command
                os.environ['OMP_NUM_THREADS'] = str(nprocs)
        else:
            command = base_command
        
        # Set up environment
        env = os.environ.copy()
        # ESPRESSO_PSEUDO points to temp/pseudo for unified pseudopotential storage
        project_root = Path(__file__).parent.parent.parent
        temp_pseudo_dir = project_root / "temp" / "pseudo"
        temp_pseudo_dir.mkdir(parents=True, exist_ok=True)
        env['ESPRESSO_PSEUDO'] = str(temp_pseudo_dir.absolute())
        # Set OMP_NUM_THREADS=1 to ensure single-threaded execution
        env['OMP_NUM_THREADS'] = '1'
        if nprocs > 1:
            env['NPROCS'] = str(nprocs)
        
        # Run command with stdin redirection (pw.x < input.in)
        stdout_file = working_dir / "stdout.txt"
        stderr_file = working_dir / "stderr.txt"
        
        with open(stdout_file, 'w') as fout, open(stderr_file, 'w') as ferr:
            stdin_handle = None
            if input_file.exists():
                stdin_handle = open(input_file, 'r')
            try:
                proc = subprocess.run(
                    command,
                    cwd=working_dir,
                    env=env,
                    stdin=stdin_handle,
                    stdout=fout,
                    stderr=ferr,
                    timeout=timeout
                )
            finally:
                if stdin_handle:
                    stdin_handle.close()
        
        result["time_taken"] = time.time() - start_time
        result["run_success"] = (proc.returncode == 0)
        result["output_file"] = str(stdout_file)
        
        # Save stdout to temp folder for debugging
        if save_output_to_temp and stdout_file.exists():
            temp_output_dir = project_root / "temp" / "test_outputs"
            if category:
                temp_output_dir = temp_output_dir / category
            temp_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create output filename: {executable}_{input_filename}_{step}.out
            input_filename = Path(input_file).stem
            if step:
                output_filename = f"{executable_name.replace('.x', '')}_{input_filename}_{step}.out"
            else:
                output_filename = f"{executable_name.replace('.x', '')}_{input_filename}.out"
            
            temp_output_file = temp_output_dir / output_filename
            shutil.copy2(stdout_file, temp_output_file)
            result["temp_output_file"] = str(temp_output_file)
        
        # Read output files
        stdout_content = stdout_file.read_text() if stdout_file.exists() else ""
        stderr_content = stderr_file.read_text() if stderr_file.exists() else ""
        
        if proc.returncode != 0:
            result["error"] = f"{executable_name} returned {proc.returncode}"
            if stderr_content:
                # Get more stderr content
                stderr_lines = stderr_content.split('\n')
                # Find error lines (usually after separator or contain keywords)
                error_lines = []
                in_error_section = False
                for line in stderr_lines:
                    if any(keyword in line.lower() for keyword in ['error', 'fatal', 'failed', 'abort', 'mpi_abort']):
                        in_error_section = True
                    if in_error_section or any(keyword in line.lower() for keyword in ['error', 'fatal', 'failed']):
                        error_lines.append(line.strip())
                        if len(error_lines) >= 10:  # Limit to 10 lines
                            break
                
                if error_lines:
                    result["error"] += f"\nstderr: {'; '.join(error_lines[:10])}"
                else:
                    result["error"] += f"\nstderr (first 500 chars): {stderr_content[:500]}"
            
            # Also check stdout for error messages
            if stdout_content:
                # Look for common error patterns
                error_lines = [line.strip() for line in stdout_content.split('\n') 
                              if any(keyword in line.lower() for keyword in ['error', 'fatal', 'failed', 'abort', 'mpi_abort'])]
                if error_lines:
                    result["error"] += f"\nstdout errors: {'; '.join(error_lines[:5])}"
        else:
            # For pw.x, prioritize checking for total energy (most reliable indicator)
            # Format: !    total energy              =     -26.70549012 Ry
            if executable_name == "pw.x":
                import re
                # Priority 1: Look for ! total energy (most reliable for SCF)
                energy_pattern = r"!\s+total energy\s+=\s+([-\d.]+)\s+Ry"
                energy_match = re.search(energy_pattern, stdout_content, re.IGNORECASE)
                
                if energy_match:
                    try:
                        energy = float(energy_match.group(1))
                        result["verify_success"] = True
                        result["success"] = True
                        result["message"] = f"Total energy: {energy:.8f} Ry"
                    except ValueError:
                        # If energy extraction fails, fall back to JOB DONE check
                        if "JOB DONE" in stdout_content:
                            result["verify_success"] = True
                            result["success"] = True
                            result["message"] = "JOB DONE (energy extraction failed)"
                        else:
                            result["error"] = "Total energy found but extraction failed and no JOB DONE"
                else:
                    # Fallback: If "! total energy" not found, look for other energy patterns
                    # (for non-SCF pw.x calculations like nscf, bands, dos)
                    energy_patterns = [
                        # Pattern 1: "total energy" without "!" (nscf may have this)
                        r"total energy\s+=\s+([-\d.]+)\s+Ry",
                        # Pattern 2: "Final energy" (sometimes used)
                        r"Final\s+energy\s+=\s+([-\d.]+)\s+Ry",
                        # Pattern 3: "energy" near "Ry" (more general)
                        r"energy\s+=\s+([-\d.]+)\s+Ry",
                    ]
                    
                    energy_match = None
                    for alt_pattern in energy_patterns:
                        energy_match = re.search(alt_pattern, stdout_content, re.IGNORECASE)
                        if energy_match:
                            try:
                                energy = float(energy_match.group(1))
                                result["verify_success"] = True
                                result["success"] = True
                                result["message"] = f"Energy: {energy:.8f} Ry"
                                break
                            except ValueError:
                                continue
                    
                    if not energy_match:
                        # No energy found - fall back to JOB DONE
                        if "JOB DONE" in stdout_content:
                            result["verify_success"] = True
                            result["success"] = True
                            result["message"] = "JOB DONE (no energy found)"
                        else:
                            # No energy and no JOB DONE - check for errors
                            error_lines = [line for line in stdout_content.split('\n') 
                                          if any(keyword in line.lower() for keyword in ['error', 'fatal', 'failed'])]
                            if error_lines:
                                result["error"] = f"JOB DONE not found and errors in output: {'; '.join(error_lines[:3])}"
                            else:
                                result["error"] = "JOB DONE not found in output (no errors detected)"
            else:
                # For non-pw.x modules, check for JOB DONE
                if "JOB DONE" in stdout_content:
                    result["verify_success"] = True
                    result["success"] = True
                    result["message"] = "JOB DONE"
                else:
                    # Even if return code is 0, check for errors in output
                    error_lines = [line for line in stdout_content.split('\n') 
                                  if any(keyword in line.lower() for keyword in ['error', 'fatal', 'failed'])]
                    if error_lines:
                        result["error"] = f"JOB DONE not found and errors in output: {'; '.join(error_lines[:3])}"
                    else:
                        result["error"] = "JOB DONE not found in output (no errors detected)"
        
    except subprocess.TimeoutExpired:
        result["time_taken"] = time.time() - start_time
        result["error"] = f"Test timed out after {timeout}s"
    except Exception as e:
        result["time_taken"] = time.time() - start_time
        result["error"] = f"Error running test: {e}"
    
    return result


def run_test_category(
    category: str,
    test_files: List[Tuple[str, str]],
    test_suite_dir: Path,
    qe_engine: QuantumEspressoEngine,
    executable_map: Dict[str, str],  # Maps step args to executable names
    timeout: int = 60,
    max_tests: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Run all tests in a category.
    
    For workflow tests (multiple sequential tests), all tests run in the same
    working directory to preserve intermediate files.
    
    Args:
        category: Category name (e.g., "ph_base")
        test_files: List of (input_file, args) tuples
        test_suite_dir: Test suite root directory
        qe_engine: Configured QE engine
        executable_map: Maps step args (like "1", "2") to executable names
        timeout: Timeout per test
        max_tests: Maximum number of tests to run
        
    Returns:
        List of test results
    """
    category_dir = test_suite_dir / category
    results = []
    
    # Limit number of tests if specified
    if max_tests:
        test_files = test_files[:max_tests]
    
    # Check if this is a workflow test (multiple sequential tests)
    is_workflow = len(test_files) > 1 and any(args for _, args in test_files)
    
    # For workflow tests, use a single working directory for all tests
    if is_workflow:
        working_dir = Path(tempfile.mkdtemp(prefix=f"qe_workflow_{category}_"))
        # Ensure pseudopotentials are available (check first test)
        if test_files:
            first_test_path = category_dir / test_files[0][0]
            if first_test_path.exists():
                ensure_pseudopotentials(first_test_path, working_dir, test_suite_dir)
    else:
        working_dir = None
    
    try:
        for i, (input_file, args) in enumerate(test_files):
            test_path = category_dir / input_file
            
            if not test_path.exists():
                results.append({
                    "category": category,
                    "file": input_file,
                    "success": False,
                    "error": "Test file not found",
                    "time_taken": 0
                })
                continue
            
            # Determine executable and input flag based on args
            executable_name = executable_map.get(args, executable_map.get("default", "pw.x"))
            
            # Determine input flag based on executable
            if executable_name in ["ph.x", "pp.x", "gipaw.x"]:
                input_flag = "-i"
            else:
                input_flag = "-inp"
            
            # For workflow tests, reuse the same working directory
            if is_workflow:
                if working_dir is None:
                    working_dir = Path(tempfile.mkdtemp(prefix=f"qe_workflow_{category}_"))
                test_working_dir = working_dir
            else:
                test_working_dir = Path(tempfile.mkdtemp(prefix=f"qe_test_{category}_{i}_"))
                # Ensure pseudopotentials
                ensure_pseudopotentials(test_path, test_working_dir, test_suite_dir)
            
            # Copy input file to working directory
            # input_file is a string, so we need to get the filename
            input_filename = Path(input_file).name
            working_input = test_working_dir / input_filename
            import shutil
            shutil.copy2(test_path, working_input)
            
            # Update pseudo_dir in input file to point to temp/pseudo
            # This ensures QE can find the pseudopotentials from unified location
            # We'll modify the file directly to preserve original formatting
            try:
                content = working_input.read_text()
                # Replace pseudo_dir with temp/pseudo absolute path
                # Match patterns like: pseudo_dir = '../../pseudo' or pseudo_dir='../../pseudo'
                import re
                project_root = Path(__file__).parent.parent.parent
                temp_pseudo_dir = project_root / "temp" / "pseudo"
                temp_pseudo_dir.mkdir(parents=True, exist_ok=True)
                pseudo_dir_abs = str(temp_pseudo_dir.absolute())
                
                # Pattern to match pseudo_dir assignments
                pattern = r'pseudo_dir\s*=\s*[^\s,/\n]+'
                replacement = f"pseudo_dir = '{pseudo_dir_abs}'"
                new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                
                if new_content != content:
                    working_input.write_text(new_content)
                else:
                    # If pseudo_dir doesn't exist, add it to control namelist
                    # Check if control namelist exists
                    if "&control" in content.lower() or "&CONTROL" in content:
                        # Add pseudo_dir to existing control namelist
                        control_pattern = r'(&control[^\n]*\n(?:[^&]*\n)*?)(/)'
                        replacement_with_pseudo = f"\\1    pseudo_dir = '{pseudo_dir_abs}'\n\\2"
                        new_content = re.sub(control_pattern, replacement_with_pseudo, content, flags=re.IGNORECASE | re.MULTILINE)
                        if new_content != content:
                            working_input.write_text(new_content)
            except Exception as e:
                # If modification fails, continue with original file
                # Pseudopotentials should still be found via ESPRESSO_PSEUDO env var
                pass
            
            # For workflow tests, we're already using the same working_dir,
            # so .save directories from previous steps (e.g., pw.x) are already there.
            # No need to copy - they're in the same directory!
            
            # Get NPROCS from environment or default to 1
            nprocs = int(os.environ.get("NPROCS", "1"))
            
            # Run test
            result = run_module_test(
                working_input,
                executable_name,
                qe_engine,
                test_working_dir,
                timeout,
                input_flag,
                nprocs=nprocs,
                save_output_to_temp=True,
                category=category,
                step=args if args else str(i+1)
            )
            
            result["category"] = category
            result["file"] = input_file
            result["step"] = args if args else str(i+1)
            
            # Compare with benchmark if available
            if args:
                benchmark_file = category_dir / f"benchmark.out.git.inp={input_file}.args={args}"
            else:
                benchmark_file = category_dir / f"benchmark.out.git.inp={input_file}"
            
            if result["run_success"]:
                stdout_file = test_working_dir / "stdout.txt"
                if stdout_file.exists():
                    pass_test, message = compare_with_benchmark(
                        stdout_file, 
                        benchmark_file,
                        executable_name=executable_name,
                        category=category
                    )
                    result["benchmark_match"] = pass_test
                    result["benchmark_message"] = message
                    if result["verify_success"]:
                        result["success"] = pass_test
                        result["message"] = message
            
            results.append(result)
            
            # Clean up non-workflow working directories
            if not is_workflow and test_working_dir.exists():
                import shutil
                shutil.rmtree(test_working_dir)
    
    except Exception as e:
        results.append({
            "category": category,
            "file": "unknown",
            "success": False,
            "error": f"Category execution failed: {e}",
            "time_taken": 0
        })
    
    # For workflow tests, the final result is the last step
    if is_workflow and len(results) > 0:
        all_steps_success = all(r.get("run_success", False) for r in results)
        final_result = results[-1]
        if all_steps_success and final_result.get("verify_success", False):
            final_input = test_files[-1][0]
            final_args = test_files[-1][1]
            if final_args:
                final_benchmark = category_dir / f"benchmark.out.git.inp={final_input}.args={final_args}"
            else:
                final_benchmark = category_dir / f"benchmark.out.git.inp={final_input}"
            
            if working_dir:
                final_stdout = working_dir / "stdout.txt"
                if final_stdout.exists():
                    final_executable = executable_map.get(final_args, executable_map.get("default", "pw.x"))
                    pass_test, message = compare_with_benchmark(
                        final_stdout, 
                        final_benchmark,
                        executable_name=final_executable,
                        category=category
                    )
                    final_result["benchmark_match"] = pass_test
                    final_result["benchmark_message"] = message
                    final_result["success"] = pass_test
                    final_result["message"] = message
    
    return results

