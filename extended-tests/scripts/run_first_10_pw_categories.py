#!/usr/bin/env python3
"""
Run first 10 pw test categories in official test suite style.
Each category runs the first test file as defined in jobconfig.
"""

import sys
from pathlib import Path
import configparser

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig

# Import test functions
import importlib.util
test_file = project_root / "tests" / "run_pw_tests_official_style.py"
spec = importlib.util.spec_from_file_location("run_pw_tests_official_style", test_file)
test_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_module)


def main():
    """Run first 10 pw categories."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run first 10 pw test categories")
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
    
    # Parse jobconfig to get categories
    jobconfig_path = args.test_dir / "jobconfig"
    config = configparser.ConfigParser()
    config.read(jobconfig_path)
    
    # Get all pw categories with their test files, sorted
    categories = []
    for section in sorted(config.sections()):
        section_name = section.rstrip('/')
        if section_name.startswith('pw_'):
            if 'inputs_args' in config[section]:
                try:
                    inputs = eval(config[section]['inputs_args'])
                    if inputs:  # Only add if has tests
                        categories.append((section_name, inputs))
                except:
                    pass
    
    # Take first 20
    categories = categories[:20]
    
    print(f"QE Engine: {args.qe_path}")
    print(f"Test suite: {args.test_dir}")
    print(f"Running first {len(categories)} pw test categories...")
    print("=" * 60)
    
    # Setup engine
    engine_config = EngineConfig(name="qe", executable_path=args.qe_path)
    engine = QuantumEspressoEngine(engine_config)
    
    if not engine.detect_executable("pw.x"):
        print(f"ERROR: pw.x not found at {args.qe_path}")
        sys.exit(1)
    
    # Run each category (first test only)
    all_results = []
    for i, (category, test_files) in enumerate(categories):
        print(f"\n[{i+1}/{len(categories)}] Category: {category}")
        
        # Run first test only
        category_results = test_module.run_test_category(
            category,
            test_files[:1],  # Only first test
            args.test_dir,
            engine,
            args.timeout
        )
        
        all_results.extend(category_results)
        
        # Print result
        if category_results:
            result = category_results[0]
            if result.get("success", False):
                msg = result.get("benchmark_message", result.get("message", "OK"))
                print(f"  ✓ PASS ({result['time_taken']:.1f}s): {msg}")
            else:
                error = result.get("error") or result.get("message") or "Unknown error"
                error_str = str(error)[:100] if error else "Unknown error"
                print(f"  ✗ FAIL ({result.get('time_taken', 0):.1f}s): {error_str}")
    
    # Overall summary
    print("\n" + "=" * 60)
    print("OVERALL SUMMARY")
    print("=" * 60)
    
    total_passed = sum(1 for r in all_results if r.get("success", False))
    total_failed = len(all_results) - total_passed
    
    print(f"Total tests: {len(all_results)}")
    print(f"Passed: {total_passed} ({100*total_passed/len(all_results):.1f}%)")
    print(f"Failed: {total_failed} ({100*total_failed/len(all_results):.1f}%)")
    
    if total_failed > 0:
        print("\nFailed tests:")
        for r in all_results:
            if not r.get("success", False):
                cat = r.get("category", "unknown")
                file = r.get("file", "unknown")
                error = r.get("error") or r.get("message") or "Unknown error"
                error_str = str(error)[:80] if error else "Unknown error"
                print(f"  - {cat}/{file}: {error_str}")
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
