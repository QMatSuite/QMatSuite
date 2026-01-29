"""
Worktree runner: executed INSIDE the 0873ebf worktree to generate golden fixtures.

This script is invoked by generate_golden.py from the main worktree.
It uses the daemon from 0873ebf and crawler/recipes copied into the worktree.

CRITICAL RUNTIME CHECKS:
- Verifies git HEAD == 0873ebf
- Verifies quantumvitas module is loaded from worktree (not editable install)

Outputs JSON to stdout for generate_golden.py to capture and write.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

# Add worktree src to path (this script runs from worktree)
WORKTREE_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(WORKTREE_ROOT / "src"))
sys.path.insert(0, str(WORKTREE_ROOT / "tests"))

# Import from 0873ebf baseline
from quantumvitas.daemon.server import QVDaemon, RPCRequest
import quantumvitas

# CRITICAL: Runtime assertions to ensure worktree isolation
BASELINE_COMMIT = "0873ebf"

def verify_baseline_isolation():
    """
    Verify we are executing baseline code from worktree, not current branch.

    Checks:
    1. git HEAD matches BASELINE_COMMIT
    2. quantumvitas module is loaded from worktree path

    Raises AssertionError if isolation is violated.
    """
    # Check git HEAD
    git_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert git_head.startswith(BASELINE_COMMIT), (
        f"ERROR: Worktree git HEAD is {git_head}, expected {BASELINE_COMMIT}. "
        f"Worktree isolation violated."
    )

    # Check quantumvitas module path
    qv_module_path = Path(quantumvitas.__file__).resolve()
    worktree_src = (WORKTREE_ROOT / "src").resolve()

    assert str(qv_module_path).startswith(str(worktree_src)), (
        f"ERROR: quantumvitas loaded from {qv_module_path}, expected under {worktree_src}. "
        f"Editable install leakage detected. Set PYTHONPATH correctly."
    )

    print(f"[VERIFIED] git HEAD: {git_head}", file=sys.stderr)
    print(f"[VERIFIED] quantumvitas from: {qv_module_path}", file=sys.stderr)


# Import crawler and recipes (copied into worktree by generate_golden.py)
# Note: These are copied to tests/contract_crawler/ in worktree
from tests.contract_crawler.crawler import crawl_all_methods
from tests.contract_crawler.payloads import get_minimal_payload
from tests.contract_crawler.recipes import ALL_RECIPES


# Non-deterministic fields to normalize (NARROWED: only truly non-deterministic)
NORMALIZE_FIELDS = {
    # ULIDs - truly non-deterministic
    "id", "structure_id", "calc_id", "step_id", "run_id", "job_id",
    "calculation_id", "entry_id",
    # Timestamps - truly non-deterministic
    "created_at", "updated_at", "started_at", "completed_at", "timestamp",
    # Paths containing temp directories - non-deterministic due to temp path
    "project_root", "log_path", "io_dir",
}

# Nested fields to normalize (dot notation)
NORMALIZE_NESTED = {
    "meta.id", "meta.created_at", "meta.updated_at",
}


def normalize_value(key: str, value, parent_key: str = ""):
    """
    Normalize non-deterministic fields for comparison.

    KEY-BASED NORMALIZATION (no heuristics):
    - If key in NORMALIZE_FIELDS or full_key in NORMALIZE_NESTED, replace with placeholder
    - Placeholder type depends on field name pattern
    - Do NOT examine value content to decide normalization
    """
    full_key = f"{parent_key}.{key}" if parent_key else key

    # Check if this field should be normalized (key-based only)
    if key in NORMALIZE_FIELDS or full_key in NORMALIZE_NESTED:
        # Determine placeholder by field name (not by value content)
        if "timestamp" in key.lower() or key in ("created_at", "updated_at", "started_at", "completed_at"):
            return "<NORMALIZED_TIMESTAMP>"
        elif "path" in key.lower() or key in ("project_root", "log_path", "io_dir"):
            return "<NORMALIZED_PATH>"
        else:
            # Default: ID-like fields
            return "<NORMALIZED_ID>"

    # Recursively normalize dicts and lists
    if isinstance(value, dict):
        return {k: normalize_value(k, v, full_key) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_value(key, item, parent_key) for item in value]

    return value


def normalize_response(response_data: dict) -> dict:
    """Normalize response for golden comparison."""
    return {k: normalize_value(k, v) for k, v in response_data.items()}


def main():
    """
    Run crawler and recipes, output JSON to stdout.

    Flow:
    1. Verify baseline isolation
    2. Run auto-crawler, store results with payload metadata
    3. Run recipes, store results with recipe_name metadata
    4. Output all golden fixtures as JSON to stdout
    """
    # STEP 1: Verify we're running baseline code
    verify_baseline_isolation()

    baseline_commit = "0873ebf"
    all_golden = {}

    print("\nRunning auto-crawler from 0873ebf...", file=sys.stderr)

    # STEP 2: Run auto-crawler
    report = crawl_all_methods()
    for result in report.results:
        if result.success and not result.needs_recipe:
            # Get the payload used for this method
            payload = get_minimal_payload(result.method_name)

            all_golden[result.method_name] = {
                "method": result.method_name,
                "success": True,
                "response": normalize_response(result.response_data),
                "payload": payload,  # Store for deterministic replay
                "baseline_commit": baseline_commit,
                "generated_at": datetime.now().isoformat(),
                "source": "auto_crawler",
            }
            print(f"  [auto] {result.method_name}: OK", file=sys.stderr)
        elif not result.needs_recipe:
            # Auto-crawler method that failed
            all_golden[result.method_name] = {
                "method": result.method_name,
                "success": False,
                "error": result.error or {"code": "unknown", "message": result.skipped_reason or "Unknown failure"},
                "baseline_commit": baseline_commit,
                "generated_at": datetime.now().isoformat(),
                "source": "auto_crawler",
            }
            print(f"  [auto] {result.method_name}: FAILED - {result.error}", file=sys.stderr)

    print(f"\nRunning {len(ALL_RECIPES)} recipes from 0873ebf...", file=sys.stderr)

    # STEP 3: Run recipes
    import tempfile
    temp_base = Path(tempfile.mkdtemp(prefix="qv_recipe_"))

    for recipe_cls in ALL_RECIPES:
        method_name = recipe_cls.method_name
        recipe_name = recipe_cls.__name__
        recipe_dir = temp_base / recipe_name
        recipe_dir.mkdir(exist_ok=True)

        try:
            recipe = recipe_cls(recipe_dir)
            result = recipe.execute()

            if result.success:
                all_golden[method_name] = {
                    "method": method_name,
                    "success": True,
                    "response": normalize_response(result.response_data),
                    "recipe_name": recipe_name,  # Store recipe class name for replay
                    "baseline_commit": baseline_commit,
                    "generated_at": datetime.now().isoformat(),
                    "source": "recipe",
                }
                print(f"  [recipe] {method_name} ({recipe_name}): OK", file=sys.stderr)
            else:
                all_golden[method_name] = {
                    "method": method_name,
                    "success": False,
                    "error": {"code": "recipe_failure", "message": result.error or "Unknown failure"},
                    "recipe_name": recipe_name,
                    "baseline_commit": baseline_commit,
                    "generated_at": datetime.now().isoformat(),
                    "source": "recipe",
                }
                print(f"  [recipe] {method_name} ({recipe_name}): FAILED - {result.error}", file=sys.stderr)
        except Exception as e:
            all_golden[method_name] = {
                "method": method_name,
                "success": False,
                "error": {"code": "recipe_exception", "message": str(e)},
                "recipe_name": recipe_name,
                "baseline_commit": baseline_commit,
                "generated_at": datetime.now().isoformat(),
                "source": "recipe",
            }
            print(f"  [recipe] {method_name} ({recipe_name}): EXCEPTION - {e}", file=sys.stderr)

    # STEP 4: Output JSON to stdout
    print(json.dumps(all_golden, indent=2))


if __name__ == "__main__":
    main()

