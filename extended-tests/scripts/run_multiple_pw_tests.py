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

# Import test function directly
import importlib.util
test_file = project_root / "tests" / "test_qe_roundtrip_execution.py"
spec = importlib.util.spec_from_file_location("test_qe_roundtrip_execution", test_file)
test_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_module)
test_input_roundtrip_execution = test_module.test_input_roundtrip_execution


def main():
    """Run tests from multiple pw categories."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run multiple pw test categories")
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
    
    # Check if pw.x is available
    if not engine.detect_executable("pw.x"):
        print(f"ERROR: pw.x not found at {args.qe_path}")
        print("Please specify correct path with --qe-path")
        sys.exit(1)
    
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
        
        result = test_input_roundtrip_execution(input_file, engine, args.timeout)
        all_results.append({
            "category": pw_dir.name,
            "file": input_file.name,
            **result
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

