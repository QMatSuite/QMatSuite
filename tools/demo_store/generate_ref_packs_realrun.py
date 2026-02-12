#!/usr/bin/env python3
"""
Generate reference packs from REAL daemon-level engine runs.

For every demo project, this tool:
  1. Materializes the demo via QVService.create_demo_project()
  2. Runs the calculation via QVService.run.run_calculation()
  3. Probes all analysis types via QVService.analysis.get_analysis()
  4. Serializes CanonicalPrimitiveBundle JSON to ref_packs/<slug>/

ALL 15 engines are available locally.  There is NO fallback.

Usage:
  python tools/demo_store/generate_ref_packs_realrun.py [options]

Options:
  --dry-run          Show what would run without executing
  --only=<slug>      Run only this demo slug (comma-separated for multiple)
  --skip=<slug>      Skip these demo slugs (comma-separated)
  --timeout=<sec>    Per-demo timeout in seconds (default 300)
  --keep-workdirs    Don't clean up run directories after success
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

REF_PACKS_DIR = REPO_ROOT / "resources" / "demo_projects" / "ref_packs"
WORK_DIR = REPO_ROOT / ".tmp" / "refpack_runs"
GENERATOR_VERSION = "3.0.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("refpack_gen")

# ---------------------------------------------------------------------------
# Analysis object types to probe per engine.
# Derived from each engine's ANALYSIS_CAPABILITIES in driver.py.
# The generator probes ALL listed types; missing ones are silently skipped.
# ---------------------------------------------------------------------------
ENGINE_ANALYSIS_TYPES: dict[str, list[str]] = {
    "qe": ["convergence", "bands", "dos", "trajectory"],
    "vasp": ["convergence", "bands", "dos", "trajectory"],
    "abinit": ["convergence", "bands", "dos", "trajectory"],
    "cp2k": ["convergence", "bands", "dos", "trajectory"],
    "siesta": ["convergence", "bands", "dos", "trajectory"],
    "gpaw": ["bands", "dos", "trajectory"],
    "lammps": ["trajectory"],
    "xtb": ["trajectory"],
    "orca": ["trajectory"],
    "gaussian": ["trajectory"],
    "psi4": ["trajectory"],
    "pyscf": ["trajectory"],
    "w90": ["field3d"],
    # These engines have no ANALYSIS_CAPABILITIES — run succeeds but no
    # chart-renderable analysis bundles are produced.
    "yambo": [],
    "qmcpack": [],
}


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _discover_demos() -> list[dict[str, str]]:
    """Discover all demo slugs and their engines from demo YAML files."""
    import yaml

    demo_dir = REPO_ROOT / "resources" / "demo_projects"
    demos = []
    for yml in sorted(demo_dir.glob("*.yml")):
        slug = yml.stem
        with open(yml) as f:
            data = yaml.safe_load(f)
        meta = data.get("meta", {})
        engine = meta.get("corpus_engine", "")
        demos.append({"slug": slug, "engine": engine, "path": str(yml)})
    return demos


def _write_ref_pack(
    demo_slug: str,
    engine: str,
    bundles: dict[str, dict],
) -> dict[str, Any]:
    """Write ref pack files and manifest.  Returns manifest dict."""
    pack_dir = REF_PACKS_DIR / demo_slug
    pack_dir.mkdir(parents=True, exist_ok=True)

    # Clean old files first
    for old_file in pack_dir.iterdir():
        old_file.unlink()

    object_types: dict[str, dict[str, str]] = {}
    for obj_type, bundle_dict in bundles.items():
        json_bytes = json.dumps(bundle_dict, indent=2, default=str).encode("utf-8")
        fname = f"{obj_type}.json"
        (pack_dir / fname).write_bytes(json_bytes)
        object_types[obj_type] = {
            "file": fname,
            "sha256": _compute_sha256(json_bytes),
        }

    manifest = {
        "demo_slug": demo_slug,
        "engine": engine,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": GENERATOR_VERSION,
        "source": "realrun",
        "object_types": object_types,
    }
    manifest_json = json.dumps(manifest, indent=2)
    (pack_dir / "manifest.json").write_text(manifest_json + "\n")
    return manifest


def generate_one_demo(
    slug: str,
    engine: str,
    timeout: int = 300,
    keep_workdir: bool = False,
) -> dict[str, Any]:
    """
    Run a single demo through the full pipeline and extract analysis bundles.

    Returns dict with status, types, timing, error info.
    """
    from quantumvitas.api.service import QVService

    result: dict[str, Any] = {
        "slug": slug,
        "engine": engine,
        "status": "UNKNOWN",
        "types": [],
        "elapsed_s": 0.0,
        "error": None,
    }

    work_dir = WORK_DIR / slug
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()

    try:
        # Step 1: Create demo project
        demo_result = QVService.create_demo_project(
            target_dir=work_dir,
            name=slug,
            demo_id=slug,
        )
        project_root = Path(demo_result["project_root"])

        # Step 2: Run calculation
        svc = QVService(project_root)
        calcs = svc.calculation.list()
        if not calcs:
            result["status"] = "NO_CALCULATIONS"
            result["error"] = "Demo has no calculations"
            return result

        calc_ulid = calcs[0].calc_ulid
        log.info("  Running %s (engine=%s, calc=%s)...", slug, engine, calc_ulid)

        run_dto = svc.run.run_calculation(
            calc_selector=calc_ulid,
            run_mode="full",
        )

        run_status = run_dto.status
        if run_status not in ("completed", "success"):
            result["status"] = f"RUN_FAILED:{run_status}"
            result["error"] = f"Run status: {run_status}"
            # Log step details
            for step in run_dto.steps:
                step_status = getattr(step, "status", None)
                if step_status and step_status not in ("completed", "success"):
                    log.warning(
                        "    Step %s: %s — %s",
                        getattr(step, "step_type_spec", "?"),
                        step_status,
                        getattr(step, "message", ""),
                    )
            return result

        # Step 3: Probe analysis types
        run_ulid = run_dto.run_ulid
        analysis_types = ENGINE_ANALYSIS_TYPES.get(engine, [])
        bundles: dict[str, dict] = {}

        for obj_type in analysis_types:
            try:
                analysis = svc.analysis.get_analysis(run_ulid, obj_type)
                bundle_dict = analysis["bundle"]
                bundles[obj_type] = bundle_dict
                log.info("    ✓ %s", obj_type)
            except Exception as exc:
                # Not all analysis types available for every demo
                log.info("    ✗ %s: %s", obj_type, exc)

        if not bundles:
            result["status"] = "NO_ANALYSIS"
            result["error"] = f"No analysis bundles produced (probed: {analysis_types})"
            return result

        # Step 4: Write ref pack
        _write_ref_pack(slug, engine, bundles)

        result["status"] = "OK"
        result["types"] = sorted(bundles.keys())

    except Exception as exc:
        import traceback
        result["status"] = "ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"
        log.error("  FAILED %s: %s", slug, exc)
        log.error("  Traceback:\n%s", traceback.format_exc())

    finally:
        result["elapsed_s"] = round(time.monotonic() - t0, 1)
        # Clean up workdir unless --keep-workdirs
        if not keep_workdir and work_dir.exists():
            try:
                shutil.rmtree(work_dir)
            except Exception:
                pass

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate ref packs from real engine runs")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without running")
    parser.add_argument("--only", type=str, default="", help="Comma-separated demo slugs to run")
    parser.add_argument("--skip", type=str, default="", help="Comma-separated demo slugs to skip")
    parser.add_argument("--timeout", type=int, default=300, help="Per-demo timeout (seconds)")
    parser.add_argument("--keep-workdirs", action="store_true", help="Keep run directories")
    args = parser.parse_args()

    only_set = set(args.only.split(",")) if args.only else set()
    skip_set = set(args.skip.split(",")) if args.skip else set()

    demos = _discover_demos()
    log.info("Discovered %d demos", len(demos))
    log.info("Ref packs dir: %s", REF_PACKS_DIR)
    log.info("Work dir: %s", WORK_DIR)

    # Filter
    if only_set:
        demos = [d for d in demos if d["slug"] in only_set]
    if skip_set:
        demos = [d for d in demos if d["slug"] not in skip_set]

    log.info("Will process %d demos", len(demos))

    if args.dry_run:
        for d in demos:
            types = ENGINE_ANALYSIS_TYPES.get(d["engine"], [])
            print(f"  {d['slug']:40s} engine={d['engine']:10s} probe={types}")
        return True

    # Ensure output dirs exist
    REF_PACKS_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    ok_count = 0
    fail_count = 0
    no_analysis_count = 0

    for i, demo in enumerate(demos, 1):
        slug = demo["slug"]
        engine = demo["engine"]
        log.info("[%d/%d] %s (%s)", i, len(demos), slug, engine)

        r = generate_one_demo(
            slug=slug,
            engine=engine,
            timeout=args.timeout,
            keep_workdir=args.keep_workdirs,
        )
        results.append(r)

        if r["status"] == "OK":
            ok_count += 1
            log.info("  OK: %s (%.1fs)", ", ".join(r["types"]), r["elapsed_s"])
        elif r["status"] == "NO_ANALYSIS":
            no_analysis_count += 1
            log.info("  NO_ANALYSIS: %s (%.1fs)", r["error"], r["elapsed_s"])
        else:
            fail_count += 1
            log.error("  FAIL: %s — %s (%.1fs)", r["status"], r["error"], r["elapsed_s"])

    # Remove stale ref packs (directories not in demo list)
    demo_slugs = {d["slug"] for d in demos}
    if REF_PACKS_DIR.exists():
        for existing in REF_PACKS_DIR.iterdir():
            if existing.is_dir() and existing.name not in demo_slugs:
                manifest_path = existing / "manifest.json"
                if manifest_path.exists():
                    if existing.name not in {d["slug"] for d in _discover_demos()}:
                        log.info("Removing stale ref pack: %s", existing.name)
                        shutil.rmtree(existing)

    # Summary
    print("\n" + "=" * 70)
    print(f"RESULTS: {ok_count} OK, {no_analysis_count} no-analysis, {fail_count} FAILED")
    print(f"Total ref packs: {ok_count}")
    print("=" * 70)

    # Detailed report
    print(f"\n{'Slug':40s} {'Engine':10s} {'Status':20s} {'Types':30s} {'Time':>8s}")
    print("-" * 110)
    for r in results:
        types_str = ", ".join(r["types"]) if r["types"] else r.get("error", "—")[:30]
        flag = " ⚠ >10min" if r["elapsed_s"] > 600 else ""
        print(f"{r['slug']:40s} {r['engine']:10s} {r['status']:20s} {types_str:30s} {r['elapsed_s']:>7.1f}s{flag}")

    # Flag demos exceeding 10-minute threshold (Rule CS6)
    slow_demos = [r for r in results if r["elapsed_s"] > 600]
    if slow_demos:
        print(f"\n{'⚠ DROPOUT CANDIDATES (>10 min):':=^70}")
        for r in slow_demos:
            print(f"  {r['slug']:40s} {r['elapsed_s']/60:.1f} min  ({r['status']})")
        print("  NOTE: These demos are flagged for review only. Human decision required to drop.")

    # Write machine-readable results matrix JSON (Rule CS6)
    _write_results_matrix(results)

    return fail_count == 0


RESULTS_MATRIX_PATH = REPO_ROOT / ".tmp" / "refpack_results_matrix.json"


def _write_results_matrix(results: list[dict[str, Any]]) -> None:
    """Write machine-readable results matrix JSON after each run (Rule CS6)."""
    matrix = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": GENERATOR_VERSION,
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results if r["status"] == "OK"),
            "no_analysis": sum(1 for r in results if r["status"] == "NO_ANALYSIS"),
            "failed": sum(
                1 for r in results
                if r["status"] not in ("OK", "NO_ANALYSIS")
            ),
        },
        "dropout_threshold_s": 600,
        "dropout_candidates": [
            r["slug"] for r in results if r["elapsed_s"] > 600
        ],
        "demos": [
            {
                "slug": r["slug"],
                "engine": r["engine"],
                "status": r["status"],
                "analysis_types": r["types"],
                "elapsed_s": r["elapsed_s"],
                "error": r.get("error"),
                "flagged_slow": r["elapsed_s"] > 600,
            }
            for r in results
        ],
    }

    RESULTS_MATRIX_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_MATRIX_PATH.write_text(json.dumps(matrix, indent=2) + "\n")
    log.info("Results matrix written to %s", RESULTS_MATRIX_PATH)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
