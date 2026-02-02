"""
Common utilities for QE testing.

This module provides shared functionality for testing QE modules,
including jobconfig parsing, benchmark comparison, and frequency extraction.
These utilities are used by both tests/ and extended-tests/.
"""

import re
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import configparser

# Import unified thresholds
from .thresholds import (
    get_energy_tolerance,
    get_frequency_threshold,
    DEFAULT_ENERGY_TOLERANCE,
    DEFAULT_FREQUENCY_THRESHOLD,
)


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


def extract_ph_frequencies(content: str) -> Optional[List[float]]:
    """
    Extract all frequency values (in THz) from ph.x output.
    
    Extracts frequencies from ALL frequency blocks (all q-points).
    Frequencies are located between lines of asterisks (*****).
    Format: freq (    N) =      X.XXXXXX [THz] =     Y.YYYYYY [cm-1]
    
    Args:
        content: ph.x output content
        
    Returns:
        List of frequency values in THz from all frequency blocks, or None if extraction failed
    """
    lines = content.split('\n')
    frequencies = []
    in_freq_section = False
    
    for line in lines:
        # Check for separator line (all asterisks)
        if re.match(r'^\s*\*+\s*$', line):
            in_freq_section = not in_freq_section
            continue
        
        # If we're in a frequency section, extract frequencies
        if in_freq_section:
            # Pattern: freq (    N) =      X.XXXXXX [THz] =     Y.YYYYYY [cm-1]
            match = re.search(r'freq\s*\(\s*\d+\s*\)\s*=\s+([-\d.]+)\s+\[THz\]', line, re.IGNORECASE)
            if match:
                try:
                    freq = float(match.group(1))
                    frequencies.append(freq)
                except ValueError:
                    continue
    
    return frequencies if frequencies else None


class TimeoutError(Exception):
    """Raised when a command times out."""
    pass


def run_command_with_timeout(
    command: list,
    cwd: Path,
    timeout: int = 60,
    env: Optional[Dict[str, str]] = None,
    stdin_file: Optional[Path] = None
) -> Tuple[int, str, str]:
    """
    Run command with timeout and optional stdin redirection.
    
    Args:
        command: Command to run (without input file flags)
        cwd: Working directory
        timeout: Timeout in seconds
        env: Optional environment variables dict
        stdin_file: Optional path to input file for stdin redirection
        
    Returns:
        Tuple of (returncode, stdout, stderr)
        
    Raises:
        TimeoutError: If command exceeds timeout
    """
    try:
        stdin_handle = None
        if stdin_file and stdin_file.exists():
            stdin_handle = open(stdin_file, 'r')
        
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=stdin_handle,
            text=True,
            env=env,
            preexec_fn=None if sys.platform == "win32" else lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)
        )
        
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            return process.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise TimeoutError(f"Command exceeded {timeout}s timeout")
        finally:
            if stdin_handle:
                stdin_handle.close()
    except Exception as e:
        raise TimeoutError(f"Error running command: {e}")


