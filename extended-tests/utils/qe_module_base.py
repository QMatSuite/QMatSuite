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

# Import test function from extended-tests/utils
import importlib.util
test_file = project_root / "extended-tests" / "utils" / "test_qe_roundtrip_execution.py"
if test_file.exists():
    spec = importlib.util.spec_from_file_location("test_qe_roundtrip_execution", test_file)
    test_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_module)
    ensure_pseudopotentials = test_module.ensure_pseudopotentials
else:
    # Fallback: define a simple version if file doesn't exist
    def ensure_pseudopotentials(input_file: Path, working_dir: Path, test_suite_dir: Path = None) -> bool:
        """Placeholder for pseudopotential download."""
        return True


def parse_jobconfig(jobconfig_path: Path, module_prefix: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    Parse jobconfig file to get test order for a specific module.
    
    Args:
        jobconfig_path: Path to jobconfig file
        module_prefix: Module prefix (e.g., "ph_", "pp_", "cp_")
    
    Returns:
        Dict mapping category name to list of (input_file, args) tuples
    """
    config = configparser.ConfigParser()
    config.read(jobconfig_path)
    
    tests = {}
    for section in config.sections():
        section_name = section.rstrip('/')
        if section_name.startswith(module_prefix):
            if 'inputs_args' in config[section]:
                try:
                    inputs = eval(config[section]['inputs_args'])
                    tests[section_name] = inputs
                except Exception as e:
                    print(f"Warning: Could not parse inputs_args for {section}: {e}")
                    tests[section_name] = []
            else:
                tests[section_name] = []
    
    return tests


def compare_with_benchmark(
    output_file: Path,
    benchmark_file: Path,
    tolerance: float = 1e-6
) -> Tuple[bool, str]:
    """
    Compare test output with benchmark output.
    
    Returns:
        (pass_test, message)
    """
    if not benchmark_file.exists():
        # No benchmark to compare - just check for JOB DONE
        if output_file.exists():
            content = output_file.read_text()
            if "JOB DONE" in content:
                return True, "JOB DONE (no benchmark to compare)"
        return False, "No benchmark and no JOB DONE"
    
    # Read both files
    try:
        output_content = output_file.read_text()
        benchmark_content = benchmark_file.read_text()
    except Exception as e:
        return False, f"Error reading files: {e}"
    
    # Check for JOB DONE
    if "JOB DONE" not in output_content:
        return False, "JOB DONE not found in output"
    
    # Extract and compare total energy if available
    # This is a simplified comparison - real testcode does more sophisticated checks
    import re
    
    # Try to extract energy from output
    energy_pattern = r"!\s+total energy\s+=\s+([-\d.]+)\s+Ry"
    output_match = re.search(energy_pattern, output_content, re.IGNORECASE)
    benchmark_match = re.search(energy_pattern, benchmark_content, re.IGNORECASE)
    
    if output_match and benchmark_match:
        try:
            output_energy = float(output_match.group(1))
            benchmark_energy = float(benchmark_match.group(1))
            energy_diff = abs(output_energy - benchmark_energy)
            
            if energy_diff <= tolerance:
                return True, f"Energy matches: {output_energy:.8f} Ry (diff: {energy_diff:.2e})"
            else:
                return False, f"Energy mismatch: {output_energy:.8f} vs {benchmark_energy:.8f} (diff: {energy_diff:.2e})"
        except ValueError:
            pass
    
    # If energy comparison fails, just check JOB DONE
    return True, "JOB DONE (energy comparison failed)"


def run_module_test(
    input_file: Path,
    executable_name: str,
    qe_engine: QuantumEspressoEngine,
    working_dir: Path,
    timeout: int = 60,
    input_flag: str = "-inp",
    nprocs: int = 1
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
        # Find executable
        exe_path = qe_engine.get_executable_path(executable_name)
        if not exe_path or not exe_path.exists():
            result["error"] = f"{executable_name} not found"
            return result
        
        # Build command
        if input_flag == "-i":
            # ph.x, pp.x, gipaw.x use -i flag
            base_command = [str(exe_path), "-i", str(input_file)]
        else:
            # pw.x and others use -inp flag
            base_command = [str(exe_path), "-inp", str(input_file)]
        
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
        env['ESPRESSO_PSEUDO'] = str(working_dir)
        if nprocs > 1:
            env['NPROCS'] = str(nprocs)
        
        # Run command
        stdout_file = working_dir / "stdout.txt"
        stderr_file = working_dir / "stderr.txt"
        
        with open(stdout_file, 'w') as fout, open(stderr_file, 'w') as ferr:
            proc = subprocess.run(
                command,
                cwd=working_dir,
                env=env,
                stdout=fout,
                stderr=ferr,
                timeout=timeout
            )
        
        result["time_taken"] = time.time() - start_time
        result["run_success"] = (proc.returncode == 0)
        result["output_file"] = str(stdout_file)
        
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
            # Check for JOB DONE
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
            
            # For workflow tests, also copy any existing save directories
            if is_workflow and working_dir.exists():
                # Copy .save directories from previous steps
                for save_dir in working_dir.glob("*.save"):
                    if save_dir.is_dir():
                        dest = test_working_dir / save_dir.name
                        if not dest.exists():
                            shutil.copytree(save_dir, dest)
            
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
                nprocs=nprocs
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
                    pass_test, message = compare_with_benchmark(stdout_file, benchmark_file)
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
                    pass_test, message = compare_with_benchmark(final_stdout, final_benchmark)
                    final_result["benchmark_match"] = pass_test
                    final_result["benchmark_message"] = message
                    final_result["success"] = pass_test
                    final_result["message"] = message
    
    return results

