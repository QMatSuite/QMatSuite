#!/usr/bin/env python3
"""
Run tests from multiple pw test categories.
"""

import sys
from pathlib import Path
import subprocess

# Add src and tests to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "extended-tests"))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig

# Import from new locations
from quantumvitas.core.engines import ensure_pseudopotentials
from tests.core import run_and_verify_step_with_assert


def main():
    """Run tests from multiple pw categories."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run multiple pw test categories")
    parser.add_argument(
        "--qe-home",
        type=Path,
        default=None,
        help="Path to QE home directory (contains bin/ and test-suite/). If not specified, will auto-detect."
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=None,
        help="Path to QE test suite directory (default: auto-detected from QE installation)"
    )
    parser.add_argument(
        "--num-categories",
        type=int,
        default=10,
        help="Number of test categories to run"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout per test in seconds"
    )
    
    args = parser.parse_args()
    
    # Setup QE engine (auto-detect if not provided)
    if args.qe_home:
        config = EngineConfig(name="qe", executable_path=args.qe_home)
    else:
        config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)
    
    if not engine.installation.is_valid():
        print("ERROR: QE installation not found.")
        print("Please specify --qe-home or ensure QE is installed and accessible.")
        sys.exit(1)
    
    # Use auto-detected test-suite directory if not provided
    if args.test_dir is None:
        args.test_dir = engine.test_suite_dir
    
    if not args.test_dir or not args.test_dir.exists():
        print(f"Error: Test suite directory not found: {args.test_dir}")
        print(f"Please specify --test-dir or ensure QE is installed with test-suite")
        sys.exit(1)
    
    # Check if pw.x is available
    if not engine.detect_executable("pw.x"):
        print(f"ERROR: pw.x not found")
        sys.exit(1)
    
    print(f"QE home: {engine.installation.qe_home}")
    print(f"QE Engine configured: {engine.get_executable_path('pw.x')}")
    print(f"Test directory: {args.test_dir}")
    print(f"Running first {args.num_categories} pw test categories...")
    print("=" * 60)
    
    # Find all pw test directories
    test_suite_dir = args.test_dir
    pw_dirs = sorted([d for d in test_suite_dir.iterdir() 
                     if d.is_dir() and d.name.startswith("pw_")])
    
    if not pw_dirs:
        print(f"ERROR: No pw_* directories found in {test_suite_dir}")
        sys.exit(1)
    
    # Limit to requested number
    pw_dirs = pw_dirs[:args.num_categories]
    
    print(f"Found {len(pw_dirs)} test categories\n")
    
    # Run tests
    all_results = []
    for i, pw_dir in enumerate(pw_dirs):
        print(f"[{i+1}/{len(pw_dirs)}] Testing category: {pw_dir.name}")
        
        # Find first .in file in this directory
        input_files = sorted([f for f in pw_dir.glob("*.in") 
                             if not f.name.startswith("benchmark")])
        
        if not input_files:
            print(f"  ⚠ SKIP: No test files found")
            continue
        
        # Run first test file
        input_file = input_files[0]
        print(f"  File: {input_file.name}")
        
        # Use standardized step execution
        import tempfile
        test_working_dir = Path(tempfile.mkdtemp(prefix="qe_test_"))
        try:
            step_result = run_and_verify_step_with_assert(
                input_file=input_file,
                qe_engine=engine,
                working_dir=test_working_dir,
                reference_file=None,
                category=pw_dir.name,
                timeout=args.timeout
            )
            all_results.append({
                "category": pw_dir.name,
                "file": input_file.name,
                "success": step_result.success,
                "error": step_result.error,
                "message": f"Step {step_result.step_type} completed",
                "time_taken": step_result.execution_time
            })
        except AssertionError as e:
            all_results.append({
                "category": pw_dir.name,
                "file": input_file.name,
                "success": False,
                "error": str(e),
                "time_taken": 0
            })
        
        if result["success"]:
            print(f"  ✓ PASS ({result['time_taken']:.1f}s): {result.get('message', 'OK')}")
        else:
            error_msg = result.get('error', result.get('message', 'Unknown error'))
            print(f"  ✗ FAIL ({result['time_taken']:.1f}s): {error_msg[:100]}")
        print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in all_results if r["success"])
    failed = len(all_results) - passed
    
    print(f"Total categories: {len(all_results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\nFailed tests:")
        for r in all_results:
            if not r["success"]:
                error_msg = r.get('error', r.get('message', 'Unknown error'))
                print(f"  - {r['category']}/{r['file']}: {error_msg[:100]}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

