#!/usr/bin/env python3
"""
Run cp tests in the same style as the official QE test suite.
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
)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run cp tests in official test suite style")
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
        help="Test category to run. If not specified, runs all cp categories"
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
        sys.exit(1)
    
    if not engine.detect_executable("cp.x"):
        print(f"ERROR: cp.x not found")
        sys.exit(1)
    
    print(f"QE home: {engine.installation.qe_home}")
    print(f"CP Engine: {engine.get_executable_path('cp.x')}")
    print(f"Test suite: {args.test_dir}")
    
    # Parse jobconfig for cp tests
    jobconfig_path = args.test_dir / "jobconfig"
    all_tests = parse_jobconfig(jobconfig_path, "cp_")
    
    if args.category:
        if args.category not in all_tests:
            print(f"ERROR: Category '{args.category}' not found")
            sys.exit(1)
        categories_to_run = {args.category: all_tests[args.category]}
    else:
        categories_to_run = all_tests
    
    print(f"Running {len(categories_to_run)} cp test categories...")
    print("=" * 60)
    
    # CP tests directly use cp.x (no workflow)
    executable_map = {
        "default": "cp.x"
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
        
        passed = sum(1 for r in category_results if r.get("success", False))
        failed = len(category_results) - passed
        print(f"  {category}: {passed} passed, {failed} failed")
        
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
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

