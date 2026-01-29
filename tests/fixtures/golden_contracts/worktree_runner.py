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
# worktree_runner.py is at: worktree/tests/fixtures/golden_contracts/worktree_runner.py
# So we need to go up 4 levels to get to worktree root
WORKTREE_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(WORKTREE_ROOT / "src"))
sys.path.insert(0, str(WORKTREE_ROOT / "tests"))

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

    # Import quantumvitas AFTER setting up path, then check its location
    import quantumvitas
    qv_module_path = Path(quantumvitas.__file__).resolve()
    worktree_src = (WORKTREE_ROOT / "src").resolve()

    assert str(qv_module_path).startswith(str(worktree_src)), (
        f"ERROR: quantumvitas loaded from {qv_module_path}, expected under {worktree_src}. "
        f"Editable install leakage detected. Set PYTHONPATH correctly."
    )

    print(f"[VERIFIED] git HEAD: {git_head}", file=sys.stderr)
    print(f"[VERIFIED] quantumvitas from: {qv_module_path}", file=sys.stderr)


# Verify isolation FIRST before importing anything
verify_baseline_isolation()

# Import from 0873ebf baseline (after path setup and verification)
from quantumvitas.daemon.server import QVDaemon, RPCRequest

# Import crawler and recipes (copied into worktree by generate_golden.py)
# Note: These are copied to tests/contract_crawler/ in worktree
# Use direct file imports since tests/ may not be a package in worktree
crawler_path = WORKTREE_ROOT / "tests" / "contract_crawler" / "crawler.py"
payloads_path = WORKTREE_ROOT / "tests" / "contract_crawler" / "payloads.py"
recipes_path = WORKTREE_ROOT / "tests" / "contract_crawler" / "recipes" / "__init__.py"

# Import using importlib to handle the module loading
import importlib.util

spec = importlib.util.spec_from_file_location("contract_crawler.crawler", crawler_path)
crawler_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crawler_module)
crawl_all_methods = crawler_module.crawl_all_methods

spec = importlib.util.spec_from_file_location("contract_crawler.payloads", payloads_path)
payloads_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(payloads_module)
get_minimal_payload = payloads_module.get_minimal_payload

spec = importlib.util.spec_from_file_location("contract_crawler.recipes", recipes_path)
recipes_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipes_module)
ALL_RECIPES = recipes_module.ALL_RECIPES
get_recipe_for_method = recipes_module.get_recipe_for_method


# Non-deterministic fields to normalize (expanded for v0 compat testing)
# MUST MATCH tests/contract_crawler/normalization.py
NORMALIZE_FIELDS = {
    # ULIDs - truly non-deterministic
    "id", "structure_id", "calc_id", "step_id", "run_id", "job_id",
    "calculation_id", "entry_id", "calculation_ulid", "target_ulid",
    "target_name", "step", "calculation", "parent_calculation_id",
    # ULID-derived fields (suffix = last 6 chars of ULID)
    "suffix",
    # Arrays of IDs
    "structure_ids",
    # Timestamps - truly non-deterministic
    "created_at", "updated_at", "started_at", "completed_at", "timestamp",
    "cached_at", "generated_at",
    # Paths containing temp directories - non-deterministic due to temp path
    "project_root", "log_path", "io_dir", "path", "absolute_path",
    "output_file", "resolved_path", "metadata_path_abs",
    # QE detection paths - vary by environment
    "qe_home", "qe_bin_dir", "pw_path", "current_bin_dir",
    # Engine discovery fields - engine_id varies
    "engine_id",
    # Environment info - vary by system
    "python_version", "python_executable", "qv_version",
    # Session IDs - UUIDs
    "session_id",
}

# Nested fields to normalize (dot notation)
NORMALIZE_NESTED = {
    "meta.id", "meta.created_at", "meta.updated_at", "meta.path",
    "prefix_outdir_injection.effective_prefix",
}

import re

# ULID pattern: 26 uppercase alphanumeric chars
ULID_PATTERN = re.compile(r'^[0-9A-Z]{26}$')

# Temp path patterns
TEMP_PATH_PATTERNS = [
    r'/var/folders/',
    r'/private/var/folders/',
    r'/tmp/',
    r'/private/tmp/',
    r'pytest-',
    r'qv_recipe_',
    r'qv_golden_',
]

# Patterns for paths that should be normalized within message strings
# These match absolute paths that vary by environment
PATH_IN_STRING_PATTERNS = [
    # QE executable paths (e.g., "pw.x found at /path/to/pw.x")
    re.compile(r'(/[^\s]+/(?:pw|ph|dos|bands|projwfc|pp)\.x(?:\.exe)?)'),
    # QE engine paths (e.g., ".qmatsuite/engines/qe/...")
    re.compile(r'(/[^\s]+/\.qmatsuite/engines/[^\s]+)'),
    # Project paths (e.g., "Project exists: /path/to/project")
    re.compile(r'((?:Project exists|Project path)[:\s]+)(/[^\s]+)'),
    # Generic absolute paths after "at " or ": "
    re.compile(r'(at |: )(/(?:Users|home|var|private|tmp)[^\s]+)'),
    # Paths in parentheses (e.g., "QE q-e-qe-7.5 (/Users/...)")
    re.compile(r'(\()(/(?:Users|home|var|private|tmp)[^\s\)]+)(\))'),
    # Created dir messages (e.g., "Created store dir: /path/to/dir")
    re.compile(r'(Created (?:store|seed) dir: )(/[^\s]+)'),
]


