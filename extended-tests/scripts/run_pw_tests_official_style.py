#!/usr/bin/env python3
"""
Run pw tests in the same style as the official QE test suite.

This script:
1. Reads jobconfig to get test order and files
2. Runs each test file in the specified order
3. Compares output with benchmark files to determine pass/fail
4. Reports results in a format similar to testcode.py
"""

import sys
import subprocess
import configparser
import tempfile
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import os
import time

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe_input import QEInputParser, QEInputGenerator

# Import test function
import importlib.util
# Try extended-tests/utils first, then fallback to tests
test_file = project_root / "extended-tests" / "utils" / "test_qe_roundtrip_execution.py"
if not test_file.exists():
    test_file = project_root / "tests" / "test_qe_roundtrip_execution.py"
spec = importlib.util.spec_from_file_location("test_qe_roundtrip_execution", test_file)
test_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_module)
test_input_roundtrip_execution = test_module.test_input_roundtrip_execution
ensure_pseudopotentials = test_module.ensure_pseudopotentials


def parse_jobconfig(jobconfig_path: Path) -> Dict[str, List[Tuple[str, str]]]:
    """
    Parse jobconfig file to get test order.
    
    Returns:
        Dict mapping category name to list of (input_file, args) tuples
    """
    config = configparser.ConfigParser()
    config.read(jobconfig_path)
    
    tests = {}
    for section in config.sections():
        # Section names may have trailing slash, e.g., "pw_dft/" or "pw_dft"
        section_name = section.rstrip('/')
        if section_name.startswith('pw_'):
            if 'inputs_args' in config[section]:
                try:
                    inputs = eval(config[section]['inputs_args'])
                    tests[section_name] = inputs
                except Exception as e:
                    # If eval fails, skip this section
                    print(f"Warning: Could not parse inputs_args for {section}: {e}")
                    tests[section_name] = []
            else:
                # No inputs_args - might be a category with default behavior
                tests[section_name] = []
    
    return tests


