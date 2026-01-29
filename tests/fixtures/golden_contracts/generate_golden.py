"""
Generate golden fixture files from commit 0873ebf.

This script:
1. Creates git worktree at 0873ebf
2. Copies contract_crawler package into worktree (0873ebf won't have it)
3. Copies worktree_runner.py into worktree
4. Runs worktree_runner.py with isolated PYTHONPATH (worktree-only)
5. Captures JSON output and writes to tests/fixtures/golden_0873ebf/daemon/
6. Cleans up worktree

Usage:
    python generate_golden.py    # Generate from 0873ebf worktree (REQUIRED)

IMPORTANT: Golden MUST come from 0873ebf. No --current flag allowed.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE_COMMIT = "0873ebf"
REPO_ROOT = Path(__file__).parent.parent.parent.parent
GOLDEN_OUTPUT_DIR = REPO_ROOT / "tests" / "fixtures" / "golden_0873ebf" / "daemon"


def setup_worktree(commit: str, worktree_path: Path) -> bool:
    """
    Create git worktree for the specified commit.

    Args:
        commit: Git commit hash or ref
        worktree_path: Path where worktree will be created

    Returns:
        True if worktree created successfully.
    """
    # Remove existing worktree if present
    if worktree_path.exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=REPO_ROOT,
            capture_output=True,
        )

    # Create new worktree
    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), commit],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"ERROR: Failed to create worktree: {result.stderr}", file=sys.stderr)
        return False

    return True


def cleanup_worktree(worktree_path: Path):
    """Remove git worktree."""
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        cwd=REPO_ROOT,
        capture_output=True,
    )


def copy_contract_crawler_to_worktree(worktree_path: Path):
    """
    Copy contract_crawler package into worktree.

    0873ebf does not contain tests/contract_crawler/, so we must copy
    the current implementation (crawler, payloads, recipes, introspection)
    into the worktree before execution.

    Files copied:
    - tests/contract_crawler/__init__.py
    - tests/contract_crawler/introspection.py
    - tests/contract_crawler/payloads.py
    - tests/contract_crawler/crawler.py
    - tests/contract_crawler/recipes/ (entire directory)
    """
    src_crawler = REPO_ROOT / "tests" / "contract_crawler"
    dst_crawler = worktree_path / "tests" / "contract_crawler"

    # Create destination directory
    dst_crawler.mkdir(parents=True, exist_ok=True)

    # Copy package files
    files_to_copy = [
        "__init__.py",
        "introspection.py",
        "payloads.py",
        "crawler.py",
        "v0_payloads.py",  # Centralized v0 payload schemas
    ]

    for filename in files_to_copy:
        src_file = src_crawler / filename
        dst_file = dst_crawler / filename
        if src_file.exists():
            shutil.copy2(src_file, dst_file)
            print(f"  Copied {filename} to worktree", file=sys.stderr)
        else:
            print(f"  WARNING: {filename} not found, skipping", file=sys.stderr)

    # Copy recipes directory
    src_recipes = src_crawler / "recipes"
    dst_recipes = dst_crawler / "recipes"
    if src_recipes.exists():
        shutil.copytree(src_recipes, dst_recipes, dirs_exist_ok=True)
        print(f"  Copied recipes/ to worktree", file=sys.stderr)
    else:
        print(f"  WARNING: recipes/ not found, skipping", file=sys.stderr)
    
    # Copy GUI methods file if it exists (for prioritization)
    gui_methods_src = REPO_ROOT / "gui" / "tests" / "e2e" / "tools" / "gui_rpc_methods.txt"
    if gui_methods_src.exists():
        gui_methods_dst = worktree_path / "gui" / "tests" / "e2e" / "tools" / "gui_rpc_methods.txt"
        gui_methods_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gui_methods_src, gui_methods_dst)
        print(f"  Copied gui_rpc_methods.txt to worktree", file=sys.stderr)


def run_worktree_runner(worktree_path: Path) -> dict:
    """
    Execute worktree_runner.py inside the worktree and capture JSON output.

    CRITICAL: Sets PYTHONPATH to worktree-only paths to prevent editable install leakage.

    Args:
        worktree_path: Path to git worktree

    Returns:
        Dict of method_name -> golden fixture data
    """
    runner_script = worktree_path / "tests" / "fixtures" / "golden_contracts" / "worktree_runner.py"

    print(f"Running worktree_runner.py from {worktree_path}...", file=sys.stderr)

    # Set PYTHONPATH to worktree-only paths
    # This prevents Python from loading quantumvitas from editable install
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([
        str(worktree_path / "src"),
        str(worktree_path / "tests"),
    ])

    # Run the runner script from worktree with isolated PYTHONPATH
    result = subprocess.run(
        [sys.executable, str(runner_script)],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        env=env,  # Use isolated environment
    )

    # Print stderr (contains verification output)
    print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"\nERROR: worktree_runner.py failed with exit code {result.returncode}", file=sys.stderr)
        print(f"stderr output shown above", file=sys.stderr)
        sys.exit(1)

    # Parse JSON from stdout
    try:
        all_golden = json.loads(result.stdout)
        return all_golden
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON output from worktree_runner.py:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        print(f"stdout:\n{result.stdout}", file=sys.stderr)
        sys.exit(1)


def main():
    """
    Generate golden fixtures from commit 0873ebf via worktree runner.

    Flow:
    1. Create worktree at 0873ebf
    2. Copy contract_crawler package into worktree
    3. Copy worktree_runner.py into worktree
    4. Run worktree_runner.py with isolated PYTHONPATH
    5. Capture JSON and write to golden_0873ebf/daemon/
    6. Clean up worktree
    """
    print(f"Generating golden fixtures from baseline commit {BASELINE_COMMIT}")
    print("Using git worktree + worktree_runner.py...\n")

    # Create worktree in temp directory
    worktree_path = Path(tempfile.mkdtemp(prefix="qv_golden_0873ebf_"))

    try:
        # STEP 1: Create worktree
        if not setup_worktree(BASELINE_COMMIT, worktree_path):
            print("ERROR: Failed to create worktree. Aborting.", file=sys.stderr)
            sys.exit(1)

        print(f"Worktree created at: {worktree_path}\n")

        # STEP 2: Copy contract_crawler package into worktree
        print("Copying contract_crawler package into worktree...", file=sys.stderr)
        copy_contract_crawler_to_worktree(worktree_path)
        print()

        # STEP 3: Copy worktree_runner.py into the worktree
        runner_src = Path(__file__).parent / "worktree_runner.py"
        runner_dst = worktree_path / "tests" / "fixtures" / "golden_contracts" / "worktree_runner.py"
        runner_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(runner_src, runner_dst)
        print(f"Copied worktree_runner.py to worktree\n", file=sys.stderr)

        # STEP 4: Run worktree_runner.py and capture JSON
        all_golden = run_worktree_runner(worktree_path)

    finally:
        print("\nCleaning up worktree...", file=sys.stderr)
        cleanup_worktree(worktree_path)
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)

    # STEP 5: Write output files to tests/fixtures/golden_0873ebf/daemon/
    GOLDEN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    success_count = 0
    failure_count = 0

    for method_name, golden in all_golden.items():
        output_file = GOLDEN_OUTPUT_DIR / f"{method_name}.json"
        with open(output_file, "w") as f:
            json.dump(golden, f, indent=2)

        if golden.get("success"):
            success_count += 1
        else:
            failure_count += 1

    # Write combined manifest
    manifest = {
        "baseline_commit": BASELINE_COMMIT,
        "total_methods": len(all_golden),
        "success_count": success_count,
        "failure_count": failure_count,
        "methods": list(all_golden.keys()),
    }
    with open(GOLDEN_OUTPUT_DIR / "_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Golden fixture generation complete")
    print(f"{'='*60}")
    print(f"Baseline commit: {BASELINE_COMMIT}")
    print(f"Total methods: {len(all_golden)}")
    print(f"  Success: {success_count}")
    print(f"  Failure: {failure_count}")
    print(f"Output directory: {GOLDEN_OUTPUT_DIR}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

