"""
Gate 0.3: Dangling Call Detector

Ensures all QMSService calls resolve to existing methods on canonical QMSService.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _find_repo_root() -> Path:
    """Find repository root (directory containing pyproject.toml or .git)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repository root")


REPO_ROOT = _find_repo_root()


def test_no_dangling_calls():
    """Ensure all QMSService calls resolve to existing methods."""
    scanner_path = REPO_ROOT / "tools/api_dangling_calls_scanner.py"

    if not scanner_path.exists():
        # If scanner doesn't exist, skip test (shouldn't happen in CI)
        pytest.skip("Scanner tool not found")

    result = subprocess.run(
        [sys.executable, str(scanner_path), "--json"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    
    if result.returncode != 0:
        # Scanner failed - this is a test failure
        assert False, f"Scanner failed: {result.stderr}"
    
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Scanner output not valid JSON: {result.stdout}"
    
    dangling = data.get("dangling_calls", [])
    
    if dangling:
        error_msg = "ERROR: Dangling API call detected:\n"
        for call in dangling[:20]:  # Limit to first 20 for readability
            error_msg += f"  - {call['file']}:{call['line']}: {call['method']}\n"
            error_msg += f"    Method '{call['method_name']}' not found on qmatsuite.api.service.QMSService\n"
            error_msg += f"    Suggestion: Method exists on qmatsuite._vault._legacy_service.QMSService - needs migration\n"
        if len(dangling) > 20:
            error_msg += f"\n  ... and {len(dangling) - 20} more dangling calls\n"
        assert False, error_msg

