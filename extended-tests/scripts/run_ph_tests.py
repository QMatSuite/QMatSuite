#!/usr/bin/env python3
"""
Run ph tests in the same style as the official QE test suite.

This script:
1. Reads jobconfig to get ph test order and files
2. Runs each test file in the specified order (pw.x first, then ph.x)
3. Compares output with benchmark files to determine pass/fail
4. Reports results in a format similar to testcode.py
"""

import sys
from pathlib import Path
import argparse

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "extended-tests"))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from utils.qe_module_base import (
    parse_jobconfig,
    run_test_category,
    compare_with_benchmark
)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run ph tests in official test suite style")
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
        "--category",
        type=str,
        default=None,
        help="Test category to run (e.g., ph_base, ph_metal). If not specified, runs all ph categories"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout per test in seconds"
    )
    parser.add_argument(
        "--max-tests",
        type=int,
        default=None,
        help="Maximum number of tests per category"
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
    
    if not engine.detect_executable("pw.x"):
        print(f"ERROR: pw.x not found")
        sys.exit(1)
    
    if not engine.detect_executable("ph.x"):
        print(f"ERROR: ph.x not found")
        sys.exit(1)
    
    print(f"QE home: {engine.installation.qe_home}")
    print(f"QE Engine: {engine.get_executable_path('pw.x')}")
    print(f"PH Engine: {engine.get_executable_path('ph.x')}")
    print(f"Test suite: {args.test_dir}")
    
    # Parse jobconfig for ph tests
    jobconfig_path = args.test_dir / "jobconfig"
    if not jobconfig_path.exists():
        print(f"ERROR: jobconfig not found at {jobconfig_path}")
        sys.exit(1)
    
    all_tests = parse_jobconfig(jobconfig_path, "ph_")
    
    if args.category:
        # Run specific category
        if args.category not in all_tests:
            print(f"ERROR: Category '{args.category}' not found")
            print(f"Available categories: {list(all_tests.keys())}")
            sys.exit(1)
        categories_to_run = {args.category: all_tests[args.category]}
    else:
        # Run all ph categories
        categories_to_run = all_tests
    
    print(f"Running {len(categories_to_run)} ph test categories...")
    print("=" * 60)
    
    # Executable map: maps step args to executable names
    # Based on run-ph.sh:
    # arg=1: pw.x
    # arg=2, 11: ph.x
    # arg=3: q2r.x
    # arg=4, 8: matdyn.x
    # arg=5: lambda.x
    # arg=6: dvscf_q2r.x
    # arg=7: postahc.x
    # arg=9: dynmat.x
    # arg=12: pw.x
    # arg=13: ph.x
    executable_map = {
        "1": "pw.x",
        "2": "ph.x",
        "3": "q2r.x",
        "4": "matdyn.x",
        "5": "lambda.x",
        "6": "dvscf_q2r.x",
        "7": "postahc.x",
        "8": "matdyn.x",
        "9": "dynmat.x",
        "11": "ph.x",
        "12": "pw.x",
        "13": "ph.x",
        "default": "ph.x"
    }
    
    all_results = []
    for i, (category, test_files) in enumerate(sorted(categories_to_run.items()), 1):
        if not test_files:
            print(f"[{i}/{len(categories_to_run)}] Category: {category}")
            print("  SKIP (no tests)")
            continue
        
        print(f"\n[{i}/{len(categories_to_run)}] Category: {category}")
        print(f"  Running {len(test_files)} tests...")
        
        category_results = run_test_category(
            category,
            test_files,
            args.test_dir,
            engine,
            executable_map,
            args.timeout,
            args.max_tests
        )
        
        all_results.extend(category_results)
        
        # Print summary for this category
        passed = sum(1 for r in category_results if r.get("success", False))
        failed = len(category_results) - passed
        print(f"  {category}: {passed} passed, {failed} failed")
        
        # Print individual results
        for result in category_results:
            if result.get("success", False):
                msg = result.get("benchmark_message", result.get("message", "OK"))
                print(f"    ✓ PASS ({result.get('time_taken', 0):.1f}s): {result['file']} - {msg}")
            else:
                error = result.get("error") or result.get("message") or "Unknown error"
                error_str = str(error)[:100] if error else "Unknown error"
                print(f"    ✗ FAIL ({result.get('time_taken', 0):.1f}s): {result['file']} - {error_str}")
    
    # Overall summary
    print("\n" + "=" * 60)
    print("OVERALL SUMMARY")
    print("=" * 60)
    total = len(all_results)
    passed = sum(1 for r in all_results if r.get("success", False))
    failed = total - passed
    
    print(f"Total tests: {total}")
    print(f"Passed: {passed} ({passed/total*100:.1f}%)" if total > 0 else "Passed: 0")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)" if total > 0 else "Failed: 0")
    
    if failed > 0:
        print("\nFailed tests:")
        for r in all_results:
            if not r.get("success", False):
                cat = r.get("category", "unknown")
                file = r.get("file", "unknown")
                error = r.get("error") or r.get("message") or "Unknown error"
                error_str = str(error)[:80] if error else "Unknown error"
                print(f"  - {cat}/{file}: {error_str}")
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

