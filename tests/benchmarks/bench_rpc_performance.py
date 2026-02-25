#!/usr/bin/env python3
"""
Benchmark runner for QMatSuite RPC / API performance.

Measures six operations against a 50-calculation project and writes
results to JSON + human-readable stdout.

Usage:
    python -m tests.benchmarks.bench_rpc_performance \
        --label before --project-root /path/to/bench_project

Output:
    - JSON: tests/benchmarks/results/{label}.json
    - Human-readable: stdout
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


RESULTS_DIR = Path(__file__).resolve().parent / "results"
N_RUNS = 3


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

def _time_call(fn, n: int = N_RUNS) -> dict:
    """
    Run *fn* n times, returning timing statistics.

    Returns:
        Dict with keys: median_s, all_s, n_runs
    """
    timings: list[float] = []
    result = None
    for _ in range(n):
        t0 = time.perf_counter()
        result = fn()
        t1 = time.perf_counter()
        timings.append(t1 - t0)
    return {
        "median_s": round(statistics.median(timings), 6),
        "all_s": [round(t, 6) for t in timings],
        "n_runs": n,
        "last_result_repr": repr(result)[:200] if result is not None else None,
    }


# ---------------------------------------------------------------------------
# Individual benchmarks
# ---------------------------------------------------------------------------

def bench_import_time() -> dict:
    """
    Benchmark 1: import time for ``from qmatsuite.api import QMSService``.

    Uses a subprocess so each iteration pays the real cold-import cost.
    """
    snippet = "from qmatsuite.api import QMSService"
    timings: list[float] = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-c", snippet],
            capture_output=True,
            text=True,
        )
        t1 = time.perf_counter()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Import failed: {proc.stderr.strip()}"
            )
        timings.append(t1 - t0)

    return {
        "median_s": round(statistics.median(timings), 6),
        "all_s": [round(t, 6) for t in timings],
        "n_runs": N_RUNS,
        "last_result_repr": None,
    }


def bench_list_no_detail(svc) -> dict:
    """Benchmark 2: svc.calculation.list(detail=False) on 50-calc project."""
    return _time_call(lambda: svc.calculation.list(detail=False))


def bench_list_with_detail(svc) -> dict:
    """Benchmark 3: svc.calculation.list(detail=True) on 50-calc project (primary target)."""
    return _time_call(lambda: svc.calculation.list(detail=True))


def bench_get_detail_single(svc, calc_ulid: str) -> dict:
    """Benchmark 4: svc.calculation.get_detail(calc_ulid) on a single calc."""
    return _time_call(lambda: svc.calculation.get_detail(calc_ulid))


def bench_build_resource_index(project_root: Path) -> dict:
    """Benchmark 5: build_resource_index(project_root) standalone."""
    from qmatsuite.core.resolution import build_resource_index

    return _time_call(lambda: build_resource_index(project_root))


def bench_preset_compilation() -> dict:
    """Benchmark 6: compile_magnetism(COLLINEAR_LSDA) x 100."""
    from qmatsuite.presets.compiler import compile_magnetism
    from qmatsuite.presets.dimensions import MagnetismOption

    def _run_100():
        # Clear lru_cache so each batch re-compiles
        compile_magnetism.cache_clear()
        results = []
        for _ in range(100):
            compile_magnetism.cache_clear()
            results.append(compile_magnetism(MagnetismOption.COLLINEAR_LSDA))
        return results[-1]

    return _time_call(_run_100)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_benchmarks(label: str, project_root: Path) -> dict:
    """
    Run all benchmarks and return a results dict.

    Args:
        label: Label for this run (e.g. "before", "after").
        project_root: Path to the benchmark project.

    Returns:
        Dict with benchmark results keyed by name.
    """
    from qmatsuite.api import QMSService

    svc = QMSService(project_root)

    # Grab a calc ULID for single-calc benchmarks
    calc_list = svc.calculation.list(detail=False)
    if not calc_list:
        raise RuntimeError("No calculations found in project. Run create_bench_project.py first.")
    first_calc_ulid = calc_list[0].calc_ulid

    print(f"=== QMatSuite RPC Performance Benchmark (label={label}) ===")
    print(f"Project: {project_root}")
    print(f"Calculations: {len(calc_list)}")
    print(f"Runs per benchmark: {N_RUNS}")
    print()

    results: dict = {
        "label": label,
        "project_root": str(project_root),
        "n_calculations": len(calc_list),
        "n_runs_per_benchmark": N_RUNS,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "benchmarks": {},
    }

    benchmarks = [
        ("1_import_time", "Import time (from qmatsuite.api import QMSService)", bench_import_time),
        ("2_list_no_detail", "calculation.list(detail=False)", lambda: bench_list_no_detail(svc)),
        ("3_list_with_detail", "calculation.list(detail=True) [primary]", lambda: bench_list_with_detail(svc)),
        ("4_get_detail_single", f"calculation.get_detail({first_calc_ulid[:8]}...)", lambda: bench_get_detail_single(svc, first_calc_ulid)),
        ("5_build_resource_index", "build_resource_index(project_root)", lambda: bench_build_resource_index(project_root)),
        ("6_preset_compilation_100x", "compile_magnetism(COLLINEAR_LSDA) x100", bench_preset_compilation),
    ]

    for key, description, fn in benchmarks:
        print(f"  Running: {description} ...", end="", flush=True)
        try:
            bench_result = fn()
            # Remove verbose last_result_repr from JSON for cleanliness
            bench_result_clean = {k: v for k, v in bench_result.items() if k != "last_result_repr"}
            results["benchmarks"][key] = bench_result_clean
            median = bench_result["median_s"]
            all_times = bench_result["all_s"]
            print(f"  median={median:.4f}s  all={all_times}")
        except Exception as exc:
            results["benchmarks"][key] = {"error": str(exc)}
            print(f"  ERROR: {exc}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark QMatSuite RPC/API performance."
    )
    parser.add_argument(
        "--label",
        required=True,
        choices=["before", "after"],
        help="Label for this benchmark run.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="Path to the 50-calculation benchmark project.",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    if not (project_root / "project.qms.yml").exists():
        print(
            f"ERROR: {project_root} does not contain project.qms.yml. "
            "Run create_bench_project.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    results = run_benchmarks(label=args.label, project_root=project_root)

    # ── Write JSON ────────────────────────────────────────────────
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_file = RESULTS_DIR / f"{args.label}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults written to: {output_file}")

    # ── Human-readable summary ────────────────────────────────────
    print("\n--- Summary ---")
    print(f"{'Benchmark':<45} {'Median (s)':>12}")
    print("-" * 60)
    for key, data in results["benchmarks"].items():
        if "error" in data:
            print(f"{key:<45} {'ERROR':>12}")
        else:
            print(f"{key:<45} {data['median_s']:>12.4f}")
    print()


if __name__ == "__main__":
    main()
