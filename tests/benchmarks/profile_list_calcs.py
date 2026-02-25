#!/usr/bin/env python3
"""
Profile list_calculations(detail=False) to understand the 43-second bottleneck.

This script instruments the call path to measure where time is spent:
1. cProfile top-20 cumulative time
2. Manual timing of each sub-operation
3. I/O operation counting (file reads, directory scans)
4. Scaling test (1, 5, 10, 25, 50 calcs)
5. Per-call build_resource_index counting

Usage:
    python tests/benchmarks/profile_list_calcs.py --project-root /path/to/bench_project

Output:
    Writes results to tests/benchmarks/results/profile_list_calcs.json
    Prints human-readable analysis to stdout
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from typing import Any

# ── Add project root to sys.path ──
project_src = Path(__file__).resolve().parent.parent.parent / "src"
sys.path.insert(0, str(project_src))


class IOCounter:
    """Count and time I/O operations by monkey-patching."""

    def __init__(self):
        self.file_reads = 0
        self.file_read_time = 0.0
        self.file_read_sizes = []
        self.yaml_loads = 0
        self.yaml_load_time = 0.0
        self.dir_scans = 0
        self.dir_scan_time = 0.0
        self.dir_scan_counts = []  # number of entries per scan
        self.glob_calls = 0
        self.glob_time = 0.0
        self._patches = []

    def start(self):
        """Start counting I/O operations."""
        import pathlib

        original_read_text = pathlib.Path.read_text
        original_iterdir = pathlib.Path.iterdir
        original_glob = pathlib.Path.glob

        counter = self

        def counting_read_text(self_path, *args, **kwargs):
            t0 = time.perf_counter()
            result = original_read_text(self_path, *args, **kwargs)
            counter.file_read_time += time.perf_counter() - t0
            counter.file_reads += 1
            counter.file_read_sizes.append(len(result))
            return result

        def counting_iterdir(self_path):
            t0 = time.perf_counter()
            result = list(original_iterdir(self_path))
            counter.dir_scan_time += time.perf_counter() - t0
            counter.dir_scans += 1
            counter.dir_scan_counts.append(len(result))
            return iter(result)

        def counting_glob(self_path, pattern, *args, **kwargs):
            t0 = time.perf_counter()
            result = list(original_glob(self_path, pattern, *args, **kwargs))
            counter.glob_time += time.perf_counter() - t0
            counter.glob_calls += 1
            return iter(result)

        p1 = patch.object(pathlib.Path, "read_text", counting_read_text)
        p2 = patch.object(pathlib.Path, "iterdir", counting_iterdir)
        p3 = patch.object(pathlib.Path, "glob", counting_glob)
        self._patches = [p1, p2, p3]
        for p in self._patches:
            p.start()

    def stop(self):
        for p in self._patches:
            p.stop()
        self._patches = []

    def summary(self) -> dict:
        return {
            "file_reads": self.file_reads,
            "file_read_time_s": round(self.file_read_time, 4),
            "total_bytes_read": sum(self.file_read_sizes),
            "avg_file_size": round(sum(self.file_read_sizes) / max(self.file_reads, 1), 0),
            "dir_scans": self.dir_scans,
            "dir_scan_time_s": round(self.dir_scan_time, 4),
            "total_dir_entries": sum(self.dir_scan_counts),
            "glob_calls": self.glob_calls,
            "glob_time_s": round(self.glob_time, 4),
        }


class BuildResourceIndexCounter:
    """Count calls to build_resource_index and measure total time."""

    def __init__(self):
        self.call_count = 0
        self.total_time = 0.0
        self.call_sites: list[str] = []
        self._original = None
        self._patch = None

    def start(self):
        import qmatsuite.core.resolution as res_mod
        self._original = res_mod.build_resource_index

        counter = self
        original = self._original

        import traceback

        def counting_build(project_root, *args, **kwargs):
            t0 = time.perf_counter()
            result = original(project_root, *args, **kwargs)
            counter.total_time += time.perf_counter() - t0
            counter.call_count += 1
            # Capture call site (skip this wrapper frame)
            stack = traceback.extract_stack(limit=4)
            caller = f"{stack[-2].filename}:{stack[-2].lineno} in {stack[-2].name}" if len(stack) >= 2 else "unknown"
            counter.call_sites.append(caller)
            return result

        self._patch = patch.object(res_mod, "build_resource_index", counting_build)
        self._patch.start()

    def stop(self):
        if self._patch:
            self._patch.stop()
            self._patch = None

    def summary(self) -> dict:
        # Deduplicate call sites and count occurrences
        site_counts: dict[str, int] = {}
        for site in self.call_sites:
            # Strip project path prefix for readability
            short = site.split("/src/")[-1] if "/src/" in site else site
            site_counts[short] = site_counts.get(short, 0) + 1

        return {
            "call_count": self.call_count,
            "total_time_s": round(self.total_time, 4),
            "avg_time_s": round(self.total_time / max(self.call_count, 1), 4),
            "call_sites": site_counts,
        }


def run_cprofile(project_root: Path) -> str:
    """Run cProfile on list(detail=False) and return top-30 results."""
    from qmatsuite.api import QMSService
    svc = QMSService(project_root)

    profiler = cProfile.Profile()
    profiler.enable()
    result = svc.calculation.list(detail=False)
    profiler.disable()

    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    ps.print_stats(30)
    return s.getvalue()


def time_sub_operations(project_root: Path) -> dict:
    """Time individual sub-operations in the list path."""
    results = {}

    # 1. Time list_calculations (resolution layer)
    from qmatsuite.core.resolution import list_calculations
    t0 = time.perf_counter()
    calc_list = list_calculations(project_root)
    results["list_calculations_resolution"] = {
        "time_s": round(time.perf_counter() - t0, 4),
        "count": len(calc_list),
    }

    # 2. Time Project.open()
    from qmatsuite.project.model import Project
    t0 = time.perf_counter()
    project = Project.open(project_root)
    results["project_open"] = {
        "time_s": round(time.perf_counter() - t0, 4),
        "n_structures": len(project.structures),
        "n_calculations": len(project.calculations),
    }

    # 3. Time load_calculation per calc
    from qmatsuite.core.models import load_calculation
    load_times = []
    for calc_resolved in calc_list[:5]:  # Sample first 5
        calc_dir = calc_resolved.absolute_path
        if calc_dir.name == "calculation.yaml":
            calc_dir = calc_dir.parent
        calc_yaml = calc_dir / "calculation.yaml"
        t0 = time.perf_counter()
        try:
            load_calculation(calc_yaml, project_root)
        except Exception:
            pass
        load_times.append(time.perf_counter() - t0)

    results["load_calculation_per_calc"] = {
        "sample_size": len(load_times),
        "times_s": [round(t, 4) for t in load_times],
        "avg_s": round(sum(load_times) / max(len(load_times), 1), 4),
        "projected_50_s": round(sum(load_times) / max(len(load_times), 1) * 50, 4),
    }

    # 4. Time Calculation.from_yaml per calc (materialize_steps=False)
    from qmatsuite.calculation.calculation import Calculation
    from_yaml_times = []
    for calc_resolved in calc_list[:5]:
        calc_dir = calc_resolved.absolute_path
        if calc_dir.name == "calculation.yaml":
            calc_dir = calc_dir.parent
        t0 = time.perf_counter()
        try:
            Calculation.from_yaml(calc_dir, project, materialize_steps=False)
        except Exception:
            pass
        from_yaml_times.append(time.perf_counter() - t0)

    results["calculation_from_yaml_per_calc"] = {
        "sample_size": len(from_yaml_times),
        "times_s": [round(t, 4) for t in from_yaml_times],
        "avg_s": round(sum(from_yaml_times) / max(len(from_yaml_times), 1), 4),
        "projected_50_s": round(sum(from_yaml_times) / max(len(from_yaml_times), 1) * 50, 4),
    }

    # 5. Time build_resource_index standalone
    from qmatsuite.core.resolution import build_resource_index
    bri_times = []
    for _ in range(3):
        t0 = time.perf_counter()
        build_resource_index(project_root)
        bri_times.append(time.perf_counter() - t0)

    results["build_resource_index_standalone"] = {
        "times_s": [round(t, 4) for t in bri_times],
        "median_s": round(sorted(bri_times)[1], 4),
    }

    # 6. Time _load_config (project.qms.yml)
    from qmatsuite.core.resolution import _load_config
    t0 = time.perf_counter()
    config = _load_config(project_root)
    results["load_config"] = {
        "time_s": round(time.perf_counter() - t0, 4),
        "n_calc_entries": len(config.get("calculations", [])),
        "n_struct_entries": len(config.get("structures", [])),
    }

    # 7. Time _calculation_to_resolved per entry
    from qmatsuite.core.resolution import _calculation_to_resolved
    ctr_times = []
    for entry in config.get("calculations", [])[:5]:
        t0 = time.perf_counter()
        try:
            _calculation_to_resolved(project_root, entry)
        except Exception:
            pass
        ctr_times.append(time.perf_counter() - t0)

    results["calculation_to_resolved_per_entry"] = {
        "sample_size": len(ctr_times),
        "times_s": [round(t, 4) for t in ctr_times],
        "avg_s": round(sum(ctr_times) / max(len(ctr_times), 1), 4),
        "projected_50_s": round(sum(ctr_times) / max(len(ctr_times), 1) * 50, 4),
    }

    # 8. Time calculation_to_dto
    from qmatsuite.api._mapping.dto_mapping import calculation_to_dto
    dto_times = []
    for calc_resolved in calc_list[:5]:
        calc_dir = calc_resolved.absolute_path
        if calc_dir.name == "calculation.yaml":
            calc_dir = calc_dir.parent
        calc_yaml = calc_dir / "calculation.yaml"
        try:
            calc_model = load_calculation(calc_yaml, project_root)
            calc_obj = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
            t0 = time.perf_counter()
            calculation_to_dto(calc_resolved, calc_model, calc_obj)
            dto_times.append(time.perf_counter() - t0)
        except Exception:
            pass

    results["calculation_to_dto_per_calc"] = {
        "sample_size": len(dto_times),
        "times_s": [round(t, 6) for t in dto_times],
        "avg_s": round(sum(dto_times) / max(len(dto_times), 1), 6),
    }

    # 9. Time ensure_calculation_identity
    from qmatsuite.core.calc_identity import ensure_calculation_identity
    eci_times = []
    for calc_resolved in calc_list[:5]:
        calc_dir = calc_resolved.absolute_path
        if calc_dir.name == "calculation.yaml":
            calc_dir = calc_dir.parent
        t0 = time.perf_counter()
        ensure_calculation_identity(calc_dir, project_root=project_root)
        eci_times.append(time.perf_counter() - t0)

    results["ensure_calc_identity_per_calc"] = {
        "sample_size": len(eci_times),
        "times_s": [round(t, 6) for t in eci_times],
        "avg_s": round(sum(eci_times) / max(len(eci_times), 1), 6),
    }

    return results


def run_scaling_test(project_root: Path) -> dict:
    """Test how list time scales with number of calculations."""
    from qmatsuite.api import QMSService
    from qmatsuite.core.resolution import list_calculations, _load_config

    config = _load_config(project_root)
    all_entries = config.get("calculations", [])
    total = len(all_entries)

    # For scaling, we test the full svc.calculation.list(detail=False) path
    # We can't easily limit the number of calcs without modifying the project,
    # so we'll time the full-project call and also time sub-operations at different scales

    # Test list_calculations resolution at different scales (by limiting config entries)
    scaling_results = {}
    for n in [1, 5, 10, 25, min(50, total)]:
        # Time _calculation_to_resolved for n entries
        from qmatsuite.core.resolution import _calculation_to_resolved
        entries = all_entries[:n]
        t0 = time.perf_counter()
        for entry in entries:
            try:
                _calculation_to_resolved(project_root, entry)
            except Exception:
                pass
        elapsed = time.perf_counter() - t0
        scaling_results[f"calc_to_resolved_{n}"] = round(elapsed, 4)

    # Also measure load_calculation + from_yaml scaling
    calc_list = list_calculations(project_root)
    from qmatsuite.project.model import Project
    from qmatsuite.core.models import load_calculation
    from qmatsuite.calculation.calculation import Calculation
    project = Project.open(project_root)

    for n in [1, 5, 10, 25, min(50, total)]:
        subset = calc_list[:n]
        t0 = time.perf_counter()
        for calc_resolved in subset:
            calc_dir = calc_resolved.absolute_path
            if calc_dir.name == "calculation.yaml":
                calc_dir = calc_dir.parent
            calc_yaml = calc_dir / "calculation.yaml"
            try:
                load_calculation(calc_yaml, project_root)
                Calculation.from_yaml(calc_dir, project, materialize_steps=False)
            except Exception:
                pass
        elapsed = time.perf_counter() - t0
        scaling_results[f"load_and_from_yaml_{n}"] = round(elapsed, 4)

    return scaling_results


def run_full_list_with_io_counting(project_root: Path) -> dict:
    """Run the full svc.calculation.list(detail=False) with I/O counting."""
    from qmatsuite.api import QMSService

    io_counter = IOCounter()
    bri_counter = BuildResourceIndexCounter()

    io_counter.start()
    bri_counter.start()

    t0 = time.perf_counter()
    svc = QMSService(project_root)
    result = svc.calculation.list(detail=False)
    total_time = time.perf_counter() - t0

    bri_counter.stop()
    io_counter.stop()

    return {
        "total_time_s": round(total_time, 4),
        "n_results": len(result),
        "io": io_counter.summary(),
        "build_resource_index": bri_counter.summary(),
    }


def main():
    parser = argparse.ArgumentParser(description="Profile list_calculations performance")
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="Path to benchmark project (created by create_bench_project.py)",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    if not (project_root / "project.qms.yml").exists():
        print(f"ERROR: No project.qms.yml at {project_root}", file=sys.stderr)
        sys.exit(1)

    print(f"Profiling list_calculations on: {project_root}")
    print(f"{'=' * 70}")

    results: dict[str, Any] = {
        "project_root": str(project_root),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    # ── Phase 1: cProfile ──
    print("\n1. cProfile top-30 (cumulative time)...")
    cprofile_output = run_cprofile(project_root)
    results["cprofile_top30"] = cprofile_output
    print(cprofile_output)

    # ── Phase 2: Sub-operation timing ──
    print("\n2. Sub-operation timing...")
    sub_ops = time_sub_operations(project_root)
    results["sub_operations"] = sub_ops
    for name, data in sub_ops.items():
        print(f"  {name}: {json.dumps(data, indent=4)}")

    # ── Phase 3: Full list with I/O counting ──
    print("\n3. Full list with I/O counting...")
    io_results = run_full_list_with_io_counting(project_root)
    results["full_list_with_io"] = io_results
    print(f"  Total time: {io_results['total_time_s']}s")
    print(f"  Results: {io_results['n_results']}")
    print(f"  I/O: {json.dumps(io_results['io'], indent=4)}")
    print(f"  build_resource_index: {json.dumps(io_results['build_resource_index'], indent=4)}")

    # ── Phase 4: Scaling test ──
    print("\n4. Scaling test...")
    scaling = run_scaling_test(project_root)
    results["scaling"] = scaling
    for name, val in scaling.items():
        print(f"  {name}: {val}s")

    # ── Save results ──
    output_dir = Path(__file__).resolve().parent / "results"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "profile_list_calcs.json"

    # Can't serialize cprofile text nicely, keep it as string
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'=' * 70}")
    print(f"Results saved to: {output_file}")

    # ── Phase 5: Summary analysis ──
    print(f"\n{'=' * 70}")
    print("ANALYSIS SUMMARY")
    print(f"{'=' * 70}")

    total = io_results["total_time_s"]
    bri_count = io_results["build_resource_index"]["call_count"]
    bri_time = io_results["build_resource_index"]["total_time_s"]
    bri_avg = io_results["build_resource_index"]["avg_time_s"]

    print(f"\nTotal list(detail=False) time: {total}s")
    print(f"build_resource_index called: {bri_count} times, total: {bri_time}s ({bri_time/total*100:.1f}%)")
    print(f"  Average per call: {bri_avg}s")
    print(f"\nI/O operations:")
    print(f"  File reads: {io_results['io']['file_reads']} ({io_results['io']['file_read_time_s']}s)")
    print(f"  Dir scans: {io_results['io']['dir_scans']} ({io_results['io']['dir_scan_time_s']}s)")
    print(f"  Glob calls: {io_results['io']['glob_calls']} ({io_results['io']['glob_time_s']}s)")

    print(f"\nbuild_resource_index call sites:")
    for site, count in io_results["build_resource_index"]["call_sites"].items():
        print(f"  {count}x  {site}")

    # Scaling analysis
    print(f"\nScaling analysis (calc_to_resolved):")
    for key in sorted(k for k in scaling if k.startswith("calc_to_resolved")):
        n = int(key.split("_")[-1])
        t = scaling[key]
        per = t / n if n > 0 else 0
        print(f"  n={n:3d}: {t:.4f}s  ({per:.4f}s/calc)")

    print(f"\nScaling analysis (load + from_yaml):")
    for key in sorted(k for k in scaling if k.startswith("load_and_from_yaml")):
        n = int(key.split("_")[-1])
        t = scaling[key]
        per = t / n if n > 0 else 0
        print(f"  n={n:3d}: {t:.4f}s  ({per:.4f}s/calc)")


if __name__ == "__main__":
    main()
