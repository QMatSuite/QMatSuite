"""Copy CI quick test files from QE test-suite to tests directory.

This script is intended to be run from the project root *after* the
environment is configured. It uses only the standard library.
"""

import json
import shutil
from pathlib import Path


# Project root (no sys.path hacks needed)
project_root = Path(__file__).parent.parent.parent.parent


def find_test_suite_dir() -> Path | None:
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


def copy_test_files(test_suite_dir: Path, output_dir: Path) -> bool:
    """Copy selected test files from test-suite to output directory."""
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

    print(f"Copying {len(selected)} test files...\n")

    copied_files: list[tuple[str, str]] = []
    missing_files: list[tuple[str, str]] = []

    for test in selected:
        category = test["category"]
        test_file = test["test_file"]

        category_dir = test_suite_dir / category
        input_file = category_dir / test_file

        dest_category_dir = output_dir / category
        dest_category_dir.mkdir(parents=True, exist_ok=True)
        dest_input = dest_category_dir / test_file

        if not input_file.exists():
            print(f"  ✗ Missing: {category}/{test_file}")
            missing_files.append((category, test_file))
            continue

        shutil.copy2(input_file, dest_input)
        copied_files.append((category, test_file))
        print(f"  ✓ Copied: {category}/{test_file}")

        # Copy benchmark/reference files if available
        benchmark_pattern = (
            f"benchmark.out.git.inp={test_file}.args={test.get('args', '')}".rstrip("=")
        )
        for benchmark in category_dir.glob("benchmark.out.git.inp=*"):
            if benchmark_pattern in benchmark.name:
                dest_benchmark = dest_category_dir / benchmark.name
                shutil.copy2(benchmark, dest_benchmark)
                print(f"      ✓ Benchmark: {benchmark.name}")

        # Copy related files (e.g. .save directories)
        for related_file in category_dir.glob(f"{test_file}*"):
            if related_file.is_file() and related_file.name != test_file:
                dest_related = dest_category_dir / related_file.name
                if not dest_related.exists():
                    shutil.copy2(related_file, dest_related)
                    print(f"      ✓ Related: {related_file.name}")

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Copied: {len(copied_files)} files")
    if missing_files:
        print(f"Missing: {len(missing_files)} files")
        for category, test_file in missing_files:
            print(f"  - {category}/{test_file}")

    manifest = {
        "source": str(test_suite_dir),
        "tests": [
            {
                "category": cat,
                "test_file": tf,
                "input_file": f"{cat}/{tf}",
            }
            for cat, tf in copied_files
        ],
        "total": len(copied_files),
    }

    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest saved to: {manifest_file}")
    return not missing_files


def main() -> int:
    """Entry point for the copy script."""
    import argparse

    parser = argparse.ArgumentParser(description="Copy CI PW test files")
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "tests" / "integration" / "ci_test_data",
        help="Output directory for CI test data",
    )
    args = parser.parse_args()

    test_suite_dir = find_test_suite_dir()
    if not test_suite_dir:
        print("Error: QE test-suite directory not found. Set QE_BIN_DIR or install QE.")
        return 1

    ok = copy_test_files(test_suite_dir, args.output)
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())

{
  "cells": [],
  "metadata": {
    "language_info": {
      "name": "python"
    }
  },
  "nbformat": 4,
  "nbformat_minor": 2
}