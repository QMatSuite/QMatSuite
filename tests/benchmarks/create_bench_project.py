#!/usr/bin/env python3
"""
Create a 50-calculation benchmark project.

Cycles through all available demo projects, loading each as a calculation
into a single project until 50 calculations are reached.

Usage:
    python -m tests.benchmarks.create_bench_project [--output-dir PATH]

Output:
    Prints the project root path on the last line.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def create_bench_project(output_dir: Path | None = None) -> Path:
    """
    Create a benchmark project with 50 calculations.

    Args:
        output_dir: Directory to create the project in.
                    If None, a temporary directory is created.

    Returns:
        Path to the project root.
    """
    from qmatsuite.api import QMSService

    target_count = 50

    # ── 1. Determine output directory ─────────────────────────────
    if output_dir is None:
        tmp = tempfile.mkdtemp(prefix="qms_bench_")
        project_root = Path(tmp) / "bench_project"
    else:
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        project_root = output_dir

    # ── 2. Initialize project ─────────────────────────────────────
    project_root.mkdir(parents=True, exist_ok=True)
    QMSService.init_project(project_root, name="benchmark-50calc")

    svc = QMSService(project_root)

    # ── 3. Discover available demos ───────────────────────────────
    demos = QMSService.list_demo_projects()
    if not demos:
        print("ERROR: No demo projects found.", file=sys.stderr)
        sys.exit(1)

    demo_ids = [d["ulid"] for d in demos]
    print(f"Found {len(demo_ids)} demo project(s): {demo_ids}")

    # ── 4. Load demos in a cycle until we reach 50 ────────────────
    loaded_ulids: list[str] = []
    idx = 0

    while len(loaded_ulids) < target_count:
        demo_id = demo_ids[idx % len(demo_ids)]
        cycle_num = idx // len(demo_ids) + 1
        try:
            result = svc.load_demo_as_calculation(demo_id=demo_id)
            calc_ulid = result["calc_ulid"]
            loaded_ulids.append(calc_ulid)
            print(
                f"  [{len(loaded_ulids):3d}/{target_count}] "
                f"Loaded demo '{demo_id}' (cycle {cycle_num}) -> {calc_ulid}"
            )
        except Exception as exc:
            print(
                f"  [SKIP] Demo '{demo_id}' (cycle {cycle_num}): {exc}",
                file=sys.stderr,
            )
        idx += 1

        # Safety valve: stop if we cycled way too many times
        if idx > target_count * 3:
            print(
                f"WARNING: Stopping after {idx} attempts "
                f"(only {len(loaded_ulids)} loaded).",
                file=sys.stderr,
            )
            break

    # ── 5. Verify ─────────────────────────────────────────────────
    unique_ulids = set(loaded_ulids)
    print(f"\nLoaded {len(loaded_ulids)} calculation(s), {len(unique_ulids)} unique ULID(s).")

    # Verify directories exist
    calcs_dir = project_root / "calculations"
    existing_dirs = [d for d in calcs_dir.iterdir() if d.is_dir()] if calcs_dir.exists() else []
    print(f"Calculation directories on disk: {len(existing_dirs)}")

    # Verify via API list
    calc_list = svc.calculation.list(detail=False)
    print(f"Calculations via svc.calculation.list(): {len(calc_list)}")

    assert len(unique_ulids) == target_count, (
        f"Expected {target_count} unique ULIDs, got {len(unique_ulids)}"
    )
    assert len(existing_dirs) >= target_count, (
        f"Expected >= {target_count} calculation dirs, got {len(existing_dirs)}"
    )
    assert len(calc_list) == target_count, (
        f"Expected {target_count} from list(), got {len(calc_list)}"
    )

    print(f"\nBenchmark project ready at: {project_root}")
    return project_root


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a 50-calculation benchmark project for QMatSuite."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to create the project in. Default: auto-created temp dir.",
    )
    args = parser.parse_args()

    project_root = create_bench_project(output_dir=args.output_dir)

    # Final line: machine-parseable project root
    print(project_root)


if __name__ == "__main__":
    main()
