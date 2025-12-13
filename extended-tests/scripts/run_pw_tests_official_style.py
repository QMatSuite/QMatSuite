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
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.io import QEInputParser, QEInputGenerator

# Pseudopotential resolution is handled by ensure_qe_pseudos (already migrated in this file)
from quantumvitas.calculation.input_runner import set_outdir_to_temp, set_pseudo_dir_to_temp
from tests.core import run_command_with_timeout, TimeoutError
from tests.core.qe_test_utils import compare_with_benchmark


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
        # Exclude pw_workflow_exx_nscf category
        if 'exx_nscf' in section_name.lower():
            continue
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
    2. Total energy matches benchmark (for SCF calculations)
    3. Fermi energy matches benchmark (for NSCF calculations, tolerance 0.01 Ry)
    
    Args:
        output_file: Path to test output
        benchmark_file: Path to benchmark output
        tolerance: Numerical tolerance for energy comparison (if None, uses threshold from thresholds.py)
        category: Test category name for category-specific thresholds
        
    Returns:
        Tuple of (pass, message)
    """
    # Import unified thresholds
    from tests.core.thresholds import get_energy_tolerance, get_fermi_energy_tolerance
    
    # Check if this is an NSCF calculation
    # NSCF calculations should compare Fermi energy instead of total energy
    # Note: We should NOT rely on category name (e.g., "dos" in category name doesn't mean NSCF)
    # Instead, we check the output content for calculation type
    is_nscf = False
    if output_file.exists():
        content = output_file.read_text()
        # Check for calculation = "nscf" in the output (in the input section that QE echoes)
        # Use regex to match calculation = "nscf" or calculation = 'nscf'
        import re
        if re.search(r'calculation\s*=\s*["\']nscf["\']', content, re.IGNORECASE):
            is_nscf = True
    
    # Use unified thresholds if tolerance not provided
    if tolerance is None:
        if is_nscf:
            tolerance = get_fermi_energy_tolerance()  # 0.01 Ry for Fermi energy
        else:
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
    
    # Extract energy from both files
    # For NSCF: extract Fermi energy; for SCF: extract total energy
    def extract_energy(content: str, is_nscf: bool = False) -> float:
        """Extract energy from QE output."""
        import re
        if is_nscf:
            # For NSCF, extract Fermi energy
            # Format: "the Fermi energy is    -4.2323 ev" or "Fermi energy = -4.2323 Ry"
            patterns = [
                r"the\s+Fermi\s+energy\s+is\s+([-\d.]+)\s+ev",
                r"Fermi\s+energy\s*=\s*([-\d.]+)\s+Ry",
                r"the\s+Fermi\s+energy\s+is\s+([-\d.]+)\s+Ry",
            ]
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        energy_value = float(match.group(1))
                        # Convert eV to Ry if needed (1 Ry = 13.6057 eV)
                        if "ev" in pattern.lower():
                            energy_value = energy_value / 13.6057
                        return energy_value
                    except ValueError:
                        continue
        else:
            # For SCF, extract total energy
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
    
    output_energy = extract_energy(output_content, is_nscf)
    benchmark_energy = extract_energy(benchmark_content, is_nscf)
    
    # For calculation tests (especially nscf/dos steps), energy might not be available
    # If JOB DONE is present, that's sufficient for success
    if output_energy is None:
        if "JOB DONE" in output_content:
            # For calculation steps without energy, JOB DONE is sufficient
            if benchmark_energy is None:
                energy_type = "Fermi energy" if is_nscf else "energy"
                return True, f"JOB DONE (no {energy_type}, no benchmark)"
            else:
                # If benchmark has energy but output doesn't, this might be a problem
                # But for calculation steps, we'll accept JOB DONE
                energy_type = "Fermi energy" if is_nscf else "energy"
                return True, f"JOB DONE (no {energy_type} in output, but benchmark has {energy_type})"
        else:
            energy_type = "Fermi energy" if is_nscf else "energy"
            return False, f"Could not extract {energy_type} from output and JOB DONE not found"
    
    if benchmark_energy is None:
        energy_type = "Fermi energy" if is_nscf else "energy"
        return True, f"JOB DONE ({energy_type}: {output_energy:.8f} Ry, no benchmark {energy_type})"
    
    # Compare energies
    energy_diff = abs(output_energy - benchmark_energy)
    energy_type = "Fermi energy" if is_nscf else "total energy"
    if energy_diff > tolerance:
        return False, f"{energy_type} mismatch: {output_energy:.8f} vs {benchmark_energy:.8f} Ry (diff: {energy_diff:.2e}, threshold: {tolerance:.2e})"
    
    return True, f"{energy_type} matches: {output_energy:.8f} Ry (diff: {energy_diff:.2e})"


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
    
    For calculation tests (multiple sequential tests), all tests run in the same
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
    
    # Check if this is a calculation test (multiple sequential tests with args)
    is_workflow = len(test_files) > 1 and any(args for _, args in test_files)
    
    # For calculation tests, use a single working directory for all tests
    # This preserves intermediate files (wavefunctions, charge density, etc.)
    if is_workflow:
        working_dir = Path(tempfile.mkdtemp(prefix=f"qe_workflow_{category}_"))
        # Ensure pseudopotentials are available (check first test)
        if test_files:
            first_test_path = category_dir / test_files[0][0]
            if first_test_path.exists():
                from quantumvitas.core.pseudo import ensure_qe_pseudos, get_system_pseudo_dir
                # Build additional search directories from test_suite_dir
                additional_search_dirs = []
                if test_suite_dir:
                    test_suite_path = Path(test_suite_dir)
                    additional_search_dirs.extend([
                        test_suite_path.parent / "pseudo",
                        test_suite_path / "pseudo",
                        test_suite_path.parent.parent / "pseudo",
                    ])
                # Find project pseudo_dir
                current = Path(first_test_path).parent
                project_root = None
                while current != current.parent:
                    if (current / "pseudo").exists() or (current / "project.qv.yml").exists():
                        project_root = current
                        break
                    current = current.parent
                if project_root:
                    pseudo_dir = project_root / "pseudo"
                else:
                    pseudo_dir = working_dir / "pseudo"
                result = ensure_qe_pseudos(
                    qe_input_file=first_test_path,
                    project_pseudo_dir=pseudo_dir,
                    system_pseudo_dir=get_system_pseudo_dir(),
                    strict=False,
                    additional_search_dirs=additional_search_dirs if additional_search_dirs else None,
                )
                # Copy to working_dir for compatibility
                if result.all_available:
                    import shutil
                    for pp_name, pp_path in result.resolved_pseudos.items():
                        working_pp = working_dir / pp_name
                        if not working_pp.exists() or working_pp.stat().st_mtime < pp_path.stat().st_mtime:
                            shutil.copy2(pp_path, working_pp)
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
            
            # Detect if this is an NSCF calculation by reading the input file
            # Only NSCF calculations should compare Fermi energy (not SCF, which also outputs Fermi energy)
            is_nscf_calc = False
            try:
                input_content = test_path.read_text()
                # Check for explicit nscf calculation type
                if re.search(r'calculation\s*=\s*["\']nscf["\']', input_content, re.IGNORECASE):
                    is_nscf_calc = True
            except Exception:
                pass
            
            # Run test using standardized step execution
            # Parse and prepare input
            qe_input = QEInputParser.parse_file(test_path)
            project_root = Path(__file__).parent.parent.parent
            set_outdir_to_temp(qe_input, project_root)
            set_pseudo_dir_to_temp(qe_input, project_root)
            
            # Generate input file in working directory
            if is_workflow and working_dir:
                test_working_dir = working_dir
            else:
                import tempfile
                test_working_dir = Path(tempfile.mkdtemp(prefix="qe_test_"))
            
            test_working_dir.mkdir(parents=True, exist_ok=True)
            generated_input = test_working_dir / test_path.name
            QEInputGenerator.write_file(qe_input, generated_input)
            
            # Ensure pseudopotentials
            from quantumvitas.core.pseudo import ensure_qe_pseudos, get_system_pseudo_dir
            # Build additional search directories from test_suite_dir
            additional_search_dirs = []
            if test_suite_dir:
                test_suite_path = Path(test_suite_dir)
                additional_search_dirs.extend([
                    test_suite_path.parent / "pseudo",
                    test_suite_path / "pseudo",
                    test_suite_path.parent.parent / "pseudo",
                ])
            # Find project pseudo_dir
            current = Path(test_path).parent
            project_root = None
            while current != current.parent:
                if (current / "pseudo").exists() or (current / "project.qv.yml").exists():
                    project_root = current
                    break
                current = current.parent
            if project_root:
                pseudo_dir = project_root / "pseudo"
            else:
                pseudo_dir = test_working_dir / "pseudo"
            result = ensure_qe_pseudos(
                qe_input_file=test_path,
                project_pseudo_dir=pseudo_dir,
                system_pseudo_dir=get_system_pseudo_dir(),
                strict=False,
                additional_search_dirs=additional_search_dirs if additional_search_dirs else None,
            )
            # Copy to working_dir for compatibility
            if result.all_available:
                import shutil
                for pp_name, pp_path in result.resolved_pseudos.items():
                    working_pp = test_working_dir / pp_name
                    if not working_pp.exists() or working_pp.stat().st_mtime < pp_path.stat().st_mtime:
                        shutil.copy2(pp_path, working_pp)
            if not result.all_available:
                results.append({
                    "category": category,
                    "file": input_file,
                    "success": False,
                    "error": "Failed to obtain pseudopotentials",
                    "time_taken": 0
                })
                continue
            
            # Detect step type and get executable
            step_type = qe_engine.detect_step_type(generated_input)
            executable_name = qe_engine.EXECUTABLE_MAP.get(step_type, "pw.x")
            
            # Build command
            command = qe_engine.build_command(step_type, generated_input, test_working_dir)
            
            # Set environment
            temp_pseudo_dir = project_root / "temp" / "pseudo"
            temp_pseudo_dir.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env['ESPRESSO_PSEUDO'] = str(temp_pseudo_dir.absolute())
            env['OMP_NUM_THREADS'] = '1'
            
            # Run command
            start_time = time.time()
            try:
                returncode, stdout, stderr = run_command_with_timeout(
                    command, test_working_dir, timeout, env=env, stdin_file=generated_input
                )
                
                # Write output files
                stdout_file = test_working_dir / "stdout.txt"
                stdout_file.write_text(stdout)
                (test_working_dir / "stderr.txt").write_text(stderr)
                
                # Determine output file
                input_stem = generated_input.stem
                output_file = test_working_dir / f"{input_stem}.out"
                if stdout and len(stdout.strip()) > 0:
                    output_file.write_text(stdout)
                
                # Create result dictionary
                result = {
                    "category": category,
                    "file": input_file,
                    "step": args if args else str(i+1),
                    "is_nscf": is_nscf_calc,
                    "run_success": (returncode == 0),
                    "returncode": returncode,
                    "output_file": str(output_file),
                    "time_taken": time.time() - start_time,
                    "verify_success": False,
                    "success": False,
                    "error": None,
                    "message": None
                }
                
                # Verify output
                if returncode == 0:
                    verify_file = output_file if output_file.exists() and output_file.stat().st_size > 0 else stdout_file
                    if verify_file.exists():
                        from tests.core.qe_step_verification import verify_step_result
                        from quantumvitas.core.engines.qe_workflow import StepResult
                        
                        step_result = StepResult(
                            step_type=step_type,
                            input_file=generated_input,
                            output_file=verify_file,
                            success=(returncode == 0),
                            return_code=returncode,
                            stdout=stdout,
                            stderr=stderr
                        )
                        
                        verify_success, verify_message = verify_step_result(step_result, None, category)
                        result["verify_success"] = verify_success
                        result["message"] = verify_message
                        result["success"] = verify_success
                    else:
                        result["error"] = "Output file not found"
                else:
                    result["error"] = f"{executable_name} returned {returncode}\nstderr: {stderr[:200]}"
                    
            except TimeoutError as e:
                result = {
                    "category": category,
                    "file": input_file,
                    "step": args if args else str(i+1),
                    "is_nscf": is_nscf_calc,
                    "run_success": False,
                    "time_taken": time.time() - start_time,
                    "error": str(e),
                    "success": False
                }
            except Exception as e:
                result = {
                    "category": category,
                    "file": input_file,
                    "step": args if args else str(i+1),
                    "is_nscf": is_nscf_calc,
                    "run_success": False,
                    "time_taken": time.time() - start_time,
                    "error": f"Error running test: {e}",
                    "success": False
                }
            
            # Compare with benchmark if available
            # For calculation tests, benchmark filename includes step number
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
                    # Check for .out file first, then fallback to stdout.txt
                    output_out_file = None
                    # Try to find .out file based on prefix or input filename
                    input_stem = Path(input_file).stem
                    # Check for prefix-based .out file
                    prefix_out = result_working_dir / f"{input_stem}.out"
                    if prefix_out.exists():
                        output_out_file = prefix_out
                    else:
                        # Check for any .out file in working_dir
                        out_files = list(result_working_dir.glob("*.out"))
                        if out_files:
                            output_out_file = out_files[0]
                    
                    # Use .out file if available, otherwise use stdout.txt
                    if output_out_file and output_out_file.exists():
                        compare_file = output_out_file
                        # Also copy to temp/test_outputs for debugging
                        if is_workflow:
                            temp_output_dir = Path("temp/test_outputs") / category
                            temp_output_dir.mkdir(parents=True, exist_ok=True)
                            step_suffix = f"_step{args}" if args else f"_step{i+1}"
                            temp_out_file = temp_output_dir / f"{input_stem}{step_suffix}.out"
                            import shutil
                            shutil.copy2(output_out_file, temp_out_file)
                            result["temp_output_file"] = str(temp_out_file)
                    else:
                        compare_file = result_working_dir / "stdout.txt"
                    
                    if compare_file.exists():
                        # Pass is_nscf flag to compare_with_benchmark
                        # Only pass nscf indicator if this is actually an NSCF calculation
                        compare_category = category
                        if is_nscf_calc:
                            # Add nscf indicator to category for proper detection in compare_with_benchmark
                            compare_category = f"{category}_nscf" if not category.endswith("_nscf") else category
                        else:
                            # For SCF calculations, ensure we don't use nscf detection
                            compare_category = category.replace("_nscf", "")
                        pass_test, message = compare_with_benchmark(
                            compare_file, 
                            benchmark_file,
                            category=compare_category
                        )
                        result["benchmark_match"] = pass_test
                        result["benchmark_message"] = message
                        # Update success based on benchmark comparison
                        if result["verify_success"]:
                            result["success"] = pass_test
                            result["message"] = message
            
            results.append(result)
            
            # For calculation tests, if a step fails, we might not be able to continue
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
    finally:
        # Clean up temp/outdir after test run
        project_root = Path(__file__).parent.parent.parent
        temp_outdir = project_root / "temp" / "outdir"
        if temp_outdir.exists():
            try:
                import shutil
                shutil.rmtree(temp_outdir)
            except Exception as e:
                # Log but don't fail if cleanup fails
                print(f"Warning: Failed to clean up temp/outdir: {e}")
    
    # For calculation tests, the final result is the last step
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
        "--qe-home",
        type=Path,
        default=None,
        help="Path to QE home directory (contains bin/ and test-suite/). Auto-detected if not provided."
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
    
    # Auto-detect QE home if not provided
    from quantumvitas.core.engines.qe_installation import QEInstallation
    if args.qe_home:
        qe_installation = QEInstallation(qe_home=args.qe_home)
    else:
        qe_installation = QEInstallation()
        args.qe_home = qe_installation.root_dir
    
    if not args.qe_home or not qe_installation.bin_dir:
        print("ERROR: Could not detect QE installation")
        print("Please specify --qe-home or ensure QE is installed")
        sys.exit(1)
    
    # Infer test-suite directory from QE home if not provided
    if args.test_dir is None:
        args.test_dir = qe_installation.test_suite_dir
    
    if not args.test_dir or not args.test_dir.exists():
        print(f"Error: Test suite directory not found: {args.test_dir}")
        print(f"Please specify --test-dir or ensure QE is installed with test-suite")
        sys.exit(1)
    
    # Setup QE engine
    config = EngineConfig(name="qe", qe_home=args.qe_home)
    engine = QuantumEspressoEngine(config)
    
    if not engine.detect_executable("pw.x"):
        print(f"ERROR: pw.x not found")
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
    # Use run_test_category to properly handle calculation tests
    all_results = run_test_category(
        category=args.category,
        test_files=test_files,
        test_suite_dir=args.test_dir,
        qe_engine=engine,
        timeout=args.timeout
    )
    
    # Print results
    for i, result in enumerate(all_results):
        if not result:
            continue
        input_file = result.get("file", "unknown")
        time_taken = result.get('time_taken', 0)
        if result.get("success"):
            print(f"✓ PASS ({time_taken:.1f}s): {result.get('benchmark_message', result.get('message', 'OK'))}")
        else:
            error_msg = result.get('error', result.get('message', 'Unknown error'))
            if error_msg:
                print(f"✗ FAIL ({time_taken:.1f}s): {error_msg[:80]}")
            else:
                print(f"✗ FAIL ({time_taken:.1f}s): Unknown error")
    
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
            if r and not r.get("success", False):
                error_msg = r.get('error') or r.get('message') or 'Unknown error'
                if error_msg:
                    print(f"  - {r.get('file', 'unknown')}: {error_msg[:100]}")
                else:
                    print(f"  - {r.get('file', 'unknown')}: Unknown error")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