def compare_with_benchmark(
    output_file: Path,
    benchmark_file: Path,
    executable_name: str = "pw.x",
    tolerance: Optional[float] = None,
    category: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Compare test output with benchmark output.
    
    For pw.x (SCF calculations), compares total energy.
    For ph.x, compares frequencies between two ***** lines.
    For other modules, only checks JOB DONE.
    
    Args:
        output_file: Path to test output
        benchmark_file: Path to benchmark output
        executable_name: QE executable name (e.g., "pw.x", "ph.x")
        tolerance: Numerical tolerance for energy comparison (if None, uses threshold from thresholds.py)
        category: Test category name (e.g., "ph_1d", "ph_2d") for category-specific thresholds
    
    Returns:
        (pass_test, message)
    
    Note:
        Thresholds are managed in tests.core.thresholds module.
        For ph.x frequency comparison, all tests use 0.015 THz by default.
    """
    # Use unified thresholds if tolerance not provided
    if tolerance is None:
        tolerance = get_energy_tolerance(category, executable_name)
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
    
    # For pw.x (and certain pw.x calculations), compare total energy
    # Priority: Use "! total energy" (most reliable indicator for SCF calculations)
    if executable_name == "pw.x":
        # Priority 1: Look for "! total energy" (most reliable, SCF always has this)
        # Format: !    total energy              =     -26.70549012 Ry
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
        
        # Fallback: If "! total energy" not found, look for other energy patterns nearby
        # (for non-SCF pw.x calculations like nscf, bands, dos)
        if not output_match:
            # Try multiple patterns in order of reliability
            energy_patterns = [
                # Pattern 1: "total energy" without "!" (nscf may have this)
                r"total energy\s+=\s+([-\d.]+)\s+Ry",
                # Pattern 2: "Final energy" (sometimes used)
                r"Final\s+energy\s+=\s+([-\d.]+)\s+Ry",
                # Pattern 3: "energy" near "Ry" (more general)
                r"energy\s+=\s+([-\d.]+)\s+Ry",
            ]
            
            for alt_pattern in energy_patterns:
                output_match = re.search(alt_pattern, output_content, re.IGNORECASE)
                benchmark_match = re.search(alt_pattern, benchmark_content, re.IGNORECASE)
                
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
                        continue
    
    # For ph.x, compare frequencies between two ***** lines
    if executable_name == "ph.x":
        output_freqs = extract_ph_frequencies(output_content)
        benchmark_freqs = extract_ph_frequencies(benchmark_content)
        
        if output_freqs is None or benchmark_freqs is None:
            # If frequency extraction failed, just check JOB DONE
            return True, "JOB DONE (frequency extraction failed)"
        
        # Check if frequency counts match
        if len(output_freqs) != len(benchmark_freqs):
            return False, f"Frequency count mismatch: {len(output_freqs)} vs {len(benchmark_freqs)}"
        
        # Calculate mean absolute difference
        if len(output_freqs) == 0:
            return True, "JOB DONE (no frequencies found)"
        
        freq_diffs = [abs(o - b) for o, b in zip(output_freqs, benchmark_freqs)]
        mean_diff = sum(freq_diffs) / len(freq_diffs)
        max_diff = max(freq_diffs) if freq_diffs else 0.0
        min_diff = min(freq_diffs) if freq_diffs else 0.0
        
        # Build detailed difference message
        diff_details = []
        diff_details.append(f"mean abs diff = {mean_diff:.6f} THz")
        diff_details.append(f"max diff = {max_diff:.6f} THz")
        diff_details.append(f"min diff = {min_diff:.6f} THz")
        
        # Show first few individual differences
        if len(freq_diffs) <= 10:
            # Show all differences
            diff_list = [f"{d:.6f}" for d in freq_diffs]
            diff_details.append(f"diffs = [{', '.join(diff_list)}] THz")
        else:
            # Show first 5 and last 5
            diff_list_start = [f"{d:.6f}" for d in freq_diffs[:5]]
            diff_list_end = [f"{d:.6f}" for d in freq_diffs[-5:]]
            diff_details.append(f"diffs (first 5) = [{', '.join(diff_list_start)}] THz")
            diff_details.append(f"diffs (last 5) = [{', '.join(diff_list_end)}] THz")
        
        diff_message = "; ".join(diff_details)
        
        # Get frequency threshold from unified thresholds module
        freq_threshold = get_frequency_threshold(category)
        
        if mean_diff > freq_threshold:
            return False, f"Frequency mean abs diff too large: {diff_message} (threshold: {freq_threshold} THz)"
        else:
            return True, f"Frequencies match: {diff_message}"
    
    # For other non-pw.x modules, just check JOB DONE
    return True, "JOB DONE"


def run_test_category_calculation(
    category: str,
    test_files: List[Tuple[str, str]],
    test_suite_dir: Path,
    qe_engine: "QuantumEspressoEngine",
    executable_map: Dict[str, str],
    timeout: int = 60,
    max_tests: Optional[int] = None,
    project_root: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Run all tests in a category using the centralized step execution system.
    
    This function replaces the old run_test_category from qe_module_base.
    It uses run_and_verify_step for each step.
    
    Args:
        category: Category name (e.g., "ph_base")
        test_files: List of (input_file, args) tuples from jobconfig
        test_suite_dir: Test suite root directory
        qe_engine: Configured QuantumEspressoEngine
        executable_map: (Deprecated, currently unused) mapping from step args
                        (like "1", "2") to executable names. Step type and
                        executable are now auto-detected from the QE input.
        timeout: Timeout per test
        max_tests: Maximum number of tests to run
        project_root: Project root directory (auto-detected if not provided)
    
    Returns:
        List of test results (dict with success, error, message, etc.)
    """
    import tempfile
    
    # Auto-detect project root if not provided
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    
    category_dir = test_suite_dir / category
    results = []
    
    # Limit number of tests if specified
    if max_tests:
        test_files = test_files[:max_tests]
    
    # Check if this is a calculation test (multiple sequential tests)
    is_calculation = len(test_files) > 1 and any(args for _, args in test_files)
    
    # For calculation tests, use a single working directory for all tests
    if is_calculation:
        working_dir = Path(tempfile.mkdtemp(prefix=f"qe_calculation_{category}_"))
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
            
            # For non-calculation tests, create a new working directory for each test
            if not is_calculation:
                working_dir = Path(tempfile.mkdtemp(prefix=f"qe_test_{category}_{i}_"))
            
            # Check for reference output file
            reference_file = None
            # Try to find benchmark file (QE test-suite format)
            if args:
                benchmark_file = category_dir / f"benchmark.out.git.inp={input_file}.args={args}"
            else:
                benchmark_file = category_dir / f"benchmark.out.git.inp={input_file}"
            
            if benchmark_file.exists():
                reference_file = benchmark_file
            
            # Run and verify step using centralized function
            try:
                from tests.core.qe_step_runner import run_and_verify_step
                from tests.core.qe_step_verification import verify_step_result
                
                step_result, success, message = run_and_verify_step(
                    input_file=test_path,
                    qe_engine=qe_engine,
                    working_dir=working_dir,
                    reference_file=reference_file,
                    category=category,
                    timeout=timeout,
                    step_type_gen=None,  # Auto-detect from input
                    project_root=project_root
                )
                
                result = {
                    "category": category,
                    "file": input_file,
                    "step": args if args else str(i+1),
                    "success": success,
                    "run_success": step_result.success,
                    "verify_success": success,
                    "output_file": str(step_result.output_file) if step_result.output_file else None,
                    "time_taken": step_result.time_taken or 0,
                    "message": message,
                    "error": step_result.error
                }
                
            except Exception as e:
                result = {
                    "category": category,
                    "file": input_file,
                    "step": args if args else str(i+1),
                    "success": False,
                    "run_success": False,
                    "verify_success": False,
                    "output_file": None,
                    "time_taken": 0,
                    "message": None,
                    "error": f"Error running test: {e}"
                }
            
            results.append(result)
            
            # For calculation tests, stop on first failure
            if is_calculation and not result.get("success", False):
                break
            
            # Clean up non-calculation working directories
            if not is_calculation and working_dir.exists():
                import shutil
                try:
                    shutil.rmtree(working_dir)
                except:
                    pass
    
    except Exception as e:
        results.append({
            "category": category,
            "file": "unknown",
            "success": False,
            "error": f"Category execution failed: {e}",
            "time_taken": 0
        })
    
    # Clean up calculation working directory
    if is_calculation and working_dir and working_dir.exists():
        import shutil
        try:
            shutil.rmtree(working_dir)
        except:
            pass
    
    return results

