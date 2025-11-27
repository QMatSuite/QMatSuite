"""Copy all SCF tests with benchmarks from QE test-suite to extended-tests/suites/pw_scf_all.

This script:
1. Scans the QE test-suite directory
2. Finds all .in files (excluding those with "benchmark" in name)
3. Detects if each file is an SCF calculation
4. Checks if a corresponding benchmark output exists
5. Copies both input and benchmark to extended-tests/suites/pw_scf_all
"""

import shutil
from pathlib import Path
from typing import Optional, Tuple, List

# Import QE detection logic
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from quantumvitas.io import QEInputParser, QEModule
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe import QuantumEspressoEngine


def find_test_suite_dir() -> Optional[Path]:
    """Find QE test-suite directory based on QE_BIN_DIR or default layout."""
    import os

    qe_bin = os.environ.get("QE_BIN_DIR")
    if qe_bin:
        qe_bin = Path(qe_bin)
    else:
        qe_bin = Path.home() / "src" / "q-e-qe-7.5" / "bin"

    if not qe_bin.exists():
        return None

    qe_root = qe_bin if qe_bin.is_dir() else qe_bin.parent
    test_suite = qe_root.parent / "test-suite"
    if test_suite.exists():
        return test_suite

    return None


def is_scf_calculation(input_file: Path) -> bool:
    """
    Detect if an input file is an SCF calculation.
    
    Args:
        input_file: Path to QE input file
        
    Returns:
        True if the file is an SCF calculation, False otherwise
    """
    try:
        qe_input = QEInputParser.parse_file(input_file)
        module = qe_input.detect_module()
        
        # Must be PW module
        if module != QEModule.PW:
            return False
        
        # Check calculation type in control namelist
        control = qe_input.get_namelist('control')
        if control:
            calculation = control.get('calculation', 'scf').lower()
            return calculation == 'scf'
        
        # Default for pw.x without explicit calculation is SCF
        return True
    except Exception as e:
        # If parsing fails, skip this file
        print(f"  ⚠️  Warning: Could not parse {input_file.name}: {e}")
        return False


def find_benchmark_file(category_dir: Path, input_filename: str) -> Optional[Path]:
    """
    Find benchmark output file for an input file.
    
    Looks for files matching pattern: benchmark.out.git.inp={input_filename}*
    
    Args:
        category_dir: Directory containing the input file
        input_filename: Name of the input file
        
    Returns:
        Path to benchmark file if found, None otherwise
    """
    # Pattern: benchmark.out.git.inp={input_filename} or with .args=...
    patterns = [
        f"benchmark.out.git.inp={input_filename}",
        f"benchmark.out.git.inp={input_filename}.args=",
    ]
    
    for pattern in patterns:
        # Try exact match first
        exact_match = category_dir / f"benchmark.out.git.inp={input_filename}"
        if exact_match.exists():
            return exact_match
        
        # Try glob pattern
        matches = list(category_dir.glob(f"benchmark.out.git.inp={input_filename}*"))
        if matches:
            # Return the first match (usually there's only one)
            return matches[0]
    
    return None


def copy_all_scf_tests(
    test_suite_dir: Path,
    output_dir: Path,
    verbose: bool = True
) -> Tuple[int, int, List[Tuple[str, str]]]:
    """
    Copy all SCF tests with benchmarks from test-suite to output directory.
    
    Args:
        test_suite_dir: Path to QE test-suite directory
        output_dir: Output directory (will create pw_scf_all subdirectory)
        verbose: Print progress messages
        
    Returns:
        Tuple of (copied_count, skipped_count, copied_files_list)
    """
    pw_scf_all_dir = output_dir / "pw_scf_all"
    pw_scf_all_dir.mkdir(parents=True, exist_ok=True)
    
    copied_count = 0
    skipped_count = 0
    copied_files: List[Tuple[str, str]] = []
    
    if verbose:
        print(f"Scanning test-suite: {test_suite_dir}")
        print(f"Output directory: {pw_scf_all_dir}\n")
    
    # Iterate through all directories in test-suite
    for category_dir in sorted(test_suite_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        
        category_name = category_dir.name
        if verbose:
            print(f"Scanning category: {category_name}")
        
        # Find all .in files (excluding those with "benchmark" in name)
        input_files = [
            f for f in category_dir.glob("*.in")
            if "benchmark" not in f.name.lower()
        ]
        
        if not input_files:
            continue
        
        category_scf_count = 0
        for input_file in sorted(input_files):
            # Check if it's an SCF calculation
            if not is_scf_calculation(input_file):
                continue
            
            # Find corresponding benchmark file
            benchmark_file = find_benchmark_file(category_dir, input_file.name)
            if not benchmark_file:
                skipped_count += 1
                if verbose:
                    print(f"  ⏭️  Skipped {input_file.name} (no benchmark found)")
                continue
            
            # Copy input file
            dest_input = pw_scf_all_dir / input_file.name
            shutil.copy2(input_file, dest_input)
            
            # Copy benchmark file
            dest_benchmark = pw_scf_all_dir / benchmark_file.name
            shutil.copy2(benchmark_file, dest_benchmark)
            
            copied_count += 1
            category_scf_count += 1
            copied_files.append((category_name, input_file.name))
            
            if verbose:
                print(f"  ✓ Copied {input_file.name} + {benchmark_file.name}")
        
        if verbose and category_scf_count > 0:
            print(f"  → Found {category_scf_count} SCF test(s) in {category_name}\n")
    
    return copied_count, skipped_count, copied_files


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
        default=project_root / "extended-tests" / "suites",
        help="Output directory (default: extended-tests/suites)",
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

    # Copy files
    copied_count, skipped_count, copied_files = copy_all_scf_tests(
        test_suite_dir,
        args.output,
        verbose=not args.quiet,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Copied: {copied_count} SCF tests (with benchmarks)")
    print(f"Skipped: {skipped_count} SCF tests (no benchmark found)")
    print(f"Output: {args.output / 'pw_scf_all'}")
    
    if copied_files and not args.quiet:
        print(f"\nCopied files:")
        for category, filename in sorted(copied_files):
            print(f"  - {category}/{filename}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

