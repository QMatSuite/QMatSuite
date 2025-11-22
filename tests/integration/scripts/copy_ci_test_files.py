#!/usr/bin/env python3
"""
Copy CI quick test files from QE test-suite to tests directory.

This script:
1. Reads selected tests from pw_test_stats.json
2. Copies input files from test-suite
3. Copies benchmark/reference files if available
4. Creates a self-contained test directory structure
"""

import sys
import json
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))


def find_test_suite_dir():
    """Find QE test-suite directory."""
    import os
    
    # Try environment variable
    qe_bin = os.environ.get("QE_BIN_DIR")
    if qe_bin:
        qe_bin = Path(qe_bin)
    else:
        qe_bin = Path.home() / "src" / "q-e-qe-7.5" / "bin"
    
    if not qe_bin.exists():
        return None
    
    if qe_bin.is_dir():
        qe_root = qe_bin.parent
    else:
        qe_root = qe_bin.parent.parent
    
    test_suite = qe_root / "test-suite"
    if test_suite.exists():
        return test_suite
    
    return None


def copy_test_files(test_suite_dir: Path, output_dir: Path):
    """Copy selected test files from test-suite to output directory."""
    # Load selected tests
    stats_file = project_root / "extended-tests" / "pw_test_stats.json"
    if not stats_file.exists():
        print(f"Error: Stats file not found: {stats_file}")
        return False
    
    with open(stats_file) as f:
        data = json.load(f)
    
    selected = data.get("selected_ci_tests", [])
    if not selected:
        print("Error: No selected tests found in stats file")
        return False
    
    print(f"Copying {len(selected)} test files...")
    print()
    
    copied_files = []
    missing_files = []
    
    for i, test in enumerate(selected, 1):
        category = test["category"]
        test_file = test["test_file"]
        
        # Source paths
        category_dir = test_suite_dir / category
        input_file = category_dir / test_file
        
        # Destination paths
        dest_category_dir = output_dir / category
        dest_category_dir.mkdir(parents=True, exist_ok=True)
        dest_input_file = dest_category_dir / test_file
        
        # Copy input file
        if input_file.exists():
            shutil.copy2(input_file, dest_input_file)
            copied_files.append((category, test_file))
            print(f"  {i:2d}. ✅ {category}/{test_file}")
        else:
            missing_files.append((category, test_file))
            print(f"  {i:2d}. ❌ {category}/{test_file} (not found)")
        
        # Try to copy benchmark file if it exists
        # Benchmark files have format: benchmark.out.git.inp={input_file}
        benchmark_pattern = f"benchmark.out.git.inp={test_file}"
        benchmark_file = category_dir / benchmark_pattern
        
        if benchmark_file.exists():
            dest_benchmark = dest_category_dir / benchmark_pattern
            shutil.copy2(benchmark_file, dest_benchmark)
            print(f"      ✅ Benchmark: {benchmark_pattern}")
        
        # Also check for any .save directories or other related files
        # (These might be needed for workflow tests)
        for related_file in category_dir.glob(f"{test_file}*"):
            if related_file.is_file() and related_file.name != test_file:
                dest_related = dest_category_dir / related_file.name
                if not dest_related.exists():
                    shutil.copy2(related_file, dest_related)
                    print(f"      ✅ Related: {related_file.name}")
    
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Copied: {len(copied_files)} files")
    if missing_files:
        print(f"Missing: {len(missing_files)} files")
        for category, test_file in missing_files:
            print(f"  - {category}/{test_file}")
    
    # Create a manifest file
    manifest = {
        "source": str(test_suite_dir),
        "tests": [
            {
                "category": cat,
                "test_file": tf,
                "input_file": f"{cat}/{tf}"
            }
            for cat, tf in copied_files
        ],
        "total": len(copied_files)
    }
    
    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\nManifest saved to: {manifest_file}")
    
    return len(missing_files) == 0


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Copy CI quick test files from QE test-suite"
    )
    parser.add_argument(
        "--test-suite-dir",
        type=Path,
        default=None,
        help="Path to QE test-suite directory (auto-detected if not provided)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "tests" / "integration" / "ci_test_data",
        help="Output directory for test files"
    )
    
    args = parser.parse_args()
    
    # Find test-suite directory
    if args.test_suite_dir:
        test_suite_dir = args.test_suite_dir
    else:
        test_suite_dir = find_test_suite_dir()
    
    if not test_suite_dir or not test_suite_dir.exists():
        print("Error: QE test-suite directory not found")
        print("Please provide --test-suite-dir or set QE_BIN_DIR environment variable")
        sys.exit(1)
    
    print("=" * 60)
    print("Copy CI Quick Test Files")
    print("=" * 60)
    print(f"Source: {test_suite_dir}")
    print(f"Destination: {args.output_dir}")
    print()
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy files
    success = copy_test_files(test_suite_dir, args.output_dir)
    
    if success:
        print("\n✅ All files copied successfully")
        sys.exit(0)
    else:
        print("\n⚠️  Some files were missing (see above)")
        sys.exit(1)


if __name__ == "__main__":
    main()

