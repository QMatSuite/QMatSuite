#!/usr/bin/env python3
"""Copy all SCF tests with benchmarks from QE test-suite.

This script uses the general copy_test_files utility to copy all SCF tests
to temp/pw_scf_all/.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.copy_test_files import copy_test_files, find_test_suite_dir


def main() -> int:
    """Entry point for the copy script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Copy all SCF tests with benchmarks from QE test-suite"
    )
    parser.add_argument(
        "--test-suite-dir",
        type=Path,
        help="Path to QE test-suite directory (auto-detected if not provided)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "temp" / "pw_scf_all",
        help="Output directory (default: temp/pw_scf_all)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages",
    )
    args = parser.parse_args()

    # Find test-suite directory
    if args.test_suite_dir:
        test_suite_dir = args.test_suite_dir
        if not test_suite_dir.exists():
            print(f"Error: Test-suite directory not found: {test_suite_dir}")
            return 1
    else:
        test_suite_dir = find_test_suite_dir()
        if not test_suite_dir:
            print("Error: QE test-suite directory not found.")
            print("Set QE_BIN_DIR environment variable or provide --test-suite-dir")
            return 1

    # Copy files (no filename filter, copy all SCF tests)
    copied_count, skipped_count, copied_files = copy_test_files(
        test_suite_dir,
        args.output,  # Pass full output path
        step_type="scf",
        filename_filter=None,
        verbose=not args.quiet,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Copied: {copied_count} SCF tests (with benchmarks)")
    print(f"Skipped: {skipped_count} SCF tests (no benchmark found)")
    print(f"Output: {args.output}")
    
    if copied_files and not args.quiet:
        print(f"\nCopied files:")
        for category, filename in sorted(copied_files):
            print(f"  - {category}/{filename}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

