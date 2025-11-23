#!/usr/bin/env python3
"""
Unified test runner for QuantumVITAS.

This script provides a unified interface to run all types of tests:
- QE official test-suite tests
- Bidirectional conversion tests
- Future test types

Usage:
    python3 tests/run_tests.py --suite qe-pw
    python3 tests/run_tests.py --suite qe-ph --timeout 120
    python3 tests/run_tests.py --all  # Run all test suites
    python3 tests/run_tests.py --list  # List available suites
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from tests.core.runner import TestRunner
from tests.suites.qe_testsuite import QETestSuite


def create_suites(qe_bin_dir: Path, test_suite_dir: Path) -> dict:
    """
    Create and register all available test suites.
    
    Returns:
        Dictionary mapping suite names to TestSuite objects
    """
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
            description=f"QE official test-suite for {module_name} module"
        )
        suites[f"qe-{module_name}"] = suite
    
    # TODO: Add bidirectional test suite
    # from tests.suites.bidirectional import BidirectionalTestSuite
    # suites["bidirectional"] = BidirectionalTestSuite(...)
    
    return suites


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="QuantumVITAS Unified Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all PW tests
  python3 tests/run_tests.py --suite qe-pw
  
  # Run PH tests with timeout
  python3 tests/run_tests.py --suite qe-ph --timeout 120
  
  # Run all test suites
  python3 tests/run_tests.py --all
  
  # List available suites
  python3 tests/run_tests.py --list
        """
    )
    
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
        "--suite",
        type=str,
        help="Run specific test suite (use --list to see available suites)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all test suites"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available test suites"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Timeout per test in seconds"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Export results to file"
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format for export"
    )
    
    args = parser.parse_args()
    
    # Setup QE engine (auto-detect if not provided)
    from quantumvitas.core.engines.qe import QuantumEspressoEngine
    from quantumvitas.core.engines.base import EngineConfig
    
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
    
    # Create test suites
    suites = create_suites(engine.installation.qe_home, args.test_dir)
    
    # List suites if requested
    if args.list:
        print("Available test suites:")
        print("=" * 60)
        for name, suite in sorted(suites.items()):
            print(f"  {name:20s} - {suite.description}")
        sys.exit(0)
    
    # Create runner and register suites
    runner = TestRunner()
    for suite in suites.values():
        runner.register_suite(suite)
    
    # Run tests
    if args.all:
        print("Running all test suites...")
        runner.run_all(timeout=args.timeout)
        runner.print_overall_summary()
    elif args.suite:
        if args.suite not in suites:
            print(f"Error: Test suite '{args.suite}' not found")
            print("\nAvailable suites:")
            for name in sorted(suites.keys()):
                print(f"  - {name}")
            sys.exit(1)
        runner.run_suite(args.suite, timeout=args.timeout)
    else:
        parser.print_help()
        sys.exit(1)
    
    # Export results if requested
    if args.output:
        runner.export_results(args.output, format=args.format)
        print(f"\nResults exported to: {args.output}")
    
    # Exit with appropriate code
    summary = runner.get_overall_summary()
    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()

