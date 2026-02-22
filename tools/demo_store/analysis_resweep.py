#!/usr/bin/env python3
"""
Re-sweep analysis over preserved demo workdirs (no engine re-runs).

For each preserved project in .tmp/refpack_runs/<slug>/:
1. Re-instantiate QMSService(project_root)
2. Find latest run_ulid from calculation
3. Probe all analysis types via run_post_run_analysis
4. Emit per-demo coverage report with expected vs actual counts

Usage:
  python tools/demo_store/analysis_resweep.py [--report] [--only=slug1,slug2]
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

WORK_DIR = REPO_ROOT / ".tmp" / "refpack_runs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("analysis_resweep")


def _get_expected_analysis_count(engine: str, gen_steps: list[str]) -> tuple[int, list[str]]:
    """
    Compute how many analysis objects SHOULD resolve given engine capabilities
    and the calculation's gen_step sequence.

    Returns (expected_count, list of expected "object_type(gen_steps)" descriptions).
    """
    from qmatsuite.core.analysis.capability import enumerate_all_matches
    from qmatsuite.core.driver_registry import DriverRegistry

    try:
        driver = DriverRegistry.get_driver(engine)
    except Exception:
        return 0, []

    caps = getattr(driver, "ANALYSIS_CAPABILITIES", []) or []
    if not caps or not gen_steps:
        return 0, []

    # Build fake ordered_gen_steps with placeholder paths/ulids
    fake_path = Path("/tmp/fake")
    fake_ordered = [(f"FAKE_{i}", gs, fake_path) for i, gs in enumerate(gen_steps)]

    matches = enumerate_all_matches(caps, fake_ordered)
    descriptions = [f"{m.object_type}({'+'.join(m.gen_steps)})" for m in matches]
    return len(matches), descriptions


def resweep_one_demo(slug: str) -> dict[str, Any]:
    """Re-sweep analysis for one preserved demo workdir."""
    from qmatsuite.api.service import QMSService
    from qmatsuite.core.analysis.capability import ResultState
    from qmatsuite.core.analysis.orchestrator import run_post_run_analysis

    work_dir = WORK_DIR / slug
    result: dict[str, Any] = {
        "slug": slug,
        "engine": "",
        "status": "UNKNOWN",
        "gen_steps": [],
        "expected_count": 0,
        "expected_descriptions": [],
        "ok_count": 0,
        "ok_types": [],
        "missing_count": 0,
        "missing_types": [],
        "error_count": 0,
        "error_types": [],
        "details": [],
    }

    # Find project root (subdirectory with project.qms.yml)
    project_root = None
    for child in work_dir.iterdir():
        if child.is_dir() and (child / "project.qms.yml").exists():
            project_root = child
            break
    if project_root is None:
        result["status"] = "NO_PROJECT"
        result["error"] = "No project.qms.yml found"
        return result

    try:
        svc = QMSService(project_root)

        # List calculations
        calcs = svc.calculation.list()
        if not calcs:
            result["status"] = "NO_CALCULATIONS"
            return result

        calc_dto = calcs[0]
        calc_ulid = calc_dto.calc_ulid
        engine = calc_dto.engine or ""
        result["engine"] = engine

        # Load full calculation model for step details
        from qmatsuite.core.models import load_calculation
        from qmatsuite.core.project_utils import load_project_config
        from qmatsuite.core.resolution import make_structure_selector_resolver

        # Find calc dir by globbing (avoids index lookup issues)
        calc_yamls = list(project_root.glob("calculations/*/calculation.yaml"))
        if not calc_yamls:
            result["status"] = "NO_CALC_DIR"
            result["error"] = "No calculation.yaml found"
            return result
        calc_dir = calc_yamls[0].parent
        config = load_project_config(project_root)
        resolver = make_structure_selector_resolver(project_root, config=config)
        calc_model = load_calculation(
            calc_dir / "calculation.yaml",
            project_root=project_root,
            resolve_structure_selector=resolver,
        )

        # Get gen_steps from calculation model
        gen_steps = []
        for step in calc_model.steps:
            gen = svc._safe_step_type_gen(step.step_type_spec or "")
            gen_steps.append(gen)
        result["gen_steps"] = gen_steps

        # Compute expected analysis count
        exp_count, exp_descs = _get_expected_analysis_count(engine, gen_steps)
        result["expected_count"] = exp_count
        result["expected_descriptions"] = exp_descs

        # Find run_ulid from provenance DB
        run_ulid = None
        try:
            from qmatsuite.provenance.db import get_db_path
            import sqlite3
            db_path = get_db_path(project_root)
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                try:
                    rows = conn.execute(
                        "SELECT run_ulid FROM runs ORDER BY run_ulid DESC LIMIT 1"
                    ).fetchall()
                    if rows:
                        run_ulid = rows[0][0]
                finally:
                    conn.close()
        except Exception:
            pass

        if not run_ulid:
            result["status"] = "NO_RUN"
            result["error"] = "No run_ulid found in provenance DB"
            return result

        # Resolve context and run analysis
        try:
            _calc_ulid, calc_dir, engine_name, driver, ordered_gen_steps = (
                svc._resolve_run_analysis_context(run_ulid)
            )
        except Exception as exc:
            result["status"] = "CONTEXT_ERROR"
            result["error"] = str(exc)
            return result

        results_list = run_post_run_analysis(
            engine=engine_name,
            driver=driver,
            ordered_gen_steps=ordered_gen_steps,
            run_ulid=run_ulid,
            calc_ulid=_calc_ulid,
            calc_dir=calc_dir,
        )

        ok_types = []
        missing_types = []
        error_types = []
        for row in results_list:
            detail = {
                "object_type": row.object_type,
                "state": row.state.value,
                "gen_steps": row.gen_steps,
                "match_key": row.match_key,
            }
            if row.reason:
                detail["reason"] = row.reason.value
            if row.error:
                detail["error"] = row.error
            result["details"].append(detail)

            if row.state == ResultState.OK:
                ok_types.append(f"{row.object_type}({'+'.join(row.gen_steps)})")
            elif row.state == ResultState.MISSING_EVIDENCE:
                reason_str = row.reason.value if row.reason else "?"
                missing_types.append(f"{row.object_type}({'+'.join(row.gen_steps)}): {reason_str}")
            elif row.state == ResultState.PARSER_ERROR:
                error_types.append(f"{row.object_type}({'+'.join(row.gen_steps)}): {row.error}")

        result["ok_count"] = len(ok_types)
        result["ok_types"] = ok_types
        result["missing_count"] = len(missing_types)
        result["missing_types"] = missing_types
        result["error_count"] = len(error_types)
        result["error_types"] = error_types

        if result["ok_count"] > 0:
            result["status"] = "OK"
        elif result["missing_count"] > 0 or result["error_count"] > 0:
            result["status"] = "NO_ANALYSIS"
        else:
            result["status"] = "NO_MATCHES"

    except Exception as exc:
        import traceback
        result["status"] = "ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"
        log.error("  %s: %s\n%s", slug, exc, traceback.format_exc())

    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Re-sweep analysis over preserved demo workdirs")
    parser.add_argument("--only", type=str, default="", help="Comma-separated slugs")
    parser.add_argument("--report", action="store_true", help="Emit detailed report")
    args = parser.parse_args()

    only_set = set(args.only.split(",")) if args.only else set()

    if not WORK_DIR.exists():
        log.error("No preserved workdirs at %s", WORK_DIR)
        return 1

    slugs = sorted(d.name for d in WORK_DIR.iterdir() if d.is_dir())
    if only_set:
        slugs = [s for s in slugs if s in only_set]

    log.info("Re-sweeping %d demos from %s", len(slugs), WORK_DIR)

    # Ensure all drivers registered
    import qmatsuite.drivers  # noqa: F401

    results = []
    for i, slug in enumerate(slugs, 1):
        log.info("[%d/%d] %s", i, len(slugs), slug)
        r = resweep_one_demo(slug)
        results.append(r)

        ok = r["ok_count"]
        exp = r["expected_count"]
        match_str = "MATCH" if ok == exp else f"MISMATCH (exp={exp})"
        log.info("  resolved=%d/%d %s | %s",
                 ok, exp, match_str,
                 ", ".join(r["ok_types"]) or "none")
        if r["missing_types"]:
            for mt in r["missing_types"]:
                log.info("    MISSING: %s", mt)
        if r["error_types"]:
            for et in r["error_types"]:
                log.info("    ERROR: %s", et)

    # Summary statistics
    total = len(results)
    ok = sum(1 for r in results if r["status"] == "OK")
    no_analysis = sum(1 for r in results if r["status"] in ("NO_ANALYSIS", "NO_MATCHES"))
    errors = sum(1 for r in results if r["status"] not in ("OK", "NO_ANALYSIS", "NO_MATCHES"))

    total_expected = sum(r["expected_count"] for r in results)
    total_resolved = sum(r["ok_count"] for r in results)
    total_missing = sum(r["missing_count"] for r in results)
    total_errors = sum(r["error_count"] for r in results)

    full_match = sum(1 for r in results if r["ok_count"] == r["expected_count"])
    partial_match = sum(1 for r in results if 0 < r["ok_count"] < r["expected_count"])
    zero_match = sum(1 for r in results if r["ok_count"] == 0)

    print("\n" + "=" * 90)
    print("ANALYSIS RE-SWEEP RESULTS")
    print(f"  Demos: {total} total, {ok} with analysis, {no_analysis} without, {errors} errors")
    print(f"  Objects: {total_resolved}/{total_expected} resolved "
          f"({total_missing} missing, {total_errors} parser errors)")
    print(f"  Coverage: {full_match} full-match, {partial_match} partial, {zero_match} zero")
    print("=" * 90)

    # Detailed table
    print(f"\n{'Slug':40s} {'Engine':10s} {'Steps':>5s} {'Exp':>4s} {'OK':>4s} "
          f"{'Miss':>4s} {'Err':>4s} {'Status'}")
    print("-" * 90)
    for r in sorted(results, key=lambda x: (x["status"] != "OK", x["slug"])):
        n_steps = len(r["gen_steps"])
        flag = "" if r["ok_count"] == r["expected_count"] else " <--"
        print(
            f"{r['slug']:40s} {r['engine']:10s} {n_steps:>5d} {r['expected_count']:>4d} "
            f"{r['ok_count']:>4d} {r['missing_count']:>4d} {r['error_count']:>4d} "
            f"{r['status']}{flag}"
        )

    # Report mismatches in detail
    mismatches = [r for r in results if r["ok_count"] != r["expected_count"]]
    if mismatches:
        print(f"\n{'MISMATCHES (expected != resolved):':=^90}")
        for r in mismatches:
            print(f"\n  {r['slug']} ({r['engine']}):")
            print(f"    Gen steps: {' -> '.join(r['gen_steps'])}")
            print(f"    Expected ({r['expected_count']}): {', '.join(r['expected_descriptions'])}")
            print(f"    Resolved ({r['ok_count']}): {', '.join(r['ok_types']) or 'none'}")
            if r["missing_types"]:
                print(f"    Missing:  {', '.join(r['missing_types'])}")
            if r["error_types"]:
                print(f"    Errors:   {', '.join(r['error_types'])}")

    # Write JSON report
    output_path = REPO_ROOT / ".tmp" / "analysis_resweep_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "total": total,
                    "ok": ok,
                    "no_analysis": no_analysis,
                    "errors": errors,
                    "total_expected": total_expected,
                    "total_resolved": total_resolved,
                    "total_missing": total_missing,
                    "total_errors": total_errors,
                    "full_match": full_match,
                    "partial_match": partial_match,
                    "zero_match": zero_match,
                },
                "demos": results,
            },
            f,
            indent=2,
            default=str,
        )
    print(f"\nResults written to: {output_path}")

    return 0 if zero_match == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
