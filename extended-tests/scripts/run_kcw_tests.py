#!/usr/bin/env python3
"""
Run kcw tests in the same style as the official QE test suite.

KCW (Koopmans-compliant Wannier functions) tests require:
- arg=1: pw.x (SCF calculation)
- arg=2: wannier90.x -pp (preprocessing)
- arg=3: pw2wannier90.x
- arg=4: wannier90.x
- arg=5,15: kcw.x (interface)
- arg=6,16: kcw.x (screen)
- arg=7: kcw.x (hamiltonian)
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
    parser = argparse.ArgumentParser(description="Run kcw tests in official test suite style")
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
        default=None,
        help="Test category to run. If not specified, runs all kcw categories"
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
    
    # Infer test-suite directory from QE path if not provided
    if args.test_dir is None:
        qe_bin = args.qe_path
        if qe_bin.is_dir():
            qe_root = qe_bin.parent
        else:
            qe_root = qe_bin.parent.parent
        args.test_dir = qe_root / "test-suite"
    
    if not args.test_dir.exists():
        print(f"Error: Test suite directory not found: {args.test_dir}")
        sys.exit(1)
    
    # Setup QE engine
    config = EngineConfig(name="qe", executable_path=args.qe_path)
    engine = QuantumEspressoEngine(config)
    
    if not engine.detect_executable("pw.x"):
        print(f"ERROR: pw.x not found at {args.qe_path}")
        sys.exit(1)
    
    print(f"QE Engine: {engine.get_executable_path('pw.x')}")
    print(f"Test suite: {args.test_dir}")
    
    # Parse jobconfig for kcw tests
    jobconfig_path = args.test_dir / "jobconfig"
    all_tests = parse_jobconfig(jobconfig_path, "kcw_")
    
    if args.category:
        if args.category not in all_tests:
            print(f"ERROR: Category '{args.category}' not found")
            sys.exit(1)
        categories_to_run = {args.category: all_tests[args.category]}
    else:
        categories_to_run = all_tests
    
    print(f"Running {len(categories_to_run)} kcw test categories...")
    print("=" * 60)
    
    # Executable map based on run-kcw.sh:
    # arg=1: pw.x
    # arg=2: wannier90.x -pp (preprocessing)
    # arg=3: pw2wannier90.x
    # arg=4: wannier90.x
    # arg=5,15: kcw.x (interface)
    # arg=6,16: kcw.x (screen)
    # arg=7: kcw.x (hamiltonian)
    # Note: wannier90.x is external, may not be in QE bin directory
    executable_map = {
        "1": "pw.x",
        "2": "wannier90.x",  # External dependency
        "3": "pw2wannier90.x",
        "4": "wannier90.x",  # External dependency
        "5": "kcw.x",
        "6": "kcw.x",
        "7": "kcw.x",
        "15": "kcw.x",
        "16": "kcw.x",
        "default": "kcw.x"
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