def _is_ulid_like(value: str) -> bool:
    """Check if value looks like a ULID."""
    return bool(ULID_PATTERN.match(value))


def _is_temp_path(value: str) -> bool:
    """Check if value is a temp path."""
    return any(pattern in value for pattern in TEMP_PATH_PATTERNS)


def _normalize_paths_in_string(value: str) -> str:
    """Normalize absolute paths embedded in message strings."""
    result = value
    for pattern in PATH_IN_STRING_PATTERNS:
        # Replace paths with normalized placeholder, preserving prefix/suffix
        if pattern.groups == 1:
            # Pattern captures just the path
            result = pattern.sub('<NORMALIZED_PATH>', result)
        elif pattern.groups == 2:
            # Pattern captures prefix + path
            result = pattern.sub(r'\1<NORMALIZED_PATH>', result)
        elif pattern.groups == 3:
            # Pattern captures prefix + path + suffix (e.g., parentheses)
            result = pattern.sub(r'\1<NORMALIZED_PATH>\3', result)
    return result


def normalize_value(key: str, value, parent_key: str = ""):
    """
    Normalize non-deterministic fields for comparison.

    Uses both key-based and value-based heuristics:
    - If key in NORMALIZE_FIELDS or full_key in NORMALIZE_NESTED, replace with placeholder
    - If value looks like a ULID, normalize it
    - If value is a temp path, normalize it
    """
    full_key = f"{parent_key}.{key}" if parent_key else key

    # Check if this field should be normalized (key-based)
    if key in NORMALIZE_FIELDS or full_key in NORMALIZE_NESTED:
        # Determine placeholder by field name
        if "timestamp" in key.lower() or key in ("created_at", "updated_at", "started_at", "completed_at", "cached_at", "generated_at"):
            return "<NORMALIZED_TIMESTAMP>"
        elif "path" in key.lower() or key in ("project_root", "log_path", "io_dir", "absolute_path", "output_file", "resolved_path", "metadata_path_abs", "qe_home", "qe_bin_dir", "pw_path", "python_executable", "current_bin_dir"):
            return "<NORMALIZED_PATH>"
        else:
            # Default: ID-like fields
            return "<NORMALIZED_ID>"

    # Value-based heuristics for strings
    if isinstance(value, str):
        # Check for ULID-like values
        if _is_ulid_like(value):
            return "<NORMALIZED_ID>"
        # Check for temp paths
        if _is_temp_path(value):
            return "<NORMALIZED_PATH>"
        # Normalize paths embedded in message and label strings (when they contain paths)
        if key in ("message", "label") or "message" in key.lower():
            normalized = _normalize_paths_in_string(value)
            if normalized != value:
                return normalized

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
    1. Verify baseline isolation (already done at module level)
    2. Run auto-crawler, store results with payload metadata
    3. Run recipes, store results with recipe_name metadata
    4. Output all golden fixtures as JSON to stdout
    """
    # Isolation already verified at module import time

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

    # STEP 3: Load GUI methods for prioritization
    gui_methods = set()
    gui_methods_file = WORKTREE_ROOT / "gui" / "tests" / "e2e" / "tools" / "gui_rpc_methods.txt"
    if gui_methods_file.exists():
        gui_methods = set(line.strip() for line in gui_methods_file.read_text().splitlines() if line.strip())
        print(f"Loaded {len(gui_methods)} GUI-used methods for prioritization", file=sys.stderr)

    print(f"\nRunning recipes from 0873ebf...", file=sys.stderr)

    # STEP 4: Run static recipes (from ALL_RECIPES)
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
                    "recipe_name": recipe_name,
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

    # STEP 5: Run parameterized recipes for ALL methods not yet covered
    if get_recipe_for_method:
        # Dynamically load parameterized recipes module
        param_recipes_path = WORKTREE_ROOT / "tests" / "contract_crawler" / "recipes" / "parameterized.py"
        if param_recipes_path.exists():
            spec_param = importlib.util.spec_from_file_location("contract_crawler.recipes.parameterized", param_recipes_path)
            param_module = importlib.util.module_from_spec(spec_param)
            spec_param.loader.exec_module(param_module)
            PARAMETERIZED_RECIPES = param_module.PARAMETERIZED_RECIPES

            # Collect ALL methods that need parameterized recipes (not just GUI)
            methods_to_cover = set()
            for recipe_cls in PARAMETERIZED_RECIPES:
                if recipe_cls is None:
                    continue
                for method_name in recipe_cls.COVERED_METHODS:
                    if method_name not in all_golden:  # Not already covered
                        methods_to_cover.add((method_name, recipe_cls))

            # Sort: GUI methods first, then alphabetical
            methods_to_cover = sorted(methods_to_cover, key=lambda x: (x[0] not in gui_methods, x[0]))
            
            for method_name, recipe_cls in methods_to_cover:
                recipe_name = f"{recipe_cls.__name__}({method_name})"
                recipe_dir = temp_base / f"{recipe_cls.__name__}_{method_name}"
                recipe_dir.mkdir(exist_ok=True)
                
                try:
                    recipe = recipe_cls(recipe_dir, method_name)
                    result = recipe.execute()
                    
                    if result.success:
                        all_golden[method_name] = {
                            "method": method_name,
                            "success": True,
                            "response": normalize_response(result.response_data),
                            "recipe_name": recipe_name,
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

    # STEP 6: Output JSON to stdout
    print(json.dumps(all_golden, indent=2))


if __name__ == "__main__":
    main()