def compare_with_benchmark(
    output_file: Path,
    benchmark_file: Path,
    tolerance: Optional[float] = None,
    category: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Compare test output with benchmark output.
    
    This is a simplified version - the real testcode does more sophisticated
    numerical comparison. For now, we check:
    1. JOB DONE in output
    2. Total energy matches benchmark (if available)
    
    Args:
        output_file: Path to test output
        benchmark_file: Path to benchmark output
        tolerance: Numerical tolerance for energy comparison (if None, uses threshold from thresholds.py)
        category: Test category name for category-specific thresholds
        
    Returns:
        Tuple of (pass, message)
    """
    # Import unified thresholds
    from tests.core.thresholds import get_energy_tolerance
    
    # Use unified thresholds if tolerance not provided
    if tolerance is None:
        tolerance = get_energy_tolerance(category, "pw.x")
    if not output_file.exists():
        return False, "Output file not found"
    
    if not benchmark_file.exists():
        # No benchmark to compare - just check for JOB DONE
        content = output_file.read_text()
        if "JOB DONE" in content:
            return True, "JOB DONE (no benchmark to compare)"
        return False, "JOB DONE not found"
    
    # Read both files
    output_content = output_file.read_text()
    benchmark_content = benchmark_file.read_text()
    
    # Check for JOB DONE
    if "JOB DONE" not in output_content:
        return False, "JOB DONE not found in output"
    
    # Extract total energy from both files
    def extract_energy(content: str) -> float:
        """Extract total energy from QE output."""
        import re
        # Look for "!    total energy" or "total energy"
        patterns = [
            r"!\s+total energy\s+=\s+([-\d.]+)\s+Ry",
            r"total energy\s+=\s+([-\d.]+)\s+Ry",
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None
    
    output_energy = extract_energy(output_content)
    benchmark_energy = extract_energy(benchmark_content)
    
    if output_energy is None:
        return False, "Could not extract energy from output"
    
    if benchmark_energy is None:
        return True, f"JOB DONE (energy: {output_energy:.8f} Ry, no benchmark energy)"
    
    # Compare energies
    energy_diff = abs(output_energy - benchmark_energy)
    if energy_diff > tolerance:
        return False, f"Energy mismatch: {output_energy:.8f} vs {benchmark_energy:.8f} (diff: {energy_diff:.2e})"
    
    return True, f"Energy matches: {output_energy:.8f} Ry (diff: {energy_diff:.2e})"


def run_test_category(
    category: str,
    test_files: List[Tuple[str, str]],
    test_suite_dir: Path,
    qe_engine: QuantumEspressoEngine,
    timeout: int = 60,
    max_tests: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Run all tests in a category.
    
    For workflow tests (multiple sequential tests), all tests run in the same
    working directory to preserve intermediate files.
    
    Args:
        category: Category name (e.g., "pw_dft")
        test_files: List of (input_file, args) tuples
        test_suite_dir: Test suite root directory
        qe_engine: Configured QE engine
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
    
    # Check if this is a workflow test (multiple sequential tests with args)
    is_workflow = len(test_files) > 1 and any(args for _, args in test_files)
    
    # For workflow tests, use a single working directory for all tests
    # This preserves intermediate files (wavefunctions, charge density, etc.)
    if is_workflow:
        working_dir = Path(tempfile.mkdtemp(prefix=f"qe_workflow_{category}_"))
        # Ensure pseudopotentials are available (check first test)
        if test_files:
            first_test_path = category_dir / test_files[0][0]
            if first_test_path.exists():
                from tests.test_qe_roundtrip_execution import ensure_pseudopotentials
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
            
            # Run test
            # For workflow tests, reuse the same working directory and pass step number
            if is_workflow:
                result = test_input_roundtrip_execution(test_path, qe_engine, timeout, working_dir, args)
            else:
                result = test_input_roundtrip_execution(test_path, qe_engine, timeout, None, None)
            result["category"] = category
            result["file"] = input_file
            result["step"] = args if args else str(i+1)
            
            # Compare with benchmark if available
            # For workflow tests, benchmark filename includes step number
            if args:
                benchmark_file = category_dir / f"benchmark.out.git.inp={input_file}.args={args}"
            else:
                benchmark_file = category_dir / f"benchmark.out.git.inp={input_file}"
            
            if result["run_success"]:
                # Get working directory from result or use the shared one
                result_working_dir = None
                if result.get("output_file"):
                    result_working_dir = Path(result["output_file"]).parent
                elif is_workflow:
                    result_working_dir = working_dir
                else:
                    # Try to find from generated input
                    pass
                
                if result_working_dir:
                    stdout_file = result_working_dir / "stdout.txt"
                    if stdout_file.exists():
                        pass_test, message = compare_with_benchmark(stdout_file, benchmark_file)
                        result["benchmark_match"] = pass_test
                        result["benchmark_message"] = message
                        # Update success based on benchmark comparison
                        if result["verify_success"]:
                            result["success"] = pass_test
                            result["message"] = message
            
            results.append(result)
            
            # For workflow tests, if a step fails, we might not be able to continue
            # But we'll try to continue anyway to see all errors
    
    except Exception as e:
        # If there's an error, add it to results
        results.append({
            "category": category,
            "file": "unknown",
            "success": False,
            "error": f"Category execution failed: {e}",
            "time_taken": 0
        })
    
    # For workflow tests, the final result is the last step
    # Only mark as success if all steps succeeded
    if is_workflow and len(results) > 0:
        all_steps_success = all(r.get("run_success", False) for r in results)
        final_result = results[-1]
        if all_steps_success and final_result.get("verify_success", False):
            # Check benchmark for final step
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


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run pw tests in official test suite style")
    parser.add_argument(
        "--qe-path",
        type=Path,
        default=Path.home() / "src" / "q-e-qe-7.5" / "bin",
        help="Path to QE bin directory"
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=None,
        help="Path to QE test suite directory (default: inferred from --qe-path)"
    )
    parser.add_argument(
        "--category",
        type=str,
        default="pw_dft",
        help="Test category to run (e.g., pw_dft, pw_atom)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout per test in seconds"
    )
    
    args = parser.parse_args()
    
    # Infer test-suite directory from QE path if not provided
    if args.test_dir is None:
        # QE bin is typically at $QE_ROOT/bin, test-suite is at $QE_ROOT/test-suite
        qe_bin = args.qe_path
        if qe_bin.is_dir():
            # If qe_path is a directory (bin), go up one level
            qe_root = qe_bin.parent
        else:
            # If qe_path is a file (pw.x), go up two levels
            qe_root = qe_bin.parent.parent
        args.test_dir = qe_root / "test-suite"
    
    if not args.test_dir.exists():
        print(f"Error: Test suite directory not found: {args.test_dir}")
        print(f"Please specify --test-dir or ensure QE is installed with test-suite")
        sys.exit(1)
    
    # Setup QE engine
    config = EngineConfig(name="qe", executable_path=args.qe_path)
    engine = QuantumEspressoEngine(config)
    
    if not engine.detect_executable("pw.x"):
        print(f"ERROR: pw.x not found at {args.qe_path}")
        sys.exit(1)
    
    print(f"QE Engine: {engine.get_executable_path('pw.x')}")
    print(f"Test suite: {args.test_dir}")
    print(f"Category: {args.category}")
    print("=" * 60)
    
    # Parse jobconfig
    jobconfig_path = args.test_dir / "jobconfig"
    if not jobconfig_path.exists():
        print(f"ERROR: jobconfig not found at {jobconfig_path}")
        sys.exit(1)
    
    tests = parse_jobconfig(jobconfig_path)
    
    # Handle category name with or without trailing slash
    category_key = args.category.rstrip('/')
    if category_key not in tests:
        print(f"ERROR: Category '{args.category}' not found in jobconfig")
        print(f"Available categories: {list(tests.keys())[:10]}")
        sys.exit(1)
    
    test_files = tests[category_key]
    
    # If no test files defined in jobconfig, find all .in files in the directory
    if not test_files:
        category_dir = args.test_dir / category_key
        if category_dir.exists():
            test_files = [(f.name, '') for f in sorted(category_dir.glob("*.in")) 
                         if not f.name.startswith("benchmark")]
            print(f"Note: No inputs_args in jobconfig, found {len(test_files)} .in files")
    print(f"\nRunning {len(test_files)} tests in {args.category}...")
    print(f"Test order: {[f[0] for f in test_files]}\n")
    
    # Run tests
    all_results = []
    for i, (input_file, args_str) in enumerate(test_files):
        print(f"[{i+1}/{len(test_files)}] {input_file}...", end=" ", flush=True)
        
        test_path = args.test_dir / args.category / input_file
        if not test_path.exists():
            print("SKIP (file not found)")
            continue
        
        result = test_input_roundtrip_execution(test_path, engine, args.timeout)
        
        # Check benchmark
        benchmark_file = args.test_dir / args.category / f"benchmark.out.git.inp={input_file}"
        working_dir = Path(result.get("output_file", "")).parent if result.get("output_file") else None
        
        if result["run_success"] and working_dir:
            stdout_file = working_dir / "stdout.txt"
            if stdout_file.exists():
                pass_test, message = compare_with_benchmark(stdout_file, benchmark_file)
                result["benchmark_match"] = pass_test
                result["benchmark_message"] = message
                if result["verify_success"]:
                    result["success"] = pass_test
        
        all_results.append(result)
        
        if result["success"]:
            print(f"✓ PASS ({result['time_taken']:.1f}s): {result.get('benchmark_message', result.get('message', 'OK'))}")
        else:
            error_msg = result.get('error', result.get('message', 'Unknown error'))
            print(f"✗ FAIL ({result['time_taken']:.1f}s): {error_msg[:80]}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in all_results if r.get("success", False))
    failed = len(all_results) - passed
    
    print(f"Total tests: {len(all_results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\nFailed tests:")
        for r in all_results:
            if not r.get("success", False):
                print(f"  - {r.get('file', 'unknown')}: {r.get('error', r.get('message', 'Unknown'))[:100]}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

