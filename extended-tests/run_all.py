#!/usr/bin/env python3
"""
Run all extended tests.

Extended tests are comprehensive tests based on the full QE official test-suite.
These tests are NOT run automatically in CI.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "extended-tests"))  # Add extended-tests to path

from suites.qe_testsuite import QETestSuite
from tests.core.runner import TestRunner


def create_suites(qe_bin_dir: Path, test_suite_dir: Path) -> dict:
    """Create and register all extended test suites."""
    suites = {}
    
    # QE test suites for different modules
    qe_modules = {
        "pw": "pw_",
        "ph": "ph_",
        "pp": "pp_",
        "cp": "cp_",
        "hp": "hp_",
        "tddfpt": "tddfpt_",
        "kcw": "kcw_",
        "epw": "epw_",
        "zg": "zg_",
        "all_currents": "all_currents_",
    }
    
    for module_name, prefix in qe_modules.items():
        suite = QETestSuite(
            test_suite_dir=test_suite_dir,
            qe_bin_dir=qe_bin_dir,
            module_prefix=prefix,
            description=f"QE official test-suite for {module_name} module (extended)"
        )
        suites[f"qe-{module_name}"] = suite
    
    return suites


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="QuantumVITAS Extended Tests Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
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
        help="Path to QE test suite directory"
    )
    parser.add_argument(
        "--suite",
        type=str,
        help="Run specific test suite"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all extended test suites"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120,
        help="Timeout per test in seconds"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Export results to file"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available test suites"
    )
    
    args = parser.parse_args()
    
    # List suites if requested
    if args.list:
        # Create temporary suites to list them
        if args.test_dir is None:
            qe_bin = args.qe_path
            if qe_bin.is_dir():
                qe_root = qe_bin.parent
            else:
                qe_root = qe_bin.parent.parent
            args.test_dir = qe_root / "test-suite"
        
        if args.test_dir.exists():
            suites = create_suites(args.qe_path, args.test_dir)
            print("Available extended test suites:")
            print("=" * 60)
            for name, suite in sorted(suites.items()):
                print(f"  {name:20s} - {suite.description}")
        else:
            print(f"Error: Test suite directory not found: {args.test_dir}")
        sys.exit(0)
    
    # Infer test-suite directory
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
    
    # Create suites
    suites = create_suites(args.qe_path, args.test_dir)
    
    # Create runner
    runner = TestRunner()
    for suite in suites.values():
        runner.register_suite(suite)
    
    # Run tests
    if args.all:
        print("Running all extended test suites...")
        runner.run_all(timeout=args.timeout)
        runner.print_overall_summary()
    elif args.suite:
        runner.run_suite(args.suite, timeout=args.timeout)
    else:
        parser.print_help()
        sys.exit(1)
    
    # Export results
    if args.output:
        runner.export_results(args.output, format="json")
        print(f"\nResults exported to: {args.output}")
    
    # Exit code
    summary = runner.get_overall_summary()
    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()

